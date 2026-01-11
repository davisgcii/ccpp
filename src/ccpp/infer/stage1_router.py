"""Stage 1 Router: Fast binary classifier for PII detection.

This module provides per-token risk scoring using logit-based classification.
For mock mode, returns random scores. In production, will load a fine-tuned
model and extract P(RISK) from SAFE/RISK token logits.
"""

import random
from typing import Optional

from ccpp.types import RiskScore
from ccpp.llm.base import LLMBackend, GenerationConfig, LogitExtractionConfig
from ccpp.llm.factory import create_backend_from_config


class Stage1Router:
    """Stage 1: Lightweight PII risk classifier.

    Mock implementation returns random scores for development/testing.
    Real implementation will load a fine-tuned model (Qwen2.5-1.5B or similar)
    and extract P(RISK) from logits.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "cuda",
        mock_mode: bool = True,
        llm_config: Optional[dict] = None,
        llm_backend: Optional[LLMBackend] = None,
    ):
        """Initialize Stage 1 router.

        Args:
            model_path: Path to fine-tuned model (for direct loading, future use)
            device: Device to run model on ("cuda" or "cpu")
            mock_mode: If True, return random scores (for development)
            llm_config: LLM harness configuration dict (for Phase 0 base model testing)
            llm_backend: Pre-initialized LLM backend (alternative to llm_config)
        """
        self.mock_mode = mock_mode
        self.device = device
        self.backend = None
        self.prompt_template = ""  # New: single template with {context} and {current_buffer}
        self.few_shot_examples = []  # Legacy: kept for backwards compatibility
        self.system_prompt = ""  # Legacy: kept for backwards compatibility
        self.logit_config = LogitExtractionConfig()

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

        # Load logit extraction config
        logit_cfg = config.get("logit_extraction", {})
        self.logit_config = LogitExtractionConfig(
            token_a=logit_cfg.get("token_a", "SAFE"),
            token_b=logit_cfg.get("token_b", "RISK"),
        )

    def classify(self, messages: list[dict], current_text: str) -> RiskScore:
        """Classify current exchange state for PII risk.

        Args:
            messages: Conversation history (for exchange-aware classification)
            current_text: Current buffer text being evaluated

        Returns:
            RiskScore with P(RISK) ∈ [0, 1]
        """
        if self.mock_mode:
            return self._mock_classify(messages, current_text)
        else:
            return self._real_classify(messages, current_text)

    def _mock_classify(self, messages: list[dict], current_text: str) -> RiskScore:
        """Mock classification with heuristic-based scoring.

        Returns higher scores for text that looks like PII patterns.
        """
        score = 0.1  # Base score

        text_lower = current_text.lower()

        # Bump score for PII-like patterns
        if "@" in current_text:
            score += 0.3
        if any(word in text_lower for word in ["email", "phone", "name", "address"]):
            score += 0.2
        if any(char.isdigit() for char in current_text):
            # Has numbers
            digit_ratio = sum(c.isdigit() for c in current_text) / max(len(current_text), 1)
            if digit_ratio > 0.3:  # >30% digits
                score += 0.3

        # Add some randomness
        score += random.uniform(-0.1, 0.1)

        # Clamp to [0, 1]
        score = max(0.0, min(1.0, score))

        return RiskScore(score=score, top_category=None)

    def _real_classify(self, messages: list[dict], current_text: str) -> RiskScore:
        """Real classification using LLM backend.

        Uses logit-based classification via the LLM harness:
        1. Format prompt with few-shot examples + conversation + current_text
        2. Extract logit probabilities via backend
        3. Return RiskScore with P(RISK)

        Args:
            messages: Conversation history
            current_text: Current buffer text

        Returns:
            RiskScore with P(RISK) probability
        """
        import logging
        logger = logging.getLogger(__name__)

        # Format prompt with few-shot examples
        prompt_messages = self._format_prompt_with_few_shot(messages, current_text)

        # Debug: Log prompt construction
        logger.debug(f"[Stage1] few_shot_examples count: {len(self.few_shot_examples)}")
        logger.debug(f"[Stage1] system_prompt length: {len(self.system_prompt)}")
        logger.debug(f"[Stage1] prompt_messages count: {len(prompt_messages)}")
        if len(prompt_messages) > 0:
            logger.debug(f"[Stage1] First message role: {prompt_messages[0].get('role', 'N/A')}")
            logger.debug(f"[Stage1] First message preview: {prompt_messages[0].get('content', '')[:100]}")

        # Extract logit probabilities
        prob_safe, prob_risk = self.backend.extract_logit_probs(
            prompt_messages,
            self.logit_config,
        )

        return RiskScore(score=prob_risk, top_category=None)

    def _format_prompt_with_few_shot(
        self,
        messages: list[dict],
        current_text: str
    ) -> list[dict]:
        """Format prompt for classification.

        Uses one of two modes:
        1. Template mode (preferred): Uses prompt_template with {context} and {current_buffer}
        2. Legacy mode: Constructs prompt from system_prompt + few_shot_examples

        Args:
            messages: Conversation history
            current_text: Current buffer text

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
                current_buffer=current_text,
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
            # Format example context
            example_messages = example.get("messages", [])
            example_context = self._format_context(example_messages)
            example_buffer = example.get("current_buffer", "")
            example_label = example.get("label", "SAFE")

            # User message: context + current buffer
            prompt.append({
                "role": "user",
                "content": self._format_classification_query(example_context, example_buffer),
            })

            # Assistant response: label
            prompt.append({
                "role": "assistant",
                "content": example_label,
            })

        # Add actual query
        prompt.append({
            "role": "user",
            "content": self._format_classification_query(actual_context, current_text),
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

    def _format_classification_query(self, context: str, current_buffer: str) -> str:
        """Format classification query with clear markdown sections.

        Args:
            context: Formatted conversation context
            current_buffer: Current buffer text

        Returns:
            Formatted query string with clear delineation
        """
        return f"""---
## Conversation Context
{context}

---
## Current Buffer (CLASSIFY THIS)
```
{current_buffer}
```
---"""

    def _format_prompt(self, messages: list[dict], current_text: str) -> str:
        """Format prompt for model (exchange-aware).

        Args:
            messages: Conversation history
            current_text: Current buffer text

        Returns:
            Formatted prompt string
        """
        # TODO: Implement proper prompt formatting for your model
        # This will depend on the model's chat template
        prompt_parts = []

        # Add conversation history
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            prompt_parts.append(f"{role.capitalize()}: {content}")

        # Add current text (partial assistant response)
        if current_text:
            prompt_parts.append(f"Assistant: {current_text}")

        # Add classification question
        prompt_parts.append(
            "\nDoes the assistant response contain or is likely to contain PII/sensitive information?"
        )

        return "\n".join(prompt_parts)
