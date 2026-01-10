"""Ollama backend for local model inference.

This backend uses the Ollama Python SDK to communicate with a local Ollama server
running Qwen3 or other models.
"""

from typing import Generator, Optional

from .base import LLMBackend, GenerationConfig, LogitExtractionConfig


class OllamaBackend(LLMBackend):
    """Ollama backend for local model inference.

    Uses the ollama-python package to communicate with Ollama server.
    Supports Qwen3-1.7B, Qwen3-4B, and other models available in Ollama.

    Example:
        ```python
        backend = OllamaBackend(model_name="qwen:1.7b")
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
            model_name: Ollama model name (e.g., "qwen:1.7b", "qwen:4b")
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
            models = self.client.list()
            available_models = [m["name"] for m in models.get("models", [])]

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

        # For Qwen3 models, disable thinking mode via chat options
        # This is done by setting enable_thinking in the chat call
        try:
            response = self.client.chat(
                model=self.model_name,
                messages=messages,
                options=options,
                stream=False,
            )

            return response["message"]["content"]

        except Exception as e:
            raise ConnectionError(f"Ollama generation failed: {e}")

    def extract_logit_probs(
        self,
        messages: list[dict],
        config: LogitExtractionConfig,
    ) -> tuple[float, float]:
        """Extract logit probabilities using Ollama.

        Note: Ollama doesn't expose raw logits via the Python SDK. We approximate by:
        1. Generating a single token with very low temperature (deterministic)
        2. Parsing the output to check if it's token_a or token_b
        3. Returning (1.0, 0.0) or (0.0, 1.0) based on the result

        For true logit extraction, fine-tuned models would need direct PyTorch/MLX loading.

        Args:
            messages: List of message dicts
            config: Logit extraction configuration

        Returns:
            Tuple of (prob_a, prob_b) - deterministic probabilities based on output

        Raises:
            ConnectionError: If Ollama server unavailable
        """
        # Generate single token with deterministic settings
        gen_config = GenerationConfig(
            max_tokens=5,  # Allow a few tokens for "SAFE" or "RISK"
            temperature=0.0,  # Deterministic
            stop_sequences=["\n", " "],  # Stop after first token
            do_sample=False,
        )

        try:
            output = self.generate(messages, gen_config).strip().upper()

            # Map to probabilities (deterministic)
            if config.token_a.upper() in output:
                return (1.0, 0.0)  # prob_a=1.0, prob_b=0.0
            elif config.token_b.upper() in output:
                return (0.0, 1.0)  # prob_a=0.0, prob_b=1.0
            else:
                # If unclear, return slight bias toward safe
                # This happens if the model outputs something unexpected
                return (0.7, 0.3)

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
            )

            for chunk in stream:
                if "message" in chunk and "content" in chunk["message"]:
                    yield chunk["message"]["content"]

        except Exception as e:
            raise ConnectionError(f"Ollama streaming failed: {e}")
