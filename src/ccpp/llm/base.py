"""Base abstractions for LLM backends.

This module provides a unified interface for different LLM backends (local via Ollama,
API via Anthropic/OpenAI, etc.) to support the CC++ PII masking pipeline.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Generator, Optional


class ModelBackend(Enum):
    """Supported model backends."""
    OLLAMA = "ollama"
    MLX = "mlx"  # Local models with true logit extraction (Apple Silicon)
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


@dataclass
class GenerationConfig:
    """Configuration for text generation.

    Attributes:
        max_tokens: Maximum number of tokens to generate
        temperature: Sampling temperature (0.0 = deterministic)
        top_p: Nucleus sampling parameter
        stop_sequences: List of sequences that stop generation
        do_sample: Whether to use sampling (False = greedy decoding)
        enable_thinking: For Qwen3 models, disable thinking mode for simple tasks
    """
    max_tokens: int = 100
    temperature: float = 0.0
    top_p: float = 1.0
    stop_sequences: Optional[list[str]] = None
    do_sample: bool = False
    enable_thinking: bool = False  # Qwen3-specific: disable for classification

    def __post_init__(self):
        if self.stop_sequences is None:
            self.stop_sequences = []


@dataclass
class LogitExtractionConfig:
    """Configuration for logit-based classification.

    For binary classification, we extract probabilities for two tokens
    (e.g., "SAFE" and "RISK") from the model's output logits.

    Attributes:
        token_a: First class token (e.g., "SAFE")
        token_b: Second class token (e.g., "RISK")
    """
    token_a: str = "SAFE"
    token_b: str = "RISK"


class LLMBackend(ABC):
    """Abstract base class for LLM backends.

    This provides a unified interface for different LLM implementations,
    allowing the system to switch between local models (Ollama) and
    API-based models (Anthropic, OpenAI) transparently.
    """

    @abstractmethod
    def generate(
        self,
        messages: list[dict],
        config: GenerationConfig,
    ) -> str:
        """Generate text from messages.

        Args:
            messages: List of message dicts with {"role": ..., "content": ...}
            config: Generation configuration

        Returns:
            Generated text string

        Raises:
            ConnectionError: If backend is unavailable
            ValueError: If input is invalid
        """
        pass

    @abstractmethod
    def extract_logit_probs(
        self,
        messages: list[dict],
        config: LogitExtractionConfig,
    ) -> tuple[float, float]:
        """Extract logit probabilities for binary classification.

        For models that don't expose logits directly (most APIs), this
        uses a workaround: generate a single token and parse the output.

        Args:
            messages: List of message dicts with {"role": ..., "content": ...}
            config: Logit extraction configuration

        Returns:
            Tuple of (prob_a, prob_b) where prob_a + prob_b ≈ 1.0
            For example, (0.3, 0.7) means 30% SAFE, 70% RISK

        Raises:
            ConnectionError: If backend is unavailable
            ValueError: If input is invalid
        """
        pass

    @abstractmethod
    def stream_generate(
        self,
        messages: list[dict],
        config: GenerationConfig,
    ) -> Generator[str, None, None]:
        """Stream generated text token-by-token.

        Args:
            messages: List of message dicts with {"role": ..., "content": ...}
            config: Generation configuration

        Yields:
            Text chunks as they are generated

        Raises:
            ConnectionError: If backend is unavailable
            ValueError: If input is invalid
        """
        pass
