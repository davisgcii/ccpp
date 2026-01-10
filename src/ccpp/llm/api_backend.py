"""API backends for cloud-based LLM services.

This module provides backends for Anthropic (Claude) and OpenAI (GPT) APIs.
"""

import os
from typing import Generator, Optional

from .base import LLMBackend, GenerationConfig, LogitExtractionConfig


class AnthropicBackend(LLMBackend):
    """Anthropic API backend (Claude models).

    Uses the Anthropic Python SDK to communicate with Claude models via API.

    Example:
        ```python
        backend = AnthropicBackend(model_name="claude-3-5-haiku-20241022")
        result = backend.generate(
            [{"role": "user", "content": "Hello"}],
            GenerationConfig(max_tokens=10)
        )
        ```
    """

    def __init__(
        self,
        model_name: str = "claude-3-5-haiku-20241022",
        api_key: Optional[str] = None,
    ):
        """Initialize Anthropic backend.

        Args:
            model_name: Claude model name
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)

        Raises:
            ImportError: If anthropic package not installed
            ValueError: If API key not provided
        """
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "anthropic package required. Install with: uv pip install anthropic"
            )

        self.model_name = model_name

        # Get API key from parameter or environment
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.client = anthropic.Anthropic(api_key=api_key)

    def generate(
        self,
        messages: list[dict],
        config: GenerationConfig,
    ) -> str:
        """Generate text using Claude.

        Args:
            messages: List of message dicts with {"role": ..., "content": ...}
            config: Generation configuration

        Returns:
            Generated text string

        Raises:
            Exception: If API call fails
        """
        try:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                top_p=config.top_p,
                stop_sequences=config.stop_sequences or [],
                messages=messages,
            )

            return response.content[0].text

        except Exception as e:
            raise Exception(f"Anthropic API call failed: {e}")

    def extract_logit_probs(
        self,
        messages: list[dict],
        config: LogitExtractionConfig,
    ) -> tuple[float, float]:
        """Extract logit probabilities.

        Note: Claude doesn't expose raw logits. We approximate by:
        1. Generating a single token with temperature=0
        2. Parsing the output
        3. Returning deterministic probabilities

        Args:
            messages: List of message dicts
            config: Logit extraction configuration

        Returns:
            Tuple of (prob_a, prob_b)

        Raises:
            Exception: If API call fails
        """
        gen_config = GenerationConfig(
            max_tokens=5,
            temperature=0.0,
            stop_sequences=["\n", " "],
        )

        try:
            output = self.generate(messages, gen_config).strip().upper()

            if config.token_a.upper() in output:
                return (1.0, 0.0)
            elif config.token_b.upper() in output:
                return (0.0, 1.0)
            else:
                return (0.7, 0.3)

        except Exception as e:
            raise Exception(f"Anthropic logit extraction failed: {e}")

    def stream_generate(
        self,
        messages: list[dict],
        config: GenerationConfig,
    ) -> Generator[str, None, None]:
        """Stream generation using Claude.

        Args:
            messages: List of message dicts
            config: Generation configuration

        Yields:
            Text chunks as they are generated

        Raises:
            Exception: If API call fails
        """
        try:
            with self.client.messages.stream(
                model=self.model_name,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                top_p=config.top_p,
                stop_sequences=config.stop_sequences or [],
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield text

        except Exception as e:
            raise Exception(f"Anthropic streaming failed: {e}")


class OpenAIBackend(LLMBackend):
    """OpenAI API backend (GPT models).

    Uses the OpenAI Python SDK to communicate with GPT models via API.

    Example:
        ```python
        backend = OpenAIBackend(model_name="gpt-4o-mini")
        result = backend.generate(
            [{"role": "user", "content": "Hello"}],
            GenerationConfig(max_tokens=10)
        )
        ```
    """

    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
    ):
        """Initialize OpenAI backend.

        Args:
            model_name: GPT model name
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)

        Raises:
            ImportError: If openai package not installed
            ValueError: If API key not provided
        """
        try:
            import openai
        except ImportError:
            raise ImportError(
                "openai package required. Install with: uv pip install openai"
            )

        self.model_name = model_name

        # Get API key from parameter or environment
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.client = openai.OpenAI(api_key=api_key)

    def generate(
        self,
        messages: list[dict],
        config: GenerationConfig,
    ) -> str:
        """Generate text using GPT.

        Args:
            messages: List of message dicts with {"role": ..., "content": ...}
            config: Generation configuration

        Returns:
            Generated text string

        Raises:
            Exception: If API call fails
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                top_p=config.top_p,
                stop=config.stop_sequences if config.stop_sequences else None,
            )

            return response.choices[0].message.content

        except Exception as e:
            raise Exception(f"OpenAI API call failed: {e}")

    def extract_logit_probs(
        self,
        messages: list[dict],
        config: LogitExtractionConfig,
    ) -> tuple[float, float]:
        """Extract logit probabilities.

        Note: OpenAI doesn't expose raw logits via standard API. We approximate by:
        1. Generating a single token with temperature=0
        2. Parsing the output
        3. Returning deterministic probabilities

        For true logit access, use the logprobs parameter (requires different approach).

        Args:
            messages: List of message dicts
            config: Logit extraction configuration

        Returns:
            Tuple of (prob_a, prob_b)

        Raises:
            Exception: If API call fails
        """
        gen_config = GenerationConfig(
            max_tokens=5,
            temperature=0.0,
            stop_sequences=["\n", " "],
        )

        try:
            output = self.generate(messages, gen_config).strip().upper()

            if config.token_a.upper() in output:
                return (1.0, 0.0)
            elif config.token_b.upper() in output:
                return (0.0, 1.0)
            else:
                return (0.7, 0.3)

        except Exception as e:
            raise Exception(f"OpenAI logit extraction failed: {e}")

    def stream_generate(
        self,
        messages: list[dict],
        config: GenerationConfig,
    ) -> Generator[str, None, None]:
        """Stream generation using GPT.

        Args:
            messages: List of message dicts
            config: Generation configuration

        Yields:
            Text chunks as they are generated

        Raises:
            Exception: If API call fails
        """
        try:
            stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                top_p=config.top_p,
                stop=config.stop_sequences if config.stop_sequences else None,
                stream=True,
            )

            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            raise Exception(f"OpenAI streaming failed: {e}")
