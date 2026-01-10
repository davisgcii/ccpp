"""Stage 2 Redactor: Entity extraction and masking.

This module provides PII entity extraction from flagged text. For mock mode,
uses regex patterns to find entities. In production, will load a fine-tuned
model that generates entity extraction commands.
"""

import re
from typing import Optional

from ccpp.types import RedactorOutput, MaskSpan, PIICategory
from ccpp.llm.base import LLMBackend, GenerationConfig
from ccpp.llm.factory import create_backend_from_config


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
        self.few_shot_examples = []
        self.system_prompt = ""

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
            config: Configuration dict with few_shot, system_prompt keys
        """
        # Load few-shot examples
        few_shot_cfg = config.get("few_shot", {})
        if few_shot_cfg.get("enabled", False):
            self.few_shot_examples = few_shot_cfg.get("examples", [])

        # Load system prompt
        self.system_prompt = config.get("system_prompt", "")

        # Load generation config
        gen_cfg = config.get("generation", {})
        self.generation_config = GenerationConfig(
            max_tokens=gen_cfg.get("max_tokens", 150),
            temperature=gen_cfg.get("temperature", 0.0),
            top_p=gen_cfg.get("top_p", 1.0),
            stop_sequences=gen_cfg.get("stop_sequences", []),
            do_sample=gen_cfg.get("do_sample", False),
            enable_thinking=gen_cfg.get("enable_thinking", False),
        )

        # Regex patterns for mock mode
        self.email_pattern = re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        )
        self.phone_pattern = re.compile(
            r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"
        )
        self.ssn_pattern = re.compile(
            r"\b\d{3}-\d{2}-\d{4}\b"
        )
        self.api_key_pattern = re.compile(
            r"\b(sk_live_[a-zA-Z0-9]+|AKIA[0-9A-Z]{16}|ghp_[a-zA-Z0-9]{36})\b"
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

        # Extract emails
        for match in self.email_pattern.finditer(window_text):
            # Filter out example.com and other test domains
            email = match.group()
            domain = email.split("@")[1].lower()
            if domain not in ["example.com", "example.org", "example.net", "test", "localhost"]:
                spans.append(
                    MaskSpan(
                        entity_text=email,
                        category=PIICategory.PII_DIRECT,
                    )
                )

        # Extract phone numbers
        for match in self.phone_pattern.finditer(window_text):
            phone = match.group()
            # Filter out 555-01XX and other test numbers
            if not phone.startswith(("555-01", "555-555", "000-", "999-", "123-")):
                spans.append(
                    MaskSpan(
                        entity_text=phone,
                        category=PIICategory.PII_DIRECT,
                    )
                )

        # Extract SSNs
        for match in self.ssn_pattern.finditer(window_text):
            ssn = match.group()
            # Filter out obvious test SSNs
            if ssn not in ["000-00-0000", "999-99-9999", "123-45-6789"]:
                spans.append(
                    MaskSpan(
                        entity_text=ssn,
                        category=PIICategory.PII_DIRECT,
                    )
                )

        # Extract API keys
        for match in self.api_key_pattern.finditer(window_text):
            key = match.group()
            # Filter out example keys
            if key != "AKIAIOSFODNN7EXAMPLE":
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
        # Format prompt with few-shot examples
        prompt_messages = self._format_prompt_with_few_shot(messages, window_text)

        # Generate entity extraction output
        output = self.backend.generate(
            prompt_messages,
            self.generation_config,
        )

        # Parse output to extract entities
        return self._parse_extraction_output(output)

    def _format_prompt_with_few_shot(
        self,
        messages: list[dict],
        window_text: str
    ) -> list[dict]:
        """Format prompt with few-shot examples.

        Constructs a prompt with:
        1. System prompt (entity extraction instructions)
        2. Few-shot examples (if enabled)
        3. Actual query (conversation context + window text)

        Args:
            messages: Conversation history
            window_text: Text window to extract entities from

        Returns:
            List of message dicts ready for LLM backend
        """
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
        actual_context = self._format_context(messages)
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
            r'MASK\s+"([^"]+)"\s+(\S+)',
            re.IGNORECASE
        )

        for match in mask_pattern.finditer(output):
            entity_text = match.group(1)
            category_str = match.group(2).lower().replace("-", "_")

            # Map category string to PIICategory enum
            try:
                if category_str == "pii/direct" or category_str == "pii_direct":
                    category = PIICategory.PII_DIRECT
                elif category_str == "pii/indirect" or category_str == "pii_indirect":
                    category = PIICategory.PII_INDIRECT
                elif category_str == "credentials":
                    category = PIICategory.CREDENTIALS
                elif category_str == "financial":
                    category = PIICategory.FINANCIAL
                elif category_str == "medical":
                    category = PIICategory.MEDICAL
                elif category_str == "location/precise" or category_str == "location_precise":
                    category = PIICategory.LOCATION_PRECISE
                else:
                    # Default to PII_DIRECT if unknown
                    category = PIICategory.PII_DIRECT
            except (ValueError, AttributeError):
                category = PIICategory.PII_DIRECT

            spans.append(MaskSpan(entity_text=entity_text, category=category))

        return RedactorOutput(spans=spans)

    def _format_prompt(self, messages: list[dict], window_text: str) -> str:
        """Format prompt for model.

        Args:
            messages: Conversation history
            window_text: Text to extract entities from

        Returns:
            Formatted prompt string
        """
        # TODO: Implement proper prompt formatting
        prompt_parts = []

        # Add conversation history
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            prompt_parts.append(f"{role.capitalize()}: {content}")

        # Add extraction instructions
        prompt_parts.append(
            "\nExtract all PII/sensitive entities from the text. "
            'Output format: MASK "entity" category'
        )
        prompt_parts.append(f"\nWindow text: {window_text}")

        return "\n".join(prompt_parts)

    def apply_masks(self, text: str, output: RedactorOutput) -> str:
        """Apply masks to text (delegates to RedactorOutput.apply_masks()).

        Args:
            text: Original text
            output: RedactorOutput with mask spans

        Returns:
            Text with entities masked
        """
        return output.apply_masks(text, mask_format="[{type}]")
