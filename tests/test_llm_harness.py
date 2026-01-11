"""Tests for LLM harness components."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import os

from ccpp.llm.base import (
    LLMBackend,
    ModelBackend,
    GenerationConfig,
    LogitExtractionConfig,
)
from ccpp.llm.factory import create_backend_from_config
from ccpp.llm.ollama_backend import OllamaBackend
from ccpp.llm.api_backend import AnthropicBackend, OpenAIBackend
from ccpp.types import ApprovedModel



def _create_mock_list_response(model_names):
    """Helper to create mock Ollama ListResponse."""
    mock_models = []
    for name in model_names:
        mock_model = MagicMock()
        mock_model.model = name
        mock_models.append(mock_model)
    
    mock_list_response = MagicMock()
    mock_list_response.models = mock_models
    return mock_list_response


class TestGenerationConfig:
    """Tests for GenerationConfig."""

    def test_default_config(self):
        """Test default generation config."""
        config = GenerationConfig()
        assert config.max_tokens == 100
        assert config.temperature == 0.0
        assert config.top_p == 1.0
        assert config.do_sample is False
        assert config.stop_sequences == []

    def test_custom_config(self):
        """Test custom generation config."""
        config = GenerationConfig(
            max_tokens=200,
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
            stop_sequences=["\n", "STOP"],
        )
        assert config.max_tokens == 200
        assert config.temperature == 0.7
        assert config.top_p == 0.9
        assert config.do_sample is True
        assert config.stop_sequences == ["\n", "STOP"]


class TestLogitExtractionConfig:
    """Tests for LogitExtractionConfig."""

    def test_default_config(self):
        """Test default logit extraction config."""
        config = LogitExtractionConfig()
        assert config.token_a == "SAFE"
        assert config.token_b == "RISK"

    def test_custom_tokens(self):
        """Test custom tokens."""
        config = LogitExtractionConfig(token_a="YES", token_b="NO")
        assert config.token_a == "YES"
        assert config.token_b == "NO"


class TestOllamaBackend:
    """Tests for OllamaBackend."""

    @patch('ollama.Client')
    def test_ollama_backend_init_success(self, mock_client_class):
        """Test successful OllamaBackend initialization."""
        # Mock client instance
        mock_client = MagicMock()

        # Mock ListResponse object with .models attribute
        mock_model = MagicMock()
        mock_model.model = ApprovedModel.QWEN3_1_7B.value

        mock_list_response = MagicMock()
        mock_list_response.models = [mock_model]

        mock_client.list.return_value = mock_list_response
        mock_client_class.return_value = mock_client

        backend = OllamaBackend(model_name=ApprovedModel.QWEN3_1_7B.value)
        assert backend.model_name == ApprovedModel.QWEN3_1_7B.value
        assert backend.timeout == 60

    @patch('ollama.Client')
    def test_ollama_backend_model_not_found(self, mock_client_class):
        """Test OllamaBackend when model not found."""
        mock_client = MagicMock()
        mock_client.list.return_value = _create_mock_list_response(["other:model"])
        mock_client_class.return_value = mock_client

        with pytest.raises(ValueError, match="Model .* not found"):
            OllamaBackend(model_name=ApprovedModel.QWEN3_1_7B.value)

    @patch('ollama.Client')
    def test_ollama_backend_connection_error(self, mock_client_class):
        """Test OllamaBackend when Ollama server not accessible."""
        mock_client = MagicMock()
        mock_client.list.side_effect = Exception("Connection refused")
        mock_client_class.return_value = mock_client

        with pytest.raises(ConnectionError, match="Cannot connect to Ollama"):
            OllamaBackend(model_name=ApprovedModel.QWEN3_1_7B.value)

    @patch('ollama.Client')
    def test_ollama_generate(self, mock_client_class):
        """Test text generation."""
        mock_client = MagicMock()
        mock_client.list.return_value = _create_mock_list_response([ApprovedModel.QWEN3_1_7B.value])
        mock_client.chat.return_value = {"message": {"content": "Hello there!"}}
        mock_client_class.return_value = mock_client

        backend = OllamaBackend(model_name=ApprovedModel.QWEN3_1_7B.value)
        result = backend.generate(
            [{"role": "user", "content": "Say hello"}],
            GenerationConfig(max_tokens=10),
        )

        assert result == "Hello there!"
        mock_client.chat.assert_called_once()

    @patch('ollama.Client')
    def test_ollama_extract_logit_probs_safe(self, mock_client_class):
        """Test logit extraction for safe content."""
        mock_client = MagicMock()
        mock_client.list.return_value = _create_mock_list_response([ApprovedModel.QWEN3_1_7B.value])
        mock_client.chat.return_value = {"message": {"content": "SAFE"}}
        mock_client_class.return_value = mock_client

        backend = OllamaBackend(model_name=ApprovedModel.QWEN3_1_7B.value)
        prob_safe, prob_risk = backend.extract_logit_probs(
            [{"role": "user", "content": "Test"}],
            LogitExtractionConfig(),
        )

        assert prob_safe == 1.0
        assert prob_risk == 0.0

    @patch('ollama.Client')
    def test_ollama_extract_logit_probs_risk(self, mock_client_class):
        """Test logit extraction for risky content."""
        mock_client = MagicMock()
        mock_client.list.return_value = _create_mock_list_response([ApprovedModel.QWEN3_1_7B.value])
        mock_client.chat.return_value = {"message": {"content": "RISK"}}
        mock_client_class.return_value = mock_client

        backend = OllamaBackend(model_name=ApprovedModel.QWEN3_1_7B.value)
        prob_safe, prob_risk = backend.extract_logit_probs(
            [{"role": "user", "content": "My email is test@test.com"}],
            LogitExtractionConfig(),
        )

        assert prob_safe == 0.0
        assert prob_risk == 1.0


class TestAnthropicBackend:
    """Tests for AnthropicBackend."""

    def test_anthropic_backend_missing_api_key(self):
        """Test AnthropicBackend with missing API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="API key required"):
                AnthropicBackend()

    @patch('anthropic.Anthropic')
    def test_anthropic_backend_init_with_env_key(self, mock_anthropic_class):
        """Test AnthropicBackend initialization with env var."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            backend = AnthropicBackend()
            assert backend.model_name == ApprovedModel.CLAUDE_HAIKU_4_5.value

    @patch('anthropic.Anthropic')
    def test_anthropic_backend_init_with_param_key(self, mock_anthropic_class):
        """Test AnthropicBackend initialization with parameter."""
        backend = AnthropicBackend(api_key="sk-ant-test")
        assert backend.model_name == ApprovedModel.CLAUDE_HAIKU_4_5.value

    @patch('anthropic.Anthropic')
    def test_anthropic_generate(self, mock_anthropic_class):
        """Test Anthropic text generation."""
        # Mock client and response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hello from Claude!")]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        backend = AnthropicBackend(api_key="sk-ant-test")
        result = backend.generate(
            [{"role": "user", "content": "Say hello"}],
            GenerationConfig(max_tokens=10),
        )

        assert result == "Hello from Claude!"


class TestOpenAIBackend:
    """Tests for OpenAIBackend."""

    def test_openai_backend_missing_api_key(self):
        """Test OpenAIBackend with missing API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="API key required"):
                OpenAIBackend()

    @patch('openai.OpenAI')
    def test_openai_backend_init_with_env_key(self, mock_openai_class):
        """Test OpenAIBackend initialization with env var."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            backend = OpenAIBackend()
            assert backend.model_name == ApprovedModel.GPT_5_MINI.value


class TestBackendFactory:
    """Tests for backend factory."""

    def test_factory_missing_backend_key(self):
        """Test factory with missing backend key."""
        with pytest.raises(ValueError, match="must contain 'backend'"):
            create_backend_from_config({})

    def test_factory_unknown_backend(self):
        """Test factory with unknown backend."""
        with pytest.raises(ValueError, match="Unknown backend"):
            create_backend_from_config({"backend": "unknown"})

    @patch('ollama.Client')
    def test_factory_creates_ollama_backend(self, mock_client_class):
        """Test factory creates Ollama backend."""
        mock_client = MagicMock()
        mock_client.list.return_value = _create_mock_list_response([ApprovedModel.QWEN3_1_7B.value])
        mock_client_class.return_value = mock_client

        config = {"backend": "ollama", "model_name": ApprovedModel.QWEN3_1_7B.value}
        backend = create_backend_from_config(config)

        assert isinstance(backend, OllamaBackend)
        assert backend.model_name == ApprovedModel.QWEN3_1_7B.value

    @patch('anthropic.Anthropic')
    def test_factory_creates_anthropic_backend(self, mock_anthropic_class):
        """Test factory creates Anthropic backend."""
        config = {
            "backend": "anthropic",
            "model_name": ApprovedModel.CLAUDE_HAIKU_4_5.value,
            "api_key": "sk-ant-test",
        }
        backend = create_backend_from_config(config)

        assert isinstance(backend, AnthropicBackend)

    @patch('openai.OpenAI')
    def test_factory_creates_openai_backend(self, mock_openai_class):
        """Test factory creates OpenAI backend."""
        config = {
            "backend": "openai",
            "model_name": ApprovedModel.GPT_5_MINI.value,
            "api_key": "sk-test",
        }
        backend = create_backend_from_config(config)

        assert isinstance(backend, OpenAIBackend)

    def test_factory_ollama_missing_model_name(self):
        """Test factory with Ollama but missing model_name."""
        with pytest.raises(ValueError, match="requires 'model_name'"):
            create_backend_from_config({"backend": "ollama"})
