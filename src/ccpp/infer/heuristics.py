"""Fast heuristic-based PII detection using regex patterns.

This module provides near-zero latency detection of obvious PII patterns
before invoking the ML-based classifiers. Focused on simple, reliable patterns:
- Email addresses
- API keys (AWS, Stripe, GitHub)

More complex patterns (phones, SSNs, credit cards) are left to ML classifiers.
"""

from ccpp.infer import patterns
from ccpp.types import HeuristicMatch, PIICategory


class FastHeuristics:
    """Fast regex-based PII detection with allowlist validation.

    Focuses on simple, reliable patterns with low false positive rates.
    Patterns and allowlists are shared with the Stage 2 mock redactor via
    :mod:`ccpp.infer.patterns`.
    """

    def detect(self, text: str) -> list[HeuristicMatch]:
        """Run all heuristic detectors on text.

        Args:
            text: Text to scan for PII patterns

        Returns:
            List of detected matches (may be empty)
        """
        matches = []

        # Check simple, reliable patterns only
        matches.extend(self._check_emails(text))
        matches.extend(self._check_aws_keys(text))
        matches.extend(self._check_stripe_keys(text))
        matches.extend(self._check_github_tokens(text))

        return matches

    def has_strong_match(self, matches: list[HeuristicMatch]) -> bool:
        """Return True if any match is high-confidence.

        Args:
            matches: List of heuristic matches

        Returns:
            True if at least one match has confidence >= 0.9
        """
        return any(m.confidence >= 0.9 for m in matches)

    def _check_emails(self, text: str) -> list[HeuristicMatch]:
        """Detect email addresses (with allowlist filtering)."""
        matches = []
        for match in patterns.EMAIL.finditer(text):
            email = match.group()
            domain = email.split("@")[1].lower()

            # Check if domain is allowlisted
            if patterns.is_allowed_email_domain(domain):
                continue

            matches.append(
                HeuristicMatch(
                    pattern_name="email",
                    matched_text=email,
                    start=match.start(),
                    end=match.end(),
                    confidence=1.0,
                    suggested_category=PIICategory.CONTACT,
                )
            )
        return matches

    def _check_aws_keys(self, text: str) -> list[HeuristicMatch]:
        """Detect AWS access keys (with example key filtering)."""
        matches = []
        for match in patterns.AWS_ACCESS_KEY.finditer(text):
            key = match.group()

            # Check if allowlisted example key
            if key in patterns.ALLOWED_AWS_KEYS:
                continue

            matches.append(
                HeuristicMatch(
                    pattern_name="aws_access_key",
                    matched_text=key,
                    start=match.start(),
                    end=match.end(),
                    confidence=1.0,
                    suggested_category=PIICategory.CREDENTIALS,
                )
            )
        return matches

    def _check_stripe_keys(self, text: str) -> list[HeuristicMatch]:
        """Detect Stripe live API keys (test keys are allowed)."""
        matches = []
        for match in patterns.STRIPE_LIVE_KEY.finditer(text):
            key = match.group()

            matches.append(
                HeuristicMatch(
                    pattern_name="stripe_live_key",
                    matched_text=key,
                    start=match.start(),
                    end=match.end(),
                    confidence=1.0,
                    suggested_category=PIICategory.CREDENTIALS,
                )
            )
        return matches

    def _check_github_tokens(self, text: str) -> list[HeuristicMatch]:
        """Detect GitHub personal access tokens."""
        matches = []
        for match in patterns.GITHUB_TOKEN.finditer(text):
            token = match.group()

            matches.append(
                HeuristicMatch(
                    pattern_name="github_token",
                    matched_text=token,
                    start=match.start(),
                    end=match.end(),
                    confidence=1.0,
                    suggested_category=PIICategory.CREDENTIALS,
                )
            )
        return matches
