"""Tests for Stage1Router."""

import pytest
from unittest.mock import Mock, patch

from ccpp.infer.stage1_router import Stage1Router
from ccpp.types import RiskScore


class TestStage1RouterMockMode:
    """Tests for Stage1Router in mock mode."""

    @pytest.fixture
    def router(self):
        """Create Stage1Router in mock mode."""
        return Stage1Router(mock_mode=True)

    def test_init_mock_mode(self, router):
        """Test initialization in mock mode."""
        assert router.mock_mode is True
        assert router.backend is None

    def test_classify_safe_text(self, router, sample_safe_text):
        """Test classification of safe text."""
        risk = router.classify([], sample_safe_text)

        assert isinstance(risk, RiskScore)
        assert 0.0 <= risk.score <= 1.0
        # Mock mode returns relatively low scores for safe text
        assert risk.score < 0.5

    def test_classify_pii_text(self, router, sample_pii_text):
        """Test classification of PII text."""
        risk = router.classify([], sample_pii_text)

        assert isinstance(risk, RiskScore)
        # Mock mode should detect @ symbol and digits
        assert risk.score > 0.3

    def test_classify_with_context(self, router, sample_messages):
        """Test classification with conversation context."""
        risk = router.classify(sample_messages, "My email is test@test.com")

        assert isinstance(risk, RiskScore)
        assert risk.score > 0.3  # Should detect email

    def test_classify_determinism(self, router):
        """Test that mock mode has some randomness."""
        # Mock mode adds random noise, so results vary slightly
        text = "Test message"
        results = [router.classify([], text).score for _ in range(5)]

        # Should have some variation due to random component
        assert len(set(results)) > 1


class TestStage1RouterRealMode:
    """Tests for Stage1Router with LLM backend."""

    @pytest.fixture
    def router(self, mock_llm_backend, stage1_config):
        """Create Stage1Router with mock backend."""
        return Stage1Router(
            llm_backend=mock_llm_backend,
            llm_config=stage1_config,
            mock_mode=False,
        )

    def test_init_real_mode(self, router, mock_llm_backend):
        """Test initialization in real mode."""
        assert router.mock_mode is False
        assert router.backend is mock_llm_backend
        assert len(router.few_shot_examples) > 0
        assert router.system_prompt != ""

    def test_init_requires_backend(self, stage1_config):
        """Test that real mode requires backend or config."""
        with pytest.raises(ValueError, match="must provide"):
            Stage1Router(mock_mode=False)

    def test_classify_calls_backend(self, router, mock_llm_backend, sample_safe_text):
        """Test that classification calls the backend."""
        mock_llm_backend.extract_logit_probs.return_value = (0.9, 0.1)

        risk = router.classify([], sample_safe_text)

        assert mock_llm_backend.extract_logit_probs.called
        assert risk.score == 0.1  # prob_risk

    def test_classify_safe_result(self, router, mock_llm_backend):
        """Test classification returning SAFE."""
        mock_llm_backend.extract_logit_probs.return_value = (0.95, 0.05)

        risk = router.classify([], "Hello there")

        assert risk.score == 0.05
        assert risk.score < 0.3

    def test_classify_risk_result(self, router, mock_llm_backend):
        """Test classification returning RISK."""
        mock_llm_backend.extract_logit_probs.return_value = (0.1, 0.9)

        risk = router.classify([], "My email is test@test.com")

        assert risk.score == 0.9
        assert risk.score > 0.7

    def test_format_prompt_with_few_shot(self, router, sample_messages):
        """Test prompt formatting with few-shot examples."""
        messages = router._format_prompt_with_few_shot(sample_messages, "Current text")

        # Should have system prompt + examples + actual query
        assert len(messages) > 0
        assert messages[0]["role"] == "system"
        assert any("SAFE" in msg.get("content", "") for msg in messages)

    def test_format_context_empty(self, router):
        """Test context formatting with no messages."""
        context = router._format_context([])
        assert "No prior context" in context

    def test_format_context_with_messages(self, router, sample_messages):
        """Test context formatting with messages."""
        context = router._format_context(sample_messages)

        assert "User:" in context or "user" in context.lower()
        assert "Assistant:" in context or "assistant" in context.lower()

    def test_load_config_from_dict(self, mock_llm_backend, stage1_config):
        """Test loading configuration from dict."""
        router = Stage1Router(
            llm_backend=mock_llm_backend,
            llm_config=stage1_config,
            mock_mode=False,
        )

        assert router.system_prompt == stage1_config["system_prompt"]
        assert len(router.few_shot_examples) == len(stage1_config["few_shot"]["examples"])
        assert router.logit_config.token_a == "SAFE"
        assert router.logit_config.token_b == "RISK"


class TestStage1RouterIntegration:
    """Integration tests for Stage1Router."""

    def test_mock_to_real_mode_compatible(self):
        """Test that mock and real mode have same interface."""
        mock_router = Stage1Router(mock_mode=True)

        # Both should have classify method
        assert hasattr(mock_router, "classify")

        # Both should return RiskScore
        result = mock_router.classify([], "Test")
        assert isinstance(result, RiskScore)

    @patch('ccpp.infer.stage1_router.create_backend_from_config')
    def test_init_from_config(self, mock_factory, stage1_config):
        """Test initialization from config dict."""
        mock_backend = Mock()
        mock_backend.extract_logit_probs.return_value = (0.9, 0.1)
        mock_factory.return_value = mock_backend

        router = Stage1Router(llm_config=stage1_config, mock_mode=False)

        assert router.backend is not None
        mock_factory.assert_called_once()
