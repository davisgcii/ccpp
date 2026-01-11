"""Factory for creating LLM backends from configuration.

This module provides a simple factory function to instantiate the appropriate
LLM backend based on configuration dictionaries.
"""

from typing import Optional

from .base import LLMBackend, ModelBackend
from .ollama_backend import OllamaBackend
from .mlx_backend import MLXBackend
from .api_backend import AnthropicBackend, OpenAIBackend
from ccpp.types import ApprovedModel


def create_backend_from_config(config: dict) -> LLMBackend:
    """Create LLM backend from configuration dictionary.

    Args:
        config: Configuration dict with required keys:
            - backend: "ollama" | "anthropic" | "openai"
            - model_name: Model identifier
            - Additional backend-specific parameters (optional):
                - For Ollama: host, timeout
                - For Anthropic: api_key
                - For OpenAI: api_key

    Returns:
        Initialized LLMBackend instance

    Raises:
        ValueError: If backend type is unknown or required parameters missing

    Examples:
        ```python
        # Ollama backend
        config = {
            "backend": "ollama",
            "model_name": ApprovedModel.QWEN3_1_7B.value,
            "host": "http://localhost:11434",
            "timeout": 60,
        }
        backend = create_backend_from_config(config)

        # Anthropic backend
        config = {
            "backend": "anthropic",
            "model_name": ApprovedModel.CLAUDE_HAIKU_4_5.value,
            # api_key will be read from ANTHROPIC_API_KEY env var
        }
        backend = create_backend_from_config(config)

        # OpenAI backend
        config = {
            "backend": "openai",
            "model_name": ApprovedModel.GPT_5_MINI.value,
            # api_key will be read from OPENAI_API_KEY env var
        }
        backend = create_backend_from_config(config)
        ```
    """
    if "backend" not in config:
        raise ValueError("config must contain 'backend' key")

    backend_type_str = config["backend"]
    try:
        backend_type = ModelBackend(backend_type_str)
    except ValueError:
        raise ValueError(
            f"Unknown backend: {backend_type_str}. "
            f"Must be one of: {[b.value for b in ModelBackend]}"
        )

    # Route to appropriate backend
    if backend_type == ModelBackend.OLLAMA:
        return _create_ollama_backend(config)
    elif backend_type == ModelBackend.MLX:
        return _create_mlx_backend(config)
    elif backend_type == ModelBackend.ANTHROPIC:
        return _create_anthropic_backend(config)
    elif backend_type == ModelBackend.OPENAI:
        return _create_openai_backend(config)
    else:
        raise ValueError(f"Unsupported backend: {backend_type}")


def _create_ollama_backend(config: dict) -> OllamaBackend:
    """Create Ollama backend from config.

    Args:
        config: Configuration dict

    Returns:
        OllamaBackend instance

    Raises:
        ValueError: If model_name missing
    """
    if "model_name" not in config:
        raise ValueError("Ollama backend requires 'model_name' in config")

    return OllamaBackend(
        model_name=config["model_name"],
        host=config.get("host"),  # Optional: None uses Ollama default
        timeout=config.get("timeout", 60),
    )


def _create_mlx_backend(config: dict) -> MLXBackend:
    """Create MLX backend from config.

    Args:
        config: Configuration dict

    Returns:
        MLXBackend instance

    Raises:
        ValueError: If model_name missing
    """
    if "model_name" not in config:
        raise ValueError("MLX backend requires 'model_name' in config")

    return MLXBackend(
        model_name=config["model_name"],
        quantized=config.get("quantized", True),  # Default to 8-bit quantized
    )


def _create_anthropic_backend(config: dict) -> AnthropicBackend:
    """Create Anthropic backend from config.

    Args:
        config: Configuration dict

    Returns:
        AnthropicBackend instance

    Raises:
        ValueError: If API key not provided
    """
    return AnthropicBackend(
        model_name=config.get("model_name", ApprovedModel.CLAUDE_HAIKU_4_5.value),
        api_key=config.get("api_key"),  # Optional: None uses env var
    )


def _create_openai_backend(config: dict) -> OpenAIBackend:
    """Create OpenAI backend from config.

    Args:
        config: Configuration dict

    Returns:
        OpenAIBackend instance

    Raises:
        ValueError: If API key not provided
    """
    return OpenAIBackend(
        model_name=config.get("model_name", ApprovedModel.GPT_5_MINI.value),
        api_key=config.get("api_key"),  # Optional: None uses env var
    )
