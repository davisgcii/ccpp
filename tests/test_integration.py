"""Integration tests for real LLM backends.

These tests require actual services to be running and are skipped by default.
Run with: pytest -m integration

Prerequisites:
- Ollama: ollama serve + ollama pull qwen3:1.7b
- Anthropic: ANTHROPIC_API_KEY environment variable
- OpenAI: OPENAI_API_KEY environment variable
"""

import os
import pytest
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

from ccpp.llm.ollama_backend import OllamaBackend
from ccpp.llm.api_backend import AnthropicBackend, OpenAIBackend
from ccpp.llm.base import GenerationConfig, LogitExtractionConfig
from ccpp.types import ApprovedModel


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestOllamaIntegration:
    """Integration tests for Ollama backend."""

    @pytest.fixture(scope="class")
    def check_ollama_available(self):
        """Check if Ollama is running and model is available."""
        try:
            import ollama
            client = ollama.Client()
            models_response = client.list()

            # The response is a ListResponse object with a .models attribute
            # Each model has .model, .modified_at, .digest, .size, etc.
            models = models_response.models if hasattr(models_response, 'models') else []

            # Check if any qwen model is available
            available_models = [m.model for m in models if hasattr(m, 'model')]
            has_qwen = any("qwen" in name.lower() for name in available_models)

            if not has_qwen:
                pytest.skip(
                    f"No qwen model found. Available models: {available_models}. "
                    f"Run: ollama pull qwen3:1.7b"
                )
            return True
        except Exception as e:
            pytest.skip(f"Ollama not accessible: {e}")

    def test_ollama_generate_basic(self, check_ollama_available):
        """Test basic text generation with Ollama."""
        backend = OllamaBackend(model_name=ApprovedModel.QWEN3_1_7B.value)

        result = backend.generate(
            messages=[{"role": "user", "content": "Say 'Hello'"}],
            config=GenerationConfig(max_tokens=10, temperature=0.0),
        )

        assert isinstance(result, str)
        assert len(result) > 0
        print(f"✓ Ollama generate: {result}")

    def test_ollama_logit_extraction(self, check_ollama_available):
        """Test logit extraction returns probabilities."""
        backend = OllamaBackend(model_name=ApprovedModel.QWEN3_1_7B.value)

        # Test with safe text
        prob_safe, prob_risk = backend.extract_logit_probs(
            messages=[{"role": "user", "content": "Hello, how are you?"}],
            config=LogitExtractionConfig(token_a="SAFE", token_b="RISK"),
        )

        assert isinstance(prob_safe, float)
        assert isinstance(prob_risk, float)
        assert 0.0 <= prob_safe <= 1.0
        assert 0.0 <= prob_risk <= 1.0
        print(f"✓ Ollama logits: safe={prob_safe}, risk={prob_risk}")

    def test_ollama_streaming(self, check_ollama_available):
        """Test streaming generation."""
        backend = OllamaBackend(model_name=ApprovedModel.QWEN3_1_7B.value)

        chunks = []
        for chunk in backend.stream_generate(
            messages=[{"role": "user", "content": "Count to 3"}],
            config=GenerationConfig(max_tokens=20, temperature=0.0),
        ):
            chunks.append(chunk)

        assert len(chunks) > 0
        full_text = "".join(chunks)
        assert len(full_text) > 0
        print(f"✓ Ollama stream: {len(chunks)} chunks, {len(full_text)} chars")


class TestAnthropicIntegration:
    """Integration tests for Anthropic backend."""

    @pytest.fixture(scope="class")
    def check_anthropic_available(self):
        """Check if Anthropic API key is set."""
        if not os.environ.get("ANTHROPIC_API_KEY"):
            pytest.skip("ANTHROPIC_API_KEY not set. Skipping Anthropic integration tests.")
        return True

    def test_anthropic_generate_basic(self, check_anthropic_available):
        """Test basic text generation with Claude."""
        backend = AnthropicBackend(model_name=ApprovedModel.CLAUDE_HAIKU_4_5.value)

        result = backend.generate(
            messages=[{"role": "user", "content": "Say 'Hello'"}],
            config=GenerationConfig(max_tokens=10, temperature=0.0),
        )

        assert isinstance(result, str)
        assert len(result) > 0
        print(f"✓ Anthropic generate: {result}")

    def test_anthropic_logit_extraction(self, check_anthropic_available):
        """Test logit extraction approximation."""
        backend = AnthropicBackend(model_name=ApprovedModel.CLAUDE_HAIKU_4_5.value)

        prob_safe, prob_risk = backend.extract_logit_probs(
            messages=[{"role": "user", "content": "Hello, how are you?"}],
            config=LogitExtractionConfig(token_a="SAFE", token_b="RISK"),
        )

        assert isinstance(prob_safe, float)
        assert isinstance(prob_risk, float)
        assert 0.0 <= prob_safe <= 1.0
        assert 0.0 <= prob_risk <= 1.0
        print(f"✓ Anthropic logits: safe={prob_safe}, risk={prob_risk}")


class TestOpenAIIntegration:
    """Integration tests for OpenAI backend."""

    @pytest.fixture(scope="class")
    def check_openai_available(self):
        """Check if OpenAI API key is set."""
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set. Skipping OpenAI integration tests.")
        return True

    def test_openai_generate_basic(self, check_openai_available):
        """Test basic text generation with GPT."""
        backend = OpenAIBackend(model_name=ApprovedModel.GPT_5_MINI.value)

        result = backend.generate(
            messages=[{"role": "user", "content": "Say 'Hello'"}],
            config=GenerationConfig(max_tokens=10, temperature=0.0),
        )

        assert isinstance(result, str)
        assert len(result) > 0
        print(f"✓ OpenAI generate: {result}")
