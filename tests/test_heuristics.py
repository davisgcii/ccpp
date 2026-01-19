"""Tests for fast heuristics module.

Simplified to test only reliable, low-false-positive patterns:
- Email addresses
- API keys (AWS, Stripe, GitHub)
"""

import pytest
from ccpp.infer.heuristics import FastHeuristics
from ccpp.types import PIICategory


class TestFastHeuristics:
    """Tests for FastHeuristics."""

    @pytest.fixture
    def heuristics(self):
        """Create FastHeuristics instance."""
        return FastHeuristics()

    # Email detection tests
    def test_detect_email(self, heuristics):
        """Test email detection."""
        text = "Contact me at john.doe@company.com for details."
        matches = heuristics.detect(text)

        assert len(matches) == 1
        assert matches[0].pattern_name == "email"
        assert matches[0].matched_text == "john.doe@company.com"
        assert matches[0].suggested_category == PIICategory.CONTACT
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

    # AWS key detection tests
    def test_detect_aws_key(self, heuristics):
        """Test AWS access key detection."""
        text = "Key: AKIATESTKEY123456789"  # 20 chars total: AKIA + 16 uppercase alphanumeric
        matches = heuristics.detect(text)

        aws_matches = [m for m in matches if m.pattern_name == "aws_access_key"]
        assert len(aws_matches) >= 1
        assert aws_matches[0].suggested_category == PIICategory.CREDENTIALS
        assert aws_matches[0].confidence == 1.0

    def test_aws_key_allowlist(self, heuristics):
        """Test that example AWS keys are filtered."""
        text = "Example: AKIAIOSFODNN7EXAMPLE"
        matches = heuristics.detect(text)

        # Example key should be filtered
        aws_matches = [m for m in matches if m.pattern_name == "aws_access_key"]
        assert len(aws_matches) == 0

    # Stripe key detection tests
    def test_detect_stripe_key(self, heuristics):
        """Test Stripe key detection."""
        text = "API key: sk_live_abc123xyz789"
        matches = heuristics.detect(text)

        stripe_matches = [m for m in matches if m.pattern_name == "stripe_live_key"]
        assert len(stripe_matches) >= 1
        assert stripe_matches[0].suggested_category == PIICategory.CREDENTIALS
        assert stripe_matches[0].confidence == 1.0

    def test_stripe_test_key_filtered(self, heuristics):
        """Test that Stripe test keys are not matched."""
        text = "Test key: sk_test_abc123"
        matches = heuristics.detect(text)

        # sk_test_ should not match the pattern (only sk_live_)
        stripe_matches = [m for m in matches if m.pattern_name == "stripe_live_key"]
        assert len(stripe_matches) == 0

    # GitHub token detection tests
    def test_detect_github_token(self, heuristics):
        """Test GitHub token detection."""
        text = "Token: ghp_" + "a" * 36
        matches = heuristics.detect(text)

        github_matches = [m for m in matches if m.pattern_name == "github_token"]
        assert len(github_matches) >= 1
        assert github_matches[0].suggested_category == PIICategory.CREDENTIALS
        assert github_matches[0].confidence == 1.0

    # General behavior tests
    def test_no_false_positives_on_safe_text(self, heuristics):
        """Test that safe text doesn't trigger false positives."""
        safe_texts = [
            "Hello, how are you?",
            "The weather is nice today.",
            "I went to the store yesterday.",
            "My favorite number is 42.",
        ]

        for text in safe_texts:
            matches = heuristics.detect(text)
            assert len(matches) == 0, f"False positive on: {text}"

    def test_mixed_content(self, heuristics):
        """Test detection in mixed PII content."""
        text = "Email: alice@company.com, AWS: AKIATEST1234567890AB"
        matches = heuristics.detect(text)

        # Should detect both types
        patterns = {m.pattern_name for m in matches}
        assert "email" in patterns
        assert "aws_access_key" in patterns

    def test_confidence_scores(self, heuristics):
        """Test that confidence scores are reasonable."""
        text = "My email is real@company.com and key AKIATEST1234567890CD"
        matches = heuristics.detect(text)

        # All matches should have high confidence
        assert all(m.confidence >= 0.9 for m in matches)

    def test_empty_text(self, heuristics):
        """Test empty input."""
        matches = heuristics.detect("")
        assert len(matches) == 0

    def test_whitespace_only(self, heuristics):
        """Test whitespace-only input."""
        matches = heuristics.detect("   \n\t  ")
        assert len(matches) == 0
