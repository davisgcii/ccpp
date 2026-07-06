"""Stage 1 Router: Fast binary classifier for PII detection.

This module provides per-token risk scoring using logit-based classification.
For mock mode, returns random scores. In production, uses MLX backend to
extract P(FAIL) from SAFE/FAIL token logits.
"""

import random
from typing import Optional

from ccpp.types import RiskScore
from ccpp.llm.base import LLMBackend, GenerationConfig, LogitExtractionConfig
from ccpp.llm.factory import create_backend_from_config


class Stage1Router:
    """Stage 1: Lightweight PII risk classifier.

    Mock implementation returns heuristic-based scores for development/testing.
    Real implementation uses MLX backend with Qwen3 to extract P(FAIL) from
    SAFE/FAIL token logits via sequence log-likelihood.
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
        self.prompt_template = ""  # Single template with {context} and {current_buffer}
        self.logit_config = LogitExtractionConfig()
        self.calibration_enabled = False
        self.calibration_delta = None
        self.diagnostic_prompt_mode = "full"
        self.sequence_loglikelihood_enabled = False

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
            config: Configuration dict with a prompt_template plus logit
                    extraction / calibration / sequence-loglikelihood settings.
        """
        # Load prompt template (the whole prompt)
        self.prompt_template = config.get("prompt_template", "")

        # Load logit extraction config
        logit_cfg = config.get("logit_extraction", {})
        generation_cfg = config.get("generation", {})
        enable_thinking = generation_cfg.get("enable_thinking", config.get("enable_thinking", False))
        self.logit_config = LogitExtractionConfig(
            token_a=logit_cfg.get("token_a", "SAFE"),
            token_b=logit_cfg.get("token_b", "FAIL"),
            enable_thinking=enable_thinking,
        )

        calibration_cfg = config.get("calibration", {})
        self.calibration_enabled = calibration_cfg.get("enabled", False)
        self.calibration_context = calibration_cfg.get("context", [])
        self.calibration_buffer = calibration_cfg.get("current_buffer", "Hello.")
        self.diagnostic_prompt_mode = config.get("diagnostic_prompt_mode", "full")

        # Sequence log-likelihood mode
        seq_ll_cfg = config.get("sequence_loglikelihood", {})
        self.sequence_loglikelihood_enabled = seq_ll_cfg.get("enabled", False)

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

        # Build the classification prompt from the template
        prompt_messages = self._build_prompt(messages, current_text)

        # Consolidated debug log for prompt construction
        logger.debug(
            f"[Stage1] prompt: template={bool(self.prompt_template)} "
            f"msgs={len(prompt_messages)}"
        )

        # Sequence log-likelihood mode: compute P(SAFE) vs P(FAIL) as full sequences
        # This bypasses the <think> token bias issue in Qwen3
        if self.sequence_loglikelihood_enabled and hasattr(self.backend, "extract_sequence_probs"):
            prob_safe, prob_risk = self.backend.extract_sequence_probs(
                prompt_messages,
                self.logit_config,
            )
            return RiskScore(score=prob_risk, top_category=None)

        # Extract logit probabilities (and optional diagnostics)
        if self.diagnostic_prompt_mode in ("minimal", "both") and hasattr(self.backend, "extract_logit_data"):
            minimal_messages = [{
                "role": "user",
                "content": (
                    "Classify the CURRENT BUFFER only. "
                    "Reply with SAFE or FAIL.\n\n"
                    f"Current buffer:\n{current_text}\n\n"
                    "Answer:"
                ),
            }]
            _, _, min_a, min_b = self.backend.extract_logit_data(
                minimal_messages,
                self.logit_config,
            )
            logger.info("[Stage1] Minimal prompt delta: %.3f", min_b - min_a)
            if self.diagnostic_prompt_mode == "minimal":
                prob_safe, prob_risk = self.backend.extract_logit_probs(
                    minimal_messages,
                    self.logit_config,
                )
                return RiskScore(score=prob_risk, top_category=None)

        if self.diagnostic_prompt_mode == "both" and hasattr(self.backend, "extract_logit_data"):
            _, _, full_a, full_b = self.backend.extract_logit_data(
                prompt_messages,
                self.logit_config,
            )
            logger.info("[Stage1] Full prompt delta: %.3f", full_b - full_a)

        if self.calibration_enabled and hasattr(self.backend, "extract_logit_data"):
            if self.calibration_delta is None:
                baseline_messages = self._build_prompt(
                    self.calibration_context,
                    self.calibration_buffer,
                )
                _, _, base_a, base_b = self.backend.extract_logit_data(
                    baseline_messages,
                    self.logit_config,
                )
                self.calibration_delta = base_b - base_a
                logger.info(
                    "[Stage1] Calibration delta initialized: %.3f",
                    self.calibration_delta,
                )

            _, _, logit_a, logit_b = self.backend.extract_logit_data(
                prompt_messages,
                self.logit_config,
            )
            adjusted_delta = (logit_b - logit_a) - float(self.calibration_delta or 0.0)
            prob_risk = 1.0 / (1.0 + pow(2.718281828459045, -adjusted_delta))
            prob_safe = 1.0 - prob_risk
            logger.info(
                "[Stage1] Adjusted delta: %.3f (raw delta: %.3f)",
                adjusted_delta,
                logit_b - logit_a,
            )
        else:
            prob_safe, prob_risk = self.backend.extract_logit_probs(
                prompt_messages,
                self.logit_config,
            )

        return RiskScore(score=prob_risk, top_category=None)

    def _build_prompt(
        self,
        messages: list[dict],
        current_text: str
    ) -> list[dict]:
        """Build the classification prompt as a list of chat messages.

        Uses the configured ``prompt_template`` (the production path). If no
        template is set, falls back to a single self-contained query built from
        the conversation context and current buffer.

        Args:
            messages: Conversation history
            current_text: Current buffer text

        Returns:
            List of message dicts ready for LLM backend
        """
        context = self._format_context(messages)

        if self.prompt_template:
            formatted_prompt = self.prompt_template.format(
                context=context,
                current_buffer=current_text,
            )
            return [{"role": "user", "content": formatted_prompt}]

        # Fallback: a single query without few-shot examples.
        return [{
            "role": "user",
            "content": self._format_classification_query(context, current_text),
        }]

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

