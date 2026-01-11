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


def _create_mock_logprobs_response(response_text, logprobs_data):
    """Helper to create mock Ollama generate response with Pydantic-like logprobs.

    The ollama-python SDK returns Pydantic objects, not dicts. This helper creates
    mock objects that match the SDK's response structure.

    Args:
        response_text: The generated text response
        logprobs_data: List of dicts with {token, logprob, top_logprobs: [{token, logprob}, ...]}

    Returns:
        Mock response object with .logprobs attribute containing Logprob-like objects
    """
    mock_response = MagicMock()
    mock_response.response = response_text

    if not logprobs_data:
        mock_response.logprobs = []
        return mock_response

    mock_logprobs = []
    for lp_data in logprobs_data:
        mock_logprob = MagicMock()
        mock_logprob.token = lp_data.get("token", "")
        mock_logprob.logprob = lp_data.get("logprob", 0.0)

        # Create top_logprobs as list of TokenLogprob-like objects
        top_logprobs = []
        for tlp in lp_data.get("top_logprobs", []):
            mock_token_logprob = MagicMock()
            mock_token_logprob.token = tlp.get("token", "")
            mock_token_logprob.logprob = tlp.get("logprob", 0.0)
            top_logprobs.append(mock_token_logprob)

        mock_logprob.top_logprobs = top_logprobs
        mock_logprobs.append(mock_logprob)

    mock_response.logprobs = mock_logprobs
    return mock_response


class TestGenerationConfig:
    """Tests for GenerationConfig."""

    def test_default_config(self):
        """Test default generation config."""
        config = GenerationConfig()
        assert config.max_tokens == 100
        assert config.temperature == 0.0
        assert config.top_p == 1.0
        assert config.top_k is None
        assert config.min_p is None
        assert config.do_sample is False
        assert config.stop_sequences == []

    def test_custom_config(self):
        """Test custom generation config."""
        config = GenerationConfig(
            max_tokens=200,
            temperature=0.7,
            top_p=0.9,
            top_k=50,
            min_p=0.05,
            do_sample=True,
            stop_sequences=["\n", "STOP"],
        )
        assert config.max_tokens == 200
        assert config.temperature == 0.7
        assert config.top_p == 0.9
        assert config.top_k == 50
        assert config.min_p == 0.05
        assert config.do_sample is True
        assert config.stop_sequences == ["\n", "STOP"]


class TestLogitExtractionConfig:
    """Tests for LogitExtractionConfig."""

    def test_default_config(self):
        """Test default logit extraction config."""
        config = LogitExtractionConfig()
        assert config.token_a == "SAFE"
        assert config.token_b == "FAIL"
        assert config.enable_thinking is False

    def test_custom_tokens(self):
        """Test custom tokens."""
        config = LogitExtractionConfig(token_a="YES", token_b="NO")
        assert config.token_a == "YES"
        assert config.token_b == "NO"
        assert config.enable_thinking is False


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
        # Mock chat response with Pydantic-like object
        mock_message = MagicMock()
        mock_message.content = "Hello there!"
        mock_chat_response = MagicMock()
        mock_chat_response.message = mock_message
        mock_client.chat.return_value = mock_chat_response
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
        """Test logit extraction for safe content with logprobs."""
        mock_client = MagicMock()
        mock_client.list.return_value = _create_mock_list_response([ApprovedModel.QWEN3_1_7B.value])
        # SAFE has higher logprob - use Pydantic-like response structure
        mock_client.generate.return_value = _create_mock_logprobs_response(
            "SAFE",
            [
                {
                    "token": "SAFE",
                    "logprob": -0.5,
                    "top_logprobs": [
                        {"token": "SAFE", "logprob": -0.5},
                        {"token": "FAIL", "logprob": -1.5},
                    ]
                }
            ]
        )
        mock_client_class.return_value = mock_client

        backend = OllamaBackend(model_name=ApprovedModel.QWEN3_1_7B.value)
        prob_safe, prob_fail = backend.extract_logit_probs(
            [{"role": "user", "content": "Test"}],
            LogitExtractionConfig(),
        )

        # With logprobs -0.5 and -1.5, softmax gives ~73% SAFE, ~27% FAIL
        assert 0.7 < prob_safe < 0.8
        assert 0.2 < prob_fail < 0.3

    @patch('ollama.Client')
    def test_ollama_extract_logit_probs_fail(self, mock_client_class):
        """Test logit extraction for risky content with logprobs."""
        mock_client = MagicMock()
        mock_client.list.return_value = _create_mock_list_response([ApprovedModel.QWEN3_1_7B.value])
        # FAIL has higher logprob - use Pydantic-like response structure
        mock_client.generate.return_value = _create_mock_logprobs_response(
            "FAIL",
            [
                {
                    "token": "FAIL",
                    "logprob": -0.3,
                    "top_logprobs": [
                        {"token": "FAIL", "logprob": -0.3},
                        {"token": "SAFE", "logprob": -2.0},
                    ]
                }
            ]
        )
        mock_client_class.return_value = mock_client

        backend = OllamaBackend(model_name=ApprovedModel.QWEN3_1_7B.value)
        prob_safe, prob_fail = backend.extract_logit_probs(
            [{"role": "user", "content": "My email is test@test.com"}],
            LogitExtractionConfig(),
        )

        # With logprobs -2.0 and -0.3, FAIL should dominate (~85%)
        assert prob_fail > 0.8
        assert prob_safe < 0.2

    @patch('ollama.Client')
    def test_ollama_extract_logit_probs_equal(self, mock_client_class):
        """Test logit extraction when SAFE and FAIL have equal logprobs."""
        mock_client = MagicMock()
        mock_client.list.return_value = _create_mock_list_response([ApprovedModel.QWEN3_1_7B.value])
        # Equal logprobs = 50/50 probability - use Pydantic-like response structure
        mock_client.generate.return_value = _create_mock_logprobs_response(
            "SAFE",
            [
                {
                    "token": "SAFE",
                    "logprob": -1.0,
                    "top_logprobs": [
                        {"token": "SAFE", "logprob": -1.0},
                        {"token": "FAIL", "logprob": -1.0},
                    ]
                }
            ]
        )
        mock_client_class.return_value = mock_client

        backend = OllamaBackend(model_name=ApprovedModel.QWEN3_1_7B.value)
        prob_safe, prob_fail = backend.extract_logit_probs(
            [{"role": "user", "content": "Hello"}],
            LogitExtractionConfig(),
        )

        # Equal logprobs = 50% each
        assert abs(prob_safe - 0.5) < 0.01
        assert abs(prob_fail - 0.5) < 0.01
        assert abs(prob_safe + prob_fail - 1.0) < 0.01

    @patch('ollama.Client')
    def test_ollama_extract_logit_probs_error_when_logprobs_missing(self, mock_client_class):
        """Test that ValueError is raised when logprobs not returned."""
        mock_client = MagicMock()
        mock_client.list.return_value = _create_mock_list_response([ApprovedModel.QWEN3_1_7B.value])
        # No logprobs in response - use Pydantic-like response structure
        mock_client.generate.return_value = _create_mock_logprobs_response("SAFE", [])
        mock_client_class.return_value = mock_client

        backend = OllamaBackend(model_name=ApprovedModel.QWEN3_1_7B.value)

        with pytest.raises(ValueError, match="Ollama did not return logprobs"):
            backend.extract_logit_probs(
                [{"role": "user", "content": "Test"}],
                LogitExtractionConfig(),
            )

    @patch('ollama.Client')
    def test_ollama_extract_logit_probs_error_when_tokens_missing(self, mock_client_class):
        """Test that ValueError is raised when SAFE/FAIL not in top_logprobs."""
        mock_client = MagicMock()
        mock_client.list.return_value = _create_mock_list_response([ApprovedModel.QWEN3_1_7B.value])
        # logprobs exist but SAFE/FAIL aren't in top_logprobs - use Pydantic-like response
        mock_client.generate.return_value = _create_mock_logprobs_response(
            "OK",
            [
                {
                    "token": "OK",
                    "logprob": -0.1,
                    "top_logprobs": [
                        {"token": "OK", "logprob": -0.1},
                        {"token": "YES", "logprob": -0.5},
                    ]
                }
            ]
        )
        mock_client_class.return_value = mock_client

        backend = OllamaBackend(model_name=ApprovedModel.QWEN3_1_7B.value)

        with pytest.raises(ValueError, match="found in top_logprobs"):
            backend.extract_logit_probs(
                [{"role": "user", "content": "Hello"}],
                LogitExtractionConfig(),
            )


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
