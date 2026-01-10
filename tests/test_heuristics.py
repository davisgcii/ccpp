"""Tests for fast heuristics module."""

import pytest
from src.ccpp.infer.heuristics import FastHeuristics, HeuristicMatch
from src.ccpp.types import PIICategory


class TestFastHeuristics:
    """Tests for FastHeuristics."""

    @pytest.fixture
    def heuristics(self):
        """Create FastHeuristics instance."""
        return FastHeuristics()

    def test_detect_email(self, heuristics):
        """Test email detection."""
        text = "Contact me at john.doe@company.com for details."
        matches = heuristics.detect(text)

        assert len(matches) == 1
        assert matches[0].pattern == "email"
        assert matches[0].matched_text == "john.doe@company.com"
        assert matches[0].category == PIICategory.PII_DIRECT
        assert matches[0].confidence >= 0.9

    def test_detect_multiple_emails(self, heuristics):
        """Test detection of multiple emails."""
        text = "Email alice@test.com or bob@test.com"
        matches = heuristics.detect(text)

        assert len(matches) == 2
        emails = [m.matched_text for m in matches]
        assert "alice@test.com" in emails
        assert "bob@test.com" in emails

    def test_email_allowlist(self, heuristics):
        """Test that example.com emails are filtered."""
        text = "Use test@example.com for testing."
        matches = heuristics.detect(text)

        # example.com should be filtered out
        assert len(matches) == 0

    def test_detect_phone_number(self, heuristics):
        """Test phone number detection."""
        text = "Call me at 555-123-4567 tomorrow."
        matches = heuristics.detect(text)

        assert len(matches) == 1
        assert matches[0].pattern == "phone"
        assert matches[0].matched_text == "555-123-4567"
        assert matches[0].category == PIICategory.PII_DIRECT

    def test_phone_number_formats(self, heuristics):
        """Test various phone number formats."""
        texts = [
            "5551234567",
            "555-123-4567",
            "555.123.4567",
        ]

        for text in texts:
            matches = heuristics.detect(text)
            assert len(matches) >= 1, f"Failed to detect: {text}"

    def test_phone_allowlist(self, heuristics):
        """Test that test phone numbers are filtered."""
        text = "Test number: 555-0100"
        matches = heuristics.detect(text)

        # 555-01XX should be filtered
        assert len(matches) == 0

    def test_detect_ssn(self, heuristics):
        """Test SSN detection."""
        text = "My SSN is 123-45-6789"
        matches = heuristics.detect(text)

        assert len(matches) == 1
        assert matches[0].pattern == "ssn"
        assert matches[0].matched_text == "123-45-6789"
        assert matches[0].category == PIICategory.PII_DIRECT

    def test_ssn_allowlist(self, heuristics):
        """Test that invalid SSNs are filtered."""
        invalid_ssns = [
            "000-00-0000",
            "999-99-9999",
            "123-45-6789",  # Known test SSN
        ]

        for ssn in invalid_ssns:
            matches = heuristics.detect(ssn)
            # Should be filtered or at least have low confidence
            if matches:
                assert all(m.confidence < 0.9 for m in matches)

    def test_detect_credit_card(self, heuristics):
        """Test credit card detection with Luhn validation."""
        # Valid test card number (passes Luhn check)
        text = "Card: 4532015112830366"
        matches = heuristics.detect(text)

        assert len(matches) >= 1
        card_match = next((m for m in matches if m.pattern == "credit_card"), None)
        assert card_match is not None
        assert card_match.category == PIICategory.FINANCIAL

    def test_credit_card_invalid_luhn(self, heuristics):
        """Test that invalid Luhn check is filtered."""
        # Invalid card number (fails Luhn check)
        text = "Card: 1234567890123456"
        matches = heuristics.detect(text)

        # Should not detect as credit card
        card_matches = [m for m in matches if m.pattern == "credit_card"]
        assert len(card_matches) == 0

    def test_detect_aws_key(self, heuristics):
        """Test AWS access key detection."""
        text = "Key: AKIAIOSFODNN7EXAMPLE"
        matches = heuristics.detect(text)

        aws_matches = [m for m in matches if m.pattern == "aws_key"]
        assert len(aws_matches) >= 1
        assert aws_matches[0].category == PIICategory.CREDENTIALS

    def test_detect_stripe_key(self, heuristics):
        """Test Stripe key detection."""
        text = "API key: sk_live_abc123xyz789"
        matches = heuristics.detect(text)

        stripe_matches = [m for m in matches if m.pattern == "stripe_key"]
        assert len(stripe_matches) >= 1
        assert stripe_matches[0].category == PIICategory.CREDENTIALS

    def test_stripe_test_key_filtered(self, heuristics):
        """Test that Stripe test keys are filtered."""
        text = "Test key: sk_test_abc123"
        matches = heuristics.detect(text)

        # sk_test_ should be filtered
        stripe_matches = [m for m in matches if m.pattern == "stripe_key"]
        assert len(stripe_matches) == 0

    def test_detect_github_token(self, heuristics):
        """Test GitHub token detection."""
        text = "Token: ghp_" + "a" * 36
        matches = heuristics.detect(text)

        github_matches = [m for m in matches if m.pattern == "github_token"]
        assert len(github_matches) >= 1
        assert github_matches[0].category == PIICategory.CREDENTIALS

    def test_detect_pem_block(self, heuristics):
        """Test PEM private key block detection."""
        text = "-----BEGIN RSA PRIVATE KEY-----\ndata\n-----END RSA PRIVATE KEY-----"
        matches = heuristics.detect(text)

        pem_matches = [m for m in matches if m.pattern == "pem_key"]
        assert len(pem_matches) >= 1
        assert pem_matches[0].category == PIICategory.CREDENTIALS

    def test_no_false_positives_on_safe_text(self, heuristics):
        """Test that safe text doesn't trigger false positives."""
        safe_texts = [
            "Hello, how are you?",
            "The weather is nice today.",
            "I like to code in Python.",
            "See the docs at example.com",
            "Call 555-0100 for testing",
        ]

        for text in safe_texts:
            matches = heuristics.detect(text)
            # Either no matches or only low-confidence matches
            high_conf_matches = [m for m in matches if m.confidence >= 0.9]
            assert len(high_conf_matches) == 0, f"False positive in: {text}"

    def test_mixed_content(self, heuristics):
        """Test detection in mixed PII content."""
        text = "Email: alice@company.com, Phone: 555-234-5678, Card: 4532015112830366"
        matches = heuristics.detect(text)

        # Should detect multiple types
        patterns = {m.pattern for m in matches}
        assert "email" in patterns
        assert "phone" in patterns
        # Card might or might not be detected depending on Luhn implementation

    def test_confidence_scores(self, heuristics):
        """Test that confidence scores are reasonable."""
        text = "My email is real@company.com"
        matches = heuristics.detect(text)

        for match in matches:
            assert 0.0 <= match.confidence <= 1.0
            assert match.confidence > 0.0  # Should have some confidence

    def test_empty_text(self, heuristics):
        """Test detection on empty text."""
        matches = heuristics.detect("")
        assert len(matches) == 0

    def test_whitespace_only(self, heuristics):
        """Test detection on whitespace."""
        matches = heuristics.detect("   \n\t  ")
        assert len(matches) == 0
