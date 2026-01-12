"""Ollama backend for local model inference.

This backend uses the Ollama Python SDK to communicate with a local Ollama server
running Qwen3 or other models. Supports true logprobs extraction via generate() API.
"""

import logging
import math
from typing import Generator, Optional

from .base import LLMBackend, GenerationConfig, LogitExtractionConfig
from .prompt_logger import log_prompt_event
from ccpp.types import ApprovedModel

logger = logging.getLogger(__name__)


class OllamaBackend(LLMBackend):
    """Ollama backend for local model inference.

    Uses the ollama-python package to communicate with Ollama server.
    Supports Qwen3-1.7B, Qwen3-4B, and other models available in Ollama.

    Example:
        ```python
        backend = OllamaBackend(model_name=ApprovedModel.QWEN3_1_7B.value)
        result = backend.generate(
            [{"role": "user", "content": "Hello"}],
            GenerationConfig(max_tokens=10)
        )
        ```
    """

    def __init__(
        self,
        model_name: str,
        host: Optional[str] = None,
        timeout: int = 60,
    ):
        """Initialize Ollama backend.

        Args:
            model_name: Ollama model name (e.g., ApprovedModel.QWEN3_1_7B.value)
            host: Ollama server host (default: uses Ollama's default)
            timeout: Request timeout in seconds

        Raises:
            ImportError: If ollama package not installed
            ConnectionError: If Ollama server not accessible
        """
        try:
            import ollama
        except ImportError:
            raise ImportError(
                "ollama package required. Install with: uv pip install ollama"
            )

        self.model_name = model_name
        self.timeout = timeout

        # Initialize Ollama client
        if host:
            self.client = ollama.Client(host=host)
        else:
            self.client = ollama.Client()

        # Verify Ollama is running and model is available
        self._check_connection()

    def _check_connection(self):
        """Verify Ollama server is accessible and model is available.

        Raises:
            ConnectionError: If server not accessible
            ValueError: If model not found
        """
        try:
            # List available models
            models_response = self.client.list()

            # Handle Ollama ListResponse object (has .models attribute)
            models = models_response.models if hasattr(models_response, 'models') else []
            available_models = [m.model for m in models if hasattr(m, 'model')]

            # Check if our model is available
            if not any(self.model_name in name for name in available_models):
                raise ValueError(
                    f"Model '{self.model_name}' not found in Ollama. "
                    f"Available models: {available_models}\n"
                    f"Pull the model with: ollama pull {self.model_name}"
                )

        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ConnectionError(
                f"Cannot connect to Ollama server. "
                f"Ensure Ollama is running. Error: {e}"
            )

    def _format_prompt(self, messages: list[dict]) -> str:
        """Format chat messages as a single prompt for generate() API.

        Uses Qwen chat template format (ChatML-style).

        Args:
            messages: List of message dicts with {"role": ..., "content": ...}

        Returns:
            Formatted prompt string
        """
        prompt = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt += f"<|im_start|>system\n{content}<|im_end|>\n"
            elif role == "user":
                prompt += f"<|im_start|>user\n{content}<|im_end|>\n"
            elif role == "assistant":
                prompt += f"<|im_start|>assistant\n{content}<|im_end|>\n"
        # Prime for assistant response
        prompt += "<|im_start|>assistant\n"
        return prompt

    def generate(
        self,
        messages: list[dict],
        config: GenerationConfig,
    ) -> str:
        """Generate text using Ollama.

        Args:
            messages: List of message dicts with {"role": ..., "content": ...}
            config: Generation configuration

        Returns:
            Generated text string

        Raises:
            ConnectionError: If Ollama server unavailable
        """
        # Build options for Ollama
        options = {
            "temperature": config.temperature,
            "top_p": config.top_p,
            "num_predict": config.max_tokens,
        }

        # Add stop sequences if provided
        if config.stop_sequences:
            options["stop"] = config.stop_sequences

        # For Qwen3 models, disable thinking mode to get direct responses
        try:
            response = self.client.chat(
                model=self.model_name,
                messages=messages,
                options=options,
                stream=False,
                think=False,  # Disable thinking mode for Qwen3
            )

            # SDK returns Pydantic objects, not dicts
            return response.message.content

        except Exception as e:
            raise ConnectionError(f"Ollama generation failed: {e}")

    def extract_logit_probs(
        self,
        messages: list[dict],
        config: LogitExtractionConfig,
    ) -> tuple[float, float]:
        """Extract logit probabilities using Ollama's logprobs API.

        Uses Ollama's native logprobs feature (generate API with logprobs=True)
        to get calibrated probabilities for SAFE/FAIL tokens in a single forward pass.

        Args:
            messages: List of message dicts
            config: Logit extraction configuration

        Returns:
            Tuple of (prob_a, prob_b) - calibrated probabilities in [0, 1]

        Raises:
            ConnectionError: If Ollama server unavailable
            ValueError: If logprobs not available or tokens not found in top_logprobs
        """
        # Use the full prompt from the messages
        # The Stage1 template includes few-shot examples that teach the model the format
        user_content = messages[-1].get("content", "") if messages else ""

        # The prompt template ends with "Answer:" - we need the model to output SAFE/FAIL
        # We use think=False to disable Qwen3's thinking mode
        # Without raw=True, Ollama applies its own template, which works with think=False
        prompt = user_content.rstrip()

        # Ensure prompt ends with space after colon to prime for SAFE/FAIL continuation
        if prompt.endswith(":"):
            prompt = prompt + " "

        try:
            # Use generate() with think=False to disable Qwen3 thinking mode
            # Note: Don't use raw=True as it prevents think=False from working
            import time
            start_time = time.time()
            response = self.client.generate(
                model=self.model_name,
                prompt=prompt,
                options={
                    "num_predict": 3,  # Generate a few tokens to ensure logprobs
                    "temperature": 0.0,  # Deterministic
                },
                stream=False,
                think=False,  # Disable thinking mode (Qwen3)
                logprobs=True,  # Enable logprobs
                top_logprobs=20,  # Get top 20 (Ollama max limit)
            )
            latency_ms = int((time.time() - start_time) * 1000)

            # Extract logprobs from response - required, no fallback
            # Note: ollama-python SDK returns Pydantic objects, not dicts
            logprobs_data = getattr(response, "logprobs", None) or []

            if not logprobs_data:
                raise ValueError(
                    "Ollama did not return logprobs. "
                    "Ensure Ollama version supports logprobs (v0.12.11+) and model is compatible."
                )

            # Get top_logprobs for the first generated token
            first_token_data = logprobs_data[0] if logprobs_data else None

            if not first_token_data or not hasattr(first_token_data, "top_logprobs"):
                raise ValueError(
                    f"Ollama response missing top_logprobs. Response: {response}"
                )

            top_logprobs = first_token_data.top_logprobs

            # Search for SAFE and FAIL tokens (case-insensitive, handle spacing)
            safe_logprob = None
            fail_logprob = None
            token_a_upper = config.token_a.strip().upper()
            token_b_upper = config.token_b.strip().upper()

            for t in top_logprobs:
                token_text = t.token.strip().upper()
                if token_text == token_a_upper and safe_logprob is None:
                    safe_logprob = t.logprob
                elif token_text == token_b_upper and fail_logprob is None:
                    fail_logprob = t.logprob

            # Handle missing tokens gracefully
            # If one token is found but not the other, assign a very low probability to the missing one
            # This makes sense: if FAIL isn't in top 20, model strongly believes SAFE, and vice versa
            found_tokens = [t.token for t in top_logprobs[:20]]
            if safe_logprob is None and fail_logprob is None:
                # Neither found - this is an error
                raise ValueError(
                    f"Neither '{config.token_a}' nor '{config.token_b}' found in top_logprobs. "
                    f"Found tokens: {found_tokens}. Model may not support this classification task."
                )
            elif safe_logprob is None:
                # FAIL found, SAFE not - model strongly believes FAIL
                # Use lowest logprob from top_logprobs minus 10 as estimate for SAFE
                min_logprob = min(t.logprob for t in top_logprobs) if top_logprobs else -20.0
                safe_logprob = min_logprob - 10.0
                logger.warning(
                    "[Ollama] Token '%s' not in top 20, using estimate logprob=%.1f. Found: %s",
                    config.token_a, safe_logprob, found_tokens[:5]
                )
            elif fail_logprob is None:
                # SAFE found, FAIL not - model strongly believes SAFE
                # Use lowest logprob from top_logprobs minus 10 as estimate for FAIL
                min_logprob = min(t.logprob for t in top_logprobs) if top_logprobs else -20.0
                fail_logprob = min_logprob - 10.0
                logger.warning(
                    "[Ollama] Token '%s' not in top 20, using estimate logprob=%.1f. Found: %s",
                    config.token_b, fail_logprob, found_tokens[:5]
                )

            # Apply softmax to get calibrated probabilities
            max_lp = max(safe_logprob, fail_logprob)
            exp_safe = math.exp(safe_logprob - max_lp)
            exp_fail = math.exp(fail_logprob - max_lp)
            total = exp_safe + exp_fail

            prob_a = exp_safe / total
            prob_b = exp_fail / total

            logger.info(
                "[Ollama LOGPROBS] logprob(%s)=%.3f, logprob(%s)=%.3f -> P(%s)=%.3f, P(%s)=%.3f",
                config.token_a, safe_logprob,
                config.token_b, fail_logprob,
                config.token_a, prob_a,
                config.token_b, prob_b,
            )

            # Serialize top_logprobs for logging (Pydantic objects -> dicts)
            top_logprobs_serialized = [
                {"token": t.token, "logprob": t.logprob}
                for t in top_logprobs
            ]

            # Get the generated token from first_token_data
            generated_token = first_token_data.token if hasattr(first_token_data, 'token') else None
            generated_logprob = first_token_data.logprob if hasattr(first_token_data, 'logprob') else None

            log_prompt_event({
                "backend": "ollama",
                "kind": "logit_probs",
                "model": self.model_name,
                "prompt": prompt,
                "response": {
                    "generated_token": generated_token,
                    "generated_logprob": generated_logprob,
                    "token_a": config.token_a,
                    "token_b": config.token_b,
                    "logprob_a": safe_logprob,
                    "logprob_b": fail_logprob,
                    "prob_a": prob_a,
                    "prob_b": prob_b,
                    "top_logprobs": top_logprobs_serialized,
                },
                "latency_ms": latency_ms,
            })

            return (prob_a, prob_b)

        except ValueError:
            raise  # Re-raise ValueError as-is
        except Exception as e:
            raise ConnectionError(f"Ollama logit extraction failed: {e}")

    def stream_generate(
        self,
        messages: list[dict],
        config: GenerationConfig,
    ) -> Generator[str, None, None]:
        """Stream generation using Ollama.

        Args:
            messages: List of message dicts
            config: Generation configuration

        Yields:
            Text chunks as they are generated

        Raises:
            ConnectionError: If Ollama server unavailable
        """
        # Build options
        options = {
            "temperature": config.temperature,
            "top_p": config.top_p,
            "num_predict": config.max_tokens,
        }

        if config.stop_sequences:
            options["stop"] = config.stop_sequences

        try:
            stream = self.client.chat(
                model=self.model_name,
                messages=messages,
                options=options,
                stream=True,
                think=False,  # Disable thinking mode for Qwen3
            )

            for chunk in stream:
                # SDK returns Pydantic objects for streaming chunks
                if hasattr(chunk, 'message') and hasattr(chunk.message, 'content'):
                    content = chunk.message.content
                    if content:
                        yield content

        except Exception as e:
            raise ConnectionError(f"Ollama streaming failed: {e}")
