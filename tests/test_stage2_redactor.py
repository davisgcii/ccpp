"""Tests for Stage2Redactor."""

import pytest
from unittest.mock import Mock, patch

from ccpp.infer.stage2_redactor import Stage2Redactor
from ccpp.types import RedactorOutput, MaskSpan, PIICategory


class TestStage2RedactorMockMode:
    """Tests for Stage2Redactor in mock mode."""

    @pytest.fixture
    def redactor(self):
        """Create Stage2Redactor in mock mode."""
        return Stage2Redactor(mock_mode=True)

    def test_init_mock_mode(self, redactor):
        """Test initialization in mock mode."""
        assert redactor.mock_mode is True
        assert redactor.backend is None

    def test_redact_no_pii(self, redactor, sample_safe_text):
        """Test redaction of safe text."""
        output = redactor.redact([], sample_safe_text)

        assert isinstance(output, RedactorOutput)
        assert len(output.spans) == 0

    def test_redact_email(self, redactor):
        """Test redaction of email."""
        text = "Contact me at john.doe@company.com"
        output = redactor.redact([], text)

        assert len(output.spans) >= 1
        email_span = output.spans[0]
        assert email_span.entity_text == "john.doe@company.com"
        assert email_span.category == PIICategory.PII_DIRECT

    def test_redact_phone(self, redactor):
        """Test redaction of phone number."""
        text = "Call me at 555-234-5678"
        output = redactor.redact([], text)

        assert len(output.spans) >= 1
        phone_span = output.spans[0]
        assert phone_span.entity_text == "555-234-5678"
        assert phone_span.category == PIICategory.PII_DIRECT

    def test_redact_multiple_entities(self, redactor, sample_pii_text):
        """Test redaction of multiple entities."""
        output = redactor.redact([], sample_pii_text)

        assert len(output.spans) >= 2
        # Should detect both email and phone

    def test_redact_allowlist_filtering(self, redactor):
        """Test that allowlisted entities are filtered."""
        text = "Email me at test@example.com or call 555-0100"
        output = redactor.redact([], text)

        # example.com and 555-01XX should be filtered
        assert len(output.spans) == 0

    def test_apply_masks(self, redactor):
        """Test applying masks to text."""
        text = "My email is john@test.com"
        output = redactor.redact([], text)

        if len(output.spans) > 0:
            masked_text = output.apply_masks(text)
            assert "john@test.com" not in masked_text
            assert "[PII/DIRECT]" in masked_text


class TestStage2RedactorRealMode:
    """Tests for Stage2Redactor with LLM backend."""

    @pytest.fixture
    def redactor(self, mock_llm_backend, stage2_config):
        """Create Stage2Redactor with mock backend."""
        return Stage2Redactor(
            llm_backend=mock_llm_backend,
            llm_config=stage2_config,
            mock_mode=False,
        )

    def test_init_real_mode(self, redactor, mock_llm_backend):
        """Test initialization in real mode."""
        assert redactor.mock_mode is False
        assert redactor.backend is mock_llm_backend
        assert len(redactor.few_shot_examples) > 0
        assert redactor.system_prompt != ""

    def test_init_requires_backend(self, stage2_config):
        """Test that real mode requires backend or config."""
        with pytest.raises(ValueError, match="must provide"):
            Stage2Redactor(mock_mode=False)

    def test_redact_calls_backend(self, redactor, mock_llm_backend):
        """Test that redaction calls the backend."""
        mock_llm_backend.generate.return_value = "PASS"

        output = redactor.redact([], "Test text")

        assert mock_llm_backend.generate.called
        assert len(output.spans) == 0  # PASS = no spans

    def test_parse_pass_output(self, redactor):
        """Test parsing PASS output."""
        output = redactor._parse_extraction_output("PASS")

        assert len(output.spans) == 0

    def test_parse_single_mask_output(self, redactor):
        """Test parsing single MASK output."""
        output_str = 'MASK "john@example.com" pii/direct'
        output = redactor._parse_extraction_output(output_str)

        assert len(output.spans) == 1
        assert output.spans[0].entity_text == "john@example.com"
        assert output.spans[0].category == PIICategory.PII_DIRECT

    def test_parse_multiple_mask_output(self, redactor):
        """Test parsing multiple MASK outputs."""
        output_str = 'MASK "alice@test.com" pii/direct; MASK "555-123-4567" pii/direct'
        output = redactor._parse_extraction_output(output_str)

        assert len(output.spans) == 2
        assert output.spans[0].entity_text == "alice@test.com"
        assert output.spans[1].entity_text == "555-123-4567"

    def test_parse_different_categories(self, redactor):
        """Test parsing different PII categories."""
        test_cases = [
            ('MASK "sk_live_123" credentials', PIICategory.CREDENTIALS),
            ('MASK "4532-1234-5678-9012" financial', PIICategory.FINANCIAL),
            ('MASK "diagnosis: flu" medical', PIICategory.MEDICAL),
            ('MASK "123 Main St" location/precise', PIICategory.LOCATION_PRECISE),
        ]

        for output_str, expected_category in test_cases:
            output = redactor._parse_extraction_output(output_str)
            assert len(output.spans) == 1
            assert output.spans[0].category == expected_category

    def test_parse_case_insensitive(self, redactor):
        """Test that parsing is case-insensitive."""
        outputs = [
            'MASK "test@test.com" pii/direct',
            'mask "test@test.com" pii/direct',
            'Mask "test@test.com" pii/direct',
        ]

        for output_str in outputs:
            output = redactor._parse_extraction_output(output_str)
            assert len(output.spans) == 1

    def test_parse_unknown_category_defaults(self, redactor):
        """Test that unknown categories default to PII_DIRECT."""
        output_str = 'MASK "entity" unknown_category'
        output = redactor._parse_extraction_output(output_str)

        assert len(output.spans) == 1
        assert output.spans[0].category == PIICategory.PII_DIRECT

    def test_format_prompt_with_few_shot(self, redactor, sample_messages):
        """Test prompt formatting with few-shot examples."""
        messages = redactor._format_prompt_with_few_shot(sample_messages, "Window text")

        assert len(messages) > 0
        assert messages[0]["role"] == "system"
        # Should include examples
        assert any("MASK" in msg.get("content", "") for msg in messages)

    def test_format_context(self, redactor, sample_messages):
        """Test context formatting."""
        context = redactor._format_context(sample_messages)

        assert len(context) > 0
        assert "User:" in context or "user" in context.lower()

    def test_format_extraction_query(self, redactor):
        """Test extraction query formatting."""
        query = redactor._format_extraction_query("Context here", "Window text here")

        assert "Context:" in query
        assert "Window text:" in query
        assert "Context here" in query
        assert "Window text here" in query


class TestStage2RedactorIntegration:
    """Integration tests for Stage2Redactor."""

    def test_end_to_end_redaction(self):
        """Test end-to-end redaction in mock mode."""
        redactor = Stage2Redactor(mock_mode=True)

        text = "Email: alice@company.com, Phone: 555-234-5678"
        output = redactor.redact([], text)

        # Should detect entities
        assert len(output.spans) >= 1

        # Apply masks
        masked_text = output.apply_masks(text)
        assert "alice@company.com" not in masked_text or "555-234-5678" not in masked_text

    def test_preserves_non_pii_text(self):
        """Test that non-PII text is preserved."""
        redactor = Stage2Redactor(mock_mode=True)

        text = "Hello, this is a safe message."
        output = redactor.redact([], text)

        masked_text = output.apply_masks(text)
        assert masked_text == text  # Should be unchanged

    @patch('ccpp.infer.stage2_redactor.create_backend_from_config')
    def test_init_from_config(self, mock_factory, stage2_config):
        """Test initialization from config dict."""
        mock_backend = Mock()
        mock_backend.generate.return_value = "PASS"
        mock_factory.return_value = mock_backend

        redactor = Stage2Redactor(llm_config=stage2_config, mock_mode=False)

        assert redactor.backend is not None
        mock_factory.assert_called_once()

    def test_parse_quoted_entities_with_spaces(self):
        """Test parsing entities with spaces."""
        redactor = Stage2Redactor(mock_mode=True)

        output_str = 'MASK "John Doe" pii/direct'
        output = redactor._parse_extraction_output(output_str)

        assert len(output.spans) == 1
        assert output.spans[0].entity_text == "John Doe"

    def test_parse_escaped_quotes(self):
        """Test parsing entities with escaped quotes."""
        redactor = Stage2Redactor(mock_mode=True)

        output_str = 'MASK "John ""Johnny"" Doe" pii/direct'
        output = redactor._parse_extraction_output(output_str)

        assert len(output.spans) == 1
        assert output.spans[0].entity_text == 'John "Johnny" Doe'
