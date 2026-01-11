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
        if len(token_ids) != 1:
            raise ValueError(
                f"Token '{token_str}' must be a single token, got IDs {token_ids}"
            )

        # Use the first token ID
        token_id = token_ids[0]
        decoded = self.tokenizer.decode([token_id])
        if decoded != token_str:
            raise ValueError(
                f"Token '{token_str}' decodes to '{decoded}', expected exact match (no leading space)"
            )
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
        import logging
        logger = logging.getLogger(__name__)
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler
        from ccpp.llm.prompt_logger import log_prompt_event

        # Apply chat template
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=config.enable_thinking,
        )
        logger.debug("[MLX GENERATE] prompt_len=%d prompt_tail=%r", len(prompt), prompt[-200:])

        # Create sampler with temperature/top_p
        sampler_kwargs = {
            "temp": config.temperature,
            "top_p": config.top_p,
        }
        if config.top_k is not None:
            sampler_kwargs["top_k"] = config.top_k
        if config.min_p is not None:
            sampler_kwargs["min_p"] = config.min_p
        if not config.do_sample:
            sampler_kwargs["temp"] = 0.0
            sampler_kwargs["top_p"] = 1.0
            sampler_kwargs.pop("top_k", None)
            sampler_kwargs.pop("min_p", None)

        sampler = make_sampler(**sampler_kwargs)

        # Generate
        response = generate(
            self.model,
            self.tokenizer,
            prompt=prompt,
            max_tokens=config.max_tokens,
            sampler=sampler,
            verbose=False,
        )

        log_prompt_event(
            {
                "backend": "mlx",
                "kind": "generate",
                "model": self.model_name,
                "prompt": prompt,
                "response": response,
                "config": {
                    "max_tokens": config.max_tokens,
                    "temperature": config.temperature,
                    "top_p": config.top_p,
                    "top_k": config.top_k,
                    "min_p": config.min_p,
                    "do_sample": config.do_sample,
                    "enable_thinking": config.enable_thinking,
                },
            }
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
        from ccpp.llm.prompt_logger import log_prompt_event

        # Apply chat template
        # NOTE: With enable_thinking=False, Qwen3 adds <think>\n\n</think> scaffold
        # This empty scaffold signals "no thinking" to the model - we keep it intact
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=config.enable_thinking,
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
        top_id = int(mx.argmax(last_logits).item())
        top_token = self.tokenizer.decode([top_id])
        top_logit = float(last_logits[top_id])
        logger.info("  Top-1 token: id=%d token=%r logit=%.3f", top_id, top_token, top_logit)

        # Get token IDs for "SAFE" and "RISK"
        try:
            token_a_id = self._get_token_id(config.token_a)
            token_b_id = self._get_token_id(config.token_b)

            logger.debug("[MLX LOGIT EXTRACTION] Token A: %r id=%d, Token B: %r id=%d", config.token_a, token_a_id, config.token_b, token_b_id)

        except ValueError as e:
            logger.error(f"[MLX] Token not found: {e}")
            # Fallback to safe default
            return (0.5, 0.5)

        # Extract logits for these specific tokens
        logit_a = float(last_logits[token_a_id])
        logit_b = float(last_logits[token_b_id])

        logger.info(
            "  Raw logits: %s=%.3f, %s=%.3f, delta=%+.3f",
            config.token_a,
            logit_a,
            config.token_b,
            logit_b,
            logit_b - logit_a,
        )
        if logger.isEnabledFor(logging.INFO):
            logits_np = np.array(last_logits.tolist(), dtype=np.float32)
            top_k = 5
            top_indices = np.argpartition(logits_np, -top_k)[-top_k:]
            top_indices = top_indices[np.argsort(logits_np[top_indices])[::-1]]
            for idx in top_indices:
                token = self.tokenizer.decode([int(idx)])
                logger.info("  Top-%d token: id=%d token=%r logit=%.3f", top_k, int(idx), token, float(logits_np[idx]))
        if logger.isEnabledFor(logging.DEBUG):
            candidate_tokens = [config.token_a, config.token_b, "PASS", "YES", "NO", f" {config.token_a}", f" {config.token_b}"]
            for token in candidate_tokens:
                token_ids = self.tokenizer.encode(token, add_special_tokens=False)
                if len(token_ids) != 1:
                    continue
                token_id = token_ids[0]
                token_logit = float(last_logits[token_id])
                logger.debug("  Token %r logit=%.3f", token, token_logit)

        # Apply softmax to get calibrated probabilities
        # softmax([a, b]) = [exp(a), exp(b)] / (exp(a) + exp(b))
        max_logit = max(logit_a, logit_b)
        exp_a = np.exp(logit_a - max_logit)
        exp_b = np.exp(logit_b - max_logit)
        total = exp_a + exp_b

        prob_a = exp_a / total
        prob_b = exp_b / total

        logger.info(f"  Softmax probs: P({config.token_a})={prob_a:.3f}, P({config.token_b})={prob_b:.3f}")
        logger.info(f"  Final: P({config.token_b})={prob_b:.3f} (RISK score)")

        log_prompt_event({
            "backend": "mlx",
            "kind": "logit_probs",
            "model": self.model_name,
            "prompt": prompt,
            "response": {
                "token_a": config.token_a,
                "token_b": config.token_b,
                "prob_a": prob_a,
                "prob_b": prob_b,
            },
        })

        return (prob_a, prob_b)

    def extract_logit_data(
        self,
        messages: list[dict],
        config: LogitExtractionConfig,
    ) -> tuple[float, float, float, float]:
        """Extract probabilities and raw logits for binary classification.

        Returns:
            Tuple of (prob_a, prob_b, logit_a, logit_b)
        """
        import logging
        logger = logging.getLogger(__name__)

        # Apply chat template
        # NOTE: With enable_thinking=False, Qwen3 adds <think>\n\n</think> scaffold
        # This empty scaffold signals "no thinking" to the model - we keep it intact
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=config.enable_thinking,
        )

        # Tokenize input
        input_ids = self.tokenizer.encode(prompt, add_special_tokens=False)
        input_ids = mx.array([input_ids])

        # Run forward pass to get logits
        logits = self.model(input_ids)
        last_logits = logits[0, -1, :]

        try:
            token_a_id = self._get_token_id(config.token_a)
            token_b_id = self._get_token_id(config.token_b)
        except ValueError as e:
            logger.error(f"[MLX] Token not found: {e}")
            return (0.5, 0.5, 0.0, 0.0)

        logit_a = float(last_logits[token_a_id])
        logit_b = float(last_logits[token_b_id])

        max_logit = max(logit_a, logit_b)
        exp_a = np.exp(logit_a - max_logit)
        exp_b = np.exp(logit_b - max_logit)
        total = exp_a + exp_b
        prob_a = exp_a / total
        prob_b = exp_b / total

        return (prob_a, prob_b, logit_a, logit_b)

    def extract_sequence_probs(
        self,
        messages: list[dict],
        config: LogitExtractionConfig,
    ) -> tuple[float, float]:
        """Extract calibrated probabilities using sequence log-likelihood with prefilling.

        Uses a single batched forward pass for efficiency:
        1. Builds both sequences (with "SAFE" and "FAIL" responses)
        2. Pads to same length and batches them
        3. Single forward pass through the model
        4. Extracts log-probabilities and normalizes

        This bypasses the <think> token issue entirely by computing
        P(assistant says "SAFE") vs P(assistant says "FAIL").

        Args:
            messages: List of message dicts
            config: Logit extraction configuration (uses token_a, token_b)

        Returns:
            Tuple of (prob_a, prob_b) - calibrated probabilities in [0, 1]
        """
        import logging
        logger = logging.getLogger(__name__)
        from ccpp.llm.prompt_logger import log_prompt_event

        # Build both sequences with assistant responses
        messages_a = messages + [{"role": "assistant", "content": config.token_a}]
        messages_b = messages + [{"role": "assistant", "content": config.token_b}]

        text_a = self.tokenizer.apply_chat_template(
            messages_a, tokenize=False, add_generation_prompt=False
        )
        text_b = self.tokenizer.apply_chat_template(
            messages_b, tokenize=False, add_generation_prompt=False
        )

        ids_a = self.tokenizer.encode(text_a, add_special_tokens=False)
        ids_b = self.tokenizer.encode(text_b, add_special_tokens=False)

        # Get response token IDs
        token_a_ids = self.tokenizer.encode(config.token_a, add_special_tokens=False)
        token_b_ids = self.tokenizer.encode(config.token_b, add_special_tokens=False)

        if len(token_a_ids) != 1 or len(token_b_ids) != 1:
            logger.warning(
                "[MLX] Tokens should be single tokens: %s=%d, %s=%d",
                config.token_a, len(token_a_ids),
                config.token_b, len(token_b_ids)
            )

        token_a_id = token_a_ids[0]
        token_b_id = token_b_ids[0]

        # Find response token positions (searching from end)
        pos_a = None
        for i in range(len(ids_a) - 1, -1, -1):
            if ids_a[i] == token_a_id:
                pos_a = i
                break

        pos_b = None
        for i in range(len(ids_b) - 1, -1, -1):
            if ids_b[i] == token_b_id:
                pos_b = i
                break

        if pos_a is None or pos_b is None:
            logger.warning(
                "[MLX] Could not find response tokens: pos_a=%s, pos_b=%s",
                pos_a, pos_b
            )
            return (0.5, 0.5)

        # Pad sequences to same length for batching
        max_len = max(len(ids_a), len(ids_b))
        pad_id = getattr(self.tokenizer, 'pad_token_id', None) or 0

        padded_a = ids_a + [pad_id] * (max_len - len(ids_a))
        padded_b = ids_b + [pad_id] * (max_len - len(ids_b))

        # Single batched forward pass
        input_ids = mx.array([padded_a, padded_b])
        logits = self.model(input_ids)

        # Extract log-probabilities at response positions
        # Logit at position (pos - 1) predicts token at pos
        idx_a = pos_a - 1
        idx_b = pos_b - 1

        if idx_a < 0 or idx_b < 0:
            logger.warning("[MLX] Response at position 0, cannot compute logprob")
            return (0.5, 0.5)

        token_logits_a = logits[0, idx_a, :]
        token_logits_b = logits[1, idx_b, :]

        logprob_a = float(token_logits_a[token_a_id] - mx.logsumexp(token_logits_a))
        logprob_b = float(token_logits_b[token_b_id] - mx.logsumexp(token_logits_b))

        logger.info(
            "[MLX PREFILL SEQ PROBS] logprob(%s)=%.3f, logprob(%s)=%.3f, delta=%.3f",
            config.token_a, logprob_a,
            config.token_b, logprob_b,
            logprob_b - logprob_a,
        )

        # Convert log-probs to probabilities via softmax
        max_logprob = max(logprob_a, logprob_b)
        exp_a = np.exp(logprob_a - max_logprob)
        exp_b = np.exp(logprob_b - max_logprob)
        total = exp_a + exp_b

        prob_a = float(exp_a / total)
        prob_b = float(exp_b / total)

        logger.info(
            "[MLX PREFILL SEQ PROBS] P(%s)=%.3f, P(%s)=%.3f",
            config.token_a, prob_a,
            config.token_b, prob_b,
        )

        # Build prompt for logging
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )

        log_prompt_event({
            "backend": "mlx",
            "kind": "prefill_sequence_probs_batched",
            "model": self.model_name,
            "prompt": prompt,
            "response": {
                "token_a": config.token_a,
                "token_b": config.token_b,
                "logprob_a": logprob_a,
                "logprob_b": logprob_b,
                "prob_a": prob_a,
                "prob_b": prob_b,
            },
        })

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
