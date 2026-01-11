"""MLX backend for local model inference with true logit extraction.

This backend uses MLX (Apple Silicon ML framework) to load Qwen3 models locally
and extract calibrated probabilities from raw logits, not just text generation.

Key difference from Ollama backend:
- Ollama: Generates text, parses "SAFE"/"RISK", returns binary 0.0/1.0
- MLX: Extracts raw logits, applies softmax, returns calibrated 0.0-1.0 probabilities
"""

from typing import Generator, Optional
import mlx.core as mx
import mlx.nn as nn
import numpy as np

from .base import LLMBackend, GenerationConfig, LogitExtractionConfig
from ccpp.types import ApprovedModel


class MLXBackend(LLMBackend):
    """MLX backend for local model inference with true logit extraction.

    Uses mlx_lm to load Qwen3 models and extract calibrated probabilities
    from raw logits for binary classification.

    Example:
        ```python
        backend = MLXBackend(model_name="Qwen/Qwen3-1.7B-MLX-8bit")
        prob_safe, prob_risk = backend.extract_logit_probs(
            [{"role": "user", "content": "Is this PII?"}],
            LogitExtractionConfig(token_a="SAFE", token_b="RISK")
        )
        # Returns calibrated probabilities like (0.73, 0.27)
        ```
    """

    def __init__(
        self,
        model_name: str,
        quantized: bool = True,
    ):
        """Initialize MLX backend.

        Args:
            model_name: HuggingFace model name (e.g., "Qwen/Qwen3-1.7B-MLX-8bit")
            quantized: Whether to use quantized model (8-bit recommended)

        Raises:
            ImportError: If mlx_lm package not installed
            ValueError: If model not found
        """
        try:
            from mlx_lm import load
            from mlx_lm.models.base import BaseModelArgs
        except ImportError:
            raise ImportError(
                "mlx_lm package required. Install with: pip install mlx-lm"
            )

        self.model_name = model_name

        # Load model and tokenizer
        print(f"Loading {model_name}...")
        self.model, self.tokenizer = load(model_name)
        print(f"✓ Model loaded: {model_name}")

        # Cache for token IDs (populated on first use)
        self._token_id_cache = {}

    def _get_token_id(self, token_str: str) -> int:
        """Get token ID for a string, with caching.

        Args:
            token_str: Token string (e.g., "SAFE", "RISK")

        Returns:
            Token ID as integer

        Raises:
            ValueError: If token not found in vocabulary
        """
        if token_str in self._token_id_cache:
            return self._token_id_cache[token_str]

        # Tokenize the string
        token_ids = self.tokenizer.encode(token_str, add_special_tokens=False)

        if not token_ids:
            raise ValueError(f"Token '{token_str}' not found in vocabulary")

        # Use the first token ID
        token_id = token_ids[0]
        self._token_id_cache[token_str] = token_id

        return token_id

    def generate(
        self,
        messages: list[dict],
        config: GenerationConfig,
    ) -> str:
        """Generate text using MLX.

        Args:
            messages: List of message dicts with {"role": ..., "content": ...}
            config: Generation configuration

        Returns:
            Generated text string
        """
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler

        # Apply chat template
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,  # Disable thinking for classification
        )

        # Create sampler with temperature/top_p
        sampler = make_sampler(temp=config.temperature, top_p=config.top_p)

        # Generate
        response = generate(
            self.model,
            self.tokenizer,
            prompt=prompt,
            max_tokens=config.max_tokens,
            sampler=sampler,
            verbose=False,
        )

        return response

    def extract_logit_probs(
        self,
        messages: list[dict],
        config: LogitExtractionConfig,
    ) -> tuple[float, float]:
        """Extract calibrated probabilities from raw logits.

        This is the key difference from Ollama backend: we get actual
        logit values for "SAFE" and "RISK" tokens, then apply softmax
        to get calibrated probabilities.

        Args:
            messages: List of message dicts
            config: Logit extraction configuration

        Returns:
            Tuple of (prob_a, prob_b) - calibrated probabilities in [0, 1]

        Raises:
            ValueError: If tokens not found in vocabulary
        """
        import logging
        logger = logging.getLogger(__name__)

        # Apply chat template
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,  # Disable thinking for classification
        )

        # Tokenize input
        input_ids = self.tokenizer.encode(prompt, add_special_tokens=False)
        input_ids = mx.array([input_ids])  # Add batch dimension

        # Run forward pass to get logits
        # Shape: [batch_size, sequence_length, vocab_size]
        logits = self.model(input_ids)

        # Get logits at the last position (next token prediction)
        # Shape: [vocab_size]
        last_logits = logits[0, -1, :]

        # Get token IDs for "SAFE" and "RISK"
        try:
            token_a_id = self._get_token_id(config.token_a)
            token_b_id = self._get_token_id(config.token_b)

            logger.debug(f"[MLX] Token IDs: {config.token_a}={token_a_id}, {config.token_b}={token_b_id}")
        except ValueError as e:
            logger.error(f"[MLX] Token not found: {e}")
            # Fallback to safe default
            return (0.9, 0.1)

        # Extract logits for these specific tokens
        logit_a = float(last_logits[token_a_id])
        logit_b = float(last_logits[token_b_id])

        logger.debug(f"[MLX] Raw logits: {config.token_a}={logit_a:.3f}, {config.token_b}={logit_b:.3f}")

        # Apply softmax to get calibrated probabilities
        # softmax([a, b]) = [exp(a), exp(b)] / (exp(a) + exp(b))
        exp_a = np.exp(logit_a)
        exp_b = np.exp(logit_b)
        total = exp_a + exp_b

        prob_a = exp_a / total
        prob_b = exp_b / total

        logger.debug(f"[MLX] Calibrated probs: P({config.token_a})={prob_a:.3f}, P({config.token_b})={prob_b:.3f}")

        return (prob_a, prob_b)

    def stream_generate(
        self,
        messages: list[dict],
        config: GenerationConfig,
    ) -> Generator[str, None, None]:
        """Stream generation using MLX.

        Args:
            messages: List of message dicts
            config: Generation configuration

        Yields:
            Text chunks as they are generated
        """
        # MLX doesn't have built-in streaming in mlx_lm.generate
        # For now, just generate full response and yield it
        response = self.generate(messages, config)
        yield response
