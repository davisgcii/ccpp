"""Tests for ccpp.types module."""

import pytest
from ccpp.types import (
    PIICategory,
    RiskScore,
    MaskSpan,
    RedactorOutput,
    HoldbackBuffer,
    RiskState,
)


class TestPIICategory:
    """Tests for PIICategory enum."""

    def test_all_categories_exist(self):
        """Test that all expected categories exist."""
        expected = [
            "SAFE",
            "PERSON",
            "CONTACT",
            "GOV_ID",
            "IDENTIFIER",
            "LOCATION",
            "FINANCIAL",
            "CREDENTIALS",
            "MEDICAL",
        ]
        for cat in expected:
            assert hasattr(PIICategory, cat)

    def test_category_values(self):
        """Test category string values."""
        assert PIICategory.SAFE.value == "safe"
        assert PIICategory.CONTACT.value == "contact"
        assert PIICategory.CREDENTIALS.value == "credentials"


class TestRiskScore:
    """Tests for RiskScore."""

    def test_risk_score_creation(self):
        """Test creating a RiskScore."""
        score = RiskScore(score=0.75)
        assert score.score == 0.75

    def test_risk_score_bounds(self):
        """Test that risk scores are bounded [0, 1]."""
        # This would ideally be enforced by the type
        score1 = RiskScore(score=0.0)
        score2 = RiskScore(score=1.0)
        assert 0.0 <= score1.score <= 1.0
        assert 0.0 <= score2.score <= 1.0


class TestMaskSpan:
    """Tests for MaskSpan."""

    def test_mask_span_creation(self):
        """Test creating a MaskSpan."""
        span = MaskSpan(
            entity_text="john@example.com",
            category=PIICategory.CONTACT
        )
        assert span.entity_text == "john@example.com"
        assert span.category == PIICategory.CONTACT

    def test_mask_span_with_special_chars(self):
        """Test MaskSpan with special characters."""
        span = MaskSpan(
            entity_text='My "quoted" email',
            category=PIICategory.CONTACT
        )
        assert span.entity_text == 'My "quoted" email'


class TestRedactorOutput:
    """Tests for RedactorOutput."""

    def test_redactor_output_empty(self):
        """Test RedactorOutput with no spans."""
        output = RedactorOutput(spans=[])
        assert len(output.spans) == 0

    def test_redactor_output_with_spans(self, sample_mask_spans):
        """Test RedactorOutput with spans."""
        output = RedactorOutput(spans=sample_mask_spans)
        assert len(output.spans) == 2
        assert output.spans[0].entity_text == "john.doe@company.com"
        assert output.spans[1].entity_text == "555-123-4567"

    def test_apply_masks_no_spans(self):
        """Test applying masks when no spans present."""
        output = RedactorOutput(spans=[])
        text = "Hello, this is safe text."
        result = output.apply_masks(text)
        assert result == text

    def test_apply_masks_single_span(self):
        """Test applying a single mask."""
        span = MaskSpan(entity_text="john@example.com", category=PIICategory.CONTACT)
        output = RedactorOutput(spans=[span])
        text = "Contact me at john@example.com for details."
        result = output.apply_masks(text)
        assert "john@example.com" not in result
        assert "[CONTACT]" in result

    def test_apply_masks_multiple_spans(self, sample_mask_spans):
        """Test applying multiple masks."""
        output = RedactorOutput(spans=sample_mask_spans)
        text = "Email: john.doe@company.com, Phone: 555-123-4567"
        result = output.apply_masks(text)
        assert "john.doe@company.com" not in result
        assert "555-123-4567" not in result
        assert result.count("[CONTACT]") == 2

    def test_apply_masks_custom_format(self):
        """Test custom mask format."""
        span = MaskSpan(entity_text="secret", category=PIICategory.CREDENTIALS)
        output = RedactorOutput(spans=[span])
        text = "The secret is here."
        result = output.apply_masks(text, mask_format="***{type}***")
        assert "***CREDENTIALS***" in result
        assert "secret" not in result

    def test_apply_masks_case_sensitive(self):
        """Test that masking is case-sensitive."""
        span = MaskSpan(entity_text="John", category=PIICategory.CONTACT)
        output = RedactorOutput(spans=[span])
        text = "John and john are different."
        result = output.apply_masks(text)
        # Only "John" should be masked, not "john"
        assert result.count("[CONTACT]") == 1
        assert "john" in result  # lowercase should remain

    def test_apply_masks_prefers_longer_entities(self):
        """Test that longer entities are masked first."""
        spans = [
            MaskSpan(entity_text="george", category=PIICategory.CONTACT),
            MaskSpan(entity_text="george@gmail.com", category=PIICategory.CONTACT),
        ]
        output = RedactorOutput(spans=spans)
        text = "Contact george@gmail.com for help."
        result = output.apply_masks(text)
        assert "[CONTACT]" in result
        assert "george@gmail.com" not in result


class TestHoldbackBuffer:
    """Tests for HoldbackBuffer."""

    def test_holdback_buffer_creation(self):
        """Test creating a HoldbackBuffer."""
        buffer = HoldbackBuffer(raw_text="Hello", overlap_tail="llo")
        assert buffer.raw_text == "Hello"
        assert buffer.overlap_tail == "llo"

    def test_holdback_buffer_empty(self):
        """Test empty HoldbackBuffer."""
        buffer = HoldbackBuffer(raw_text="", overlap_tail="")
        assert buffer.raw_text == ""
        assert buffer.overlap_tail == ""


class TestRiskState:
    """Tests for RiskState."""

    def test_risk_state_creation(self):
        """Test creating a RiskState."""
        state = RiskState(
            ema_risk=0.5,
            is_escalated=True
        )
        assert state.ema_risk == 0.5
        assert state.is_escalated is True

    def test_risk_state_defaults(self):
        """Test RiskState default values."""
        state = RiskState()
        assert state.ema_risk == 0.0
        assert state.is_escalated is False

    def test_risk_state_transitions(self):
        """Test risk state transitions."""
        state = RiskState(ema_risk=0.2, is_escalated=False)

        # Simulate escalation
        state.ema_risk = 0.7
        state.is_escalated = True
        assert state.is_escalated is True

        # Simulate de-escalation
        state.ema_risk = 0.2
        state.is_escalated = False
        assert state.is_escalated is False
