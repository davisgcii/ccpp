"""Stage 2 Redactor: Entity extraction and masking.

This module provides PII entity extraction from flagged text. For mock mode,
uses regex patterns to find entities. In production, will load a fine-tuned
model that generates entity extraction commands.
"""

import re
from typing import Optional

from ccpp.infer import patterns
from ccpp.llm.base import GenerationConfig, LLMBackend
from ccpp.llm.factory import create_backend_from_config
from ccpp.types import MaskSpan, PIICategory, RedactorOutput


class Stage2Redactor:
    """Stage 2: Accurate PII entity extractor.

    Mock implementation uses regex patterns. Real implementation will load
    a fine-tuned model (Qwen2.5-7B or similar) that generates:
        PASS
        MASK "entity" category
        MASK "entity1" category1; MASK "entity2" category2
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "cuda",
        mock_mode: bool = True,
        llm_config: Optional[dict] = None,
        llm_backend: Optional[LLMBackend] = None,
    ):
        """Initialize Stage 2 redactor.

        Args:
            model_path: Path to fine-tuned model (for direct loading, future use)
            device: Device to run model on ("cuda" or "cpu")
            mock_mode: If True, use regex-based extraction (for development)
            llm_config: LLM harness configuration dict (for Phase 0 base model testing)
            llm_backend: Pre-initialized LLM backend (alternative to llm_config)
        """
        self.mock_mode = mock_mode
        self.device = device
        self.backend = None
        self.prompt_template = ""  # New: single template with {context} and {window_text}
        self.few_shot_examples = []  # Legacy: kept for backwards compatibility
        self.system_prompt = ""  # Legacy: kept for backwards compatibility

        # Regex patterns for mock-mode extraction live in ccpp.infer.patterns
        # (shared with FastHeuristics so the two never drift apart).

        if not mock_mode:
            # Priority: llm_backend > llm_config > model_path
            if llm_backend:
                self.backend = llm_backend
                self._load_config_from_dict(llm_config or {})
            elif llm_config:
                self.backend = create_backend_from_config(llm_config)
                self._load_config_from_dict(llm_config)
            elif model_path:
                # Future: Load fine-tuned model directly (MLX, transformers)
                raise NotImplementedError("Direct model loading not yet implemented")
            else:
                raise ValueError(
                    "When mock_mode=False, must provide llm_backend, llm_config, or model_path"
                )

    def _load_config_from_dict(self, config: dict):
        """Load configuration from dict.

        Args:
            config: Configuration dict with prompt_template (preferred) or
                    legacy few_shot/system_prompt keys
        """
        # New: Load prompt template (preferred method)
        self.prompt_template = config.get("prompt_template", "")

        # Legacy: Load few-shot examples (for backwards compatibility)
        few_shot_cfg = config.get("few_shot", {})
        if few_shot_cfg.get("enabled", False):
            self.few_shot_examples = few_shot_cfg.get("examples", [])

        # Legacy: Load system prompt
        self.system_prompt = config.get("system_prompt", "")

        # Load generation config
        gen_cfg = config.get("generation", {})
        if not gen_cfg:
            gen_cfg = {
                "max_tokens": config.get("max_tokens"),
                "temperature": config.get("temperature"),
                "top_p": config.get("top_p"),
                "top_k": config.get("top_k"),
                "min_p": config.get("min_p"),
                "stop_sequences": config.get("stop_sequences"),
                "do_sample": config.get("do_sample"),
                "enable_thinking": config.get("enable_thinking"),
            }

        def _pick(cfg: dict, key: str, default):
            value = cfg.get(key)
            return default if value is None else value

        self.generation_config = GenerationConfig(
            max_tokens=_pick(gen_cfg, "max_tokens", 150),
            temperature=_pick(gen_cfg, "temperature", 0.0),
            top_p=_pick(gen_cfg, "top_p", 1.0),
            top_k=_pick(gen_cfg, "top_k", None),
            min_p=_pick(gen_cfg, "min_p", None),
            stop_sequences=_pick(gen_cfg, "stop_sequences", []),
            do_sample=_pick(gen_cfg, "do_sample", False),
            enable_thinking=_pick(gen_cfg, "enable_thinking", False),
        )

    def redact(self, messages: list[dict], window_text: str) -> RedactorOutput:
        """Extract PII entities from window text.

        Args:
            messages: Conversation history (for context)
            window_text: Text to extract entities from (with overlap tail)

        Returns:
            RedactorOutput with list of MaskSpan objects
        """
        if self.mock_mode:
            return self._mock_redact(window_text)
        else:
            return self._real_redact(messages, window_text)

    def _mock_redact(self, window_text: str) -> RedactorOutput:
        """Mock entity extraction using regex patterns.

        Returns:
            RedactorOutput with detected entities
        """
        spans = []

        # Extract emails (skip allowlisted documentation/test domains)
        for match in patterns.EMAIL.finditer(window_text):
            email = match.group()
            domain = email.split("@")[1].lower()
            if not patterns.is_allowed_email_domain(domain):
                spans.append(
                    MaskSpan(
                        entity_text=email,
                        category=PIICategory.CONTACT,
                    )
                )

        # Extract phone numbers (skip obvious placeholder prefixes)
        for match in patterns.PHONE.finditer(window_text):
            phone = match.group()
            if not phone.startswith(patterns.TEST_PHONE_PREFIXES):
                spans.append(
                    MaskSpan(
                        entity_text=phone,
                        category=PIICategory.CONTACT,
                    )
                )

        # Extract SSNs (skip obvious placeholder SSNs)
        for match in patterns.SSN.finditer(window_text):
            ssn = match.group()
            if ssn not in patterns.TEST_SSNS:
                spans.append(
                    MaskSpan(
                        entity_text=ssn,
                        category=PIICategory.GOV_ID,
                    )
                )

        # Extract API keys (skip allowlisted example keys)
        for match in patterns.API_KEY.finditer(window_text):
            key = match.group()
            if key not in patterns.ALLOWED_AWS_KEYS:
                spans.append(
                    MaskSpan(
                        entity_text=key,
                        category=PIICategory.CREDENTIALS,
                    )
                )

        return RedactorOutput(spans=spans)

    def _real_redact(self, messages: list[dict], window_text: str) -> RedactorOutput:
        """Real entity extraction using LLM backend.

        Uses generation to produce entity extraction commands via the LLM harness:
        1. Format prompt with few-shot examples + conversation + window_text
        2. Generate output
        3. Parse output to extract MaskSpan objects

        Args:
            messages: Conversation history
            window_text: Text window to extract entities from

        Returns:
            RedactorOutput with extracted entities
        """
        import logging
        import time
        logger = logging.getLogger(__name__)

        # Format prompt with few-shot examples
        prompt_messages = self._format_prompt_with_few_shot(messages, window_text)

        # Consolidated debug log
        logger.debug(
            f"[Stage2] prompt: examples={len(self.few_shot_examples)} "
            f"sys_len={len(self.system_prompt)} window={len(window_text)}ch"
        )

        # Generate entity extraction output
        start_time = time.time()
        output = self.backend.generate(
            prompt_messages,
            self.generation_config,
        )
        latency_ms = int((time.time() - start_time) * 1000)

        # Parse output to extract entities
        result = self._parse_extraction_output(output)

        # Single consolidated log with all relevant info
        logger.info(
            f"[Stage2] entities={len(result.spans)} lat={latency_ms}ms "
            f"output={repr(output[:80])}{'...' if len(output) > 80 else ''}"
        )
        return result

    def _format_prompt_with_few_shot(
        self,
        messages: list[dict],
        window_text: str
    ) -> list[dict]:
        """Format prompt for entity extraction.

        Uses one of two modes:
        1. Template mode (preferred): Uses prompt_template with {context} and {window_text}
        2. Legacy mode: Constructs prompt from system_prompt + few_shot_examples

        Args:
            messages: Conversation history
            window_text: Text window to extract entities from

        Returns:
            List of message dicts ready for LLM backend
        """
        # Format context for either mode
        actual_context = self._format_context(messages)

        # New: Template mode (preferred)
        if self.prompt_template:
            # Simple string substitution
            formatted_prompt = self.prompt_template.format(
                context=actual_context,
                window_text=window_text,
            )
            # Return as single user message (template includes everything)
            return [{"role": "user", "content": formatted_prompt}]

        # Legacy: Construct from system_prompt + few_shot_examples
        prompt = []

        # Add system prompt
        if self.system_prompt:
            prompt.append({
                "role": "system",
                "content": self.system_prompt.strip(),
            })

        # Add few-shot examples
        for example in self.few_shot_examples:
            # Format example
            example_messages = example.get("messages", [])
            example_window = example.get("window_text", "")
            example_output = example.get("output", "PASS")

            # User message: context + window text
            example_context = self._format_context(example_messages)
            prompt.append({
                "role": "user",
                "content": self._format_extraction_query(example_context, example_window),
            })

            # Assistant response: extraction output
            prompt.append({
                "role": "assistant",
                "content": example_output,
            })

        # Add actual query
        prompt.append({
            "role": "user",
            "content": self._format_extraction_query(actual_context, window_text),
        })

        return prompt

    def _format_context(self, messages: list[dict]) -> str:
        """Format conversation context as a string.

        Args:
            messages: List of message dicts

        Returns:
            Formatted context string
        """
        if not messages:
            return "(No prior context)"

        context_parts = []
        for msg in messages:
            role = msg.get("role", "").capitalize()
            content = msg.get("content", "")
            context_parts.append(f"{role}: {content}")

        return "\n".join(context_parts)

    def _format_extraction_query(self, context: str, window_text: str) -> str:
        """Format entity extraction query.

        Args:
            context: Formatted conversation context
            window_text: Text window to extract entities from

        Returns:
            Formatted query string
        """
        return f"Context:\n{context}\n\nWindow text:\n{window_text}"

    def _parse_extraction_output(self, output: str) -> RedactorOutput:
        """Parse entity extraction output.

        Expected format:
        - PASS
        - MASK "entity_text" category
        - MASK "entity1" cat1; MASK "entity2" cat2

        Args:
            output: Model output string

        Returns:
            RedactorOutput with extracted MaskSpan objects
        """
        output = output.strip()

        # If PASS, return empty spans
        if output.upper() == "PASS":
            return RedactorOutput(spans=[])

        # Parse MASK commands
        spans = []

        # Pattern: MASK "entity_text" category
        # Handles quoted strings with escaping
        mask_pattern = re.compile(
            r'MASK\s+"((?:[^"]|"")*)"\s+(\S+)',
            re.IGNORECASE
        )

        for match in mask_pattern.finditer(output):
            entity_text = match.group(1).replace('""', '"')
            category_str = match.group(2).lower().replace("-", "_")

            # Map category string to PIICategory enum
            # Categories match training data: person, contact, gov_id, identifier,
            # location, financial, credentials, medical
            try:
                if category_str == "person":
                    category = PIICategory.PERSON
                elif category_str == "contact":
                    category = PIICategory.CONTACT
                elif category_str == "gov_id":
                    category = PIICategory.GOV_ID
                elif category_str == "identifier":
                    category = PIICategory.IDENTIFIER
                elif category_str == "location":
                    category = PIICategory.LOCATION
                elif category_str == "financial":
                    category = PIICategory.FINANCIAL
                elif category_str == "credentials":
                    category = PIICategory.CREDENTIALS
                elif category_str == "medical":
                    category = PIICategory.MEDICAL
                else:
                    # Default to IDENTIFIER if unknown
                    import logging
                    logging.getLogger(__name__).warning(
                        f"Unknown PII category: {category_str}, defaulting to identifier"
                    )
                    category = PIICategory.IDENTIFIER
            except (ValueError, AttributeError):
                category = PIICategory.IDENTIFIER

            spans.append(MaskSpan(entity_text=entity_text, category=category))

        return RedactorOutput(spans=spans)

