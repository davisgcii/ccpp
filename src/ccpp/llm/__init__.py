"""LLM backend abstraction layer for CC++ PII masking.

This package provides a unified interface for different LLM backends:
- Ollama (local models)
- Anthropic (Claude API)
- OpenAI (GPT API)

Usage:
    ```python
    from ccpp.llm import create_backend_from_config, GenerationConfig

    config = {"backend": "ollama", "model_name": "qwen:1.7b"}
    backend = create_backend_from_config(config)

    result = backend.generate(
        [{"role": "user", "content": "Hello"}],
        GenerationConfig(max_tokens=10)
    )
    ```
"""

from .base import (
    LLMBackend,
    ModelBackend,
    GenerationConfig,
    LogitExtractionConfig,
)
from .factory import create_backend_from_config
from .ollama_backend import OllamaBackend
from .api_backend import AnthropicBackend, OpenAIBackend

__all__ = [
    # Base classes
    "LLMBackend",
    "ModelBackend",
    "GenerationConfig",
    "LogitExtractionConfig",
    # Factory
    "create_backend_from_config",
    # Backends
    "OllamaBackend",
    "AnthropicBackend",
    "OpenAIBackend",
]
