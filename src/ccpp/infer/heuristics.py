"""Fast heuristic-based PII detection using regex patterns.

This module provides near-zero latency detection of obvious PII patterns
before invoking the ML-based classifiers. Includes allowlist validation to
reduce false positives on test/example data.
"""

import re
from typing import Optional

from ccpp.types import HeuristicMatch, PIICategory


class FastHeuristics:
    """Fast regex-based PII detection with allowlist validation."""

    def __init__(self):
        # Compile regex patterns for efficiency
        self.email_pattern = re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        )
        self.phone_us_pattern = re.compile(
            r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"
        )
        self.ssn_pattern = re.compile(
            r"\b\d{3}-\d{2}-\d{4}\b"
        )
        self.credit_card_pattern = re.compile(
            r"\b\d{13,19}\b"  # 13-19 contiguous digits
        )
        self.aws_key_pattern = re.compile(
            r"\bAKIA[0-9A-Z]{16}\b"
        )
        self.stripe_live_pattern = re.compile(
            r"\bsk_live_[a-zA-Z0-9]+\b"
        )
        self.github_token_pattern = re.compile(
            r"\bghp_[a-zA-Z0-9]{36}\b"
        )
        self.pem_block_pattern = re.compile(
            r"-----BEGIN .* PRIVATE KEY-----"
        )

        # Allowlisted domains (RFC 2606, RFC 6761)
        self.allowed_email_domains = {
            "example.com",
            "example.org",
            "example.net",
            "test",
            "invalid",
            "localhost",
        }

        # Allowlisted phone prefixes (reserved fake numbers)
        self.allowed_phone_prefixes = {
            "555-01",  # 555-0100 through 555-0199
            "555-555",  # 555-555-5555
            "555-12",   # 555-1212 (directory assistance)
            "000-000",  # Obviously fake
            "999-999",  # Obviously fake
            "123-456",  # Obvious placeholder
        }

        # Allowlisted SSN patterns (not issued)
        self.allowed_ssn_patterns = {
            "000-00-0000",
            "999-99-9999",
            "123-45-6789",  # Obvious placeholder
        }

        # Test credit card numbers (from payment processor docs)
        self.test_credit_cards = {
            "4111111111111111",  # Visa test
            "4012888888881881",  # Visa test
            "5500000000000004",  # Mastercard test
            "5555555555554444",  # Mastercard test
            "378282246310005",   # Amex test
            "371449635398431",   # Amex test
            "6011111111111117",  # Discover test
            "6011000990139424",  # Discover test
            "3530111333300000",  # JCB test
        }

        # Allowlisted AWS example keys
        self.allowed_aws_keys = {
            "AKIAIOSFODNN7EXAMPLE",
        }

    def check(self, text: str) -> list[HeuristicMatch]:
        """Run all heuristic detectors on text.

        Args:
            text: Text to scan for PII patterns

        Returns:
            List of detected matches (may be empty)
        """
        matches = []

        # Check each pattern type
        matches.extend(self._check_emails(text))
        matches.extend(self._check_phones(text))
        matches.extend(self._check_ssns(text))
        matches.extend(self._check_credit_cards(text))
        matches.extend(self._check_aws_keys(text))
        matches.extend(self._check_stripe_keys(text))
        matches.extend(self._check_github_tokens(text))
        matches.extend(self._check_pem_blocks(text))

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
        for match in self.email_pattern.finditer(text):
            email = match.group()
            domain = email.split("@")[1].lower()

            # Check if domain is allowlisted
            if self._is_allowed_email_domain(domain):
                continue

            matches.append(
                HeuristicMatch(
                    pattern_name="email",
                    matched_text=email,
                    start=match.start(),
                    end=match.end(),
                    confidence=1.0,
                    suggested_category=PIICategory.PII_DIRECT,
                )
            )
        return matches

    def _is_allowed_email_domain(self, domain: str) -> bool:
        """Check if email domain is allowlisted."""
        domain_lower = domain.lower()

        # Exact match
        if domain_lower in self.allowed_email_domains:
            return True

        # Subdomain of allowed domain
        for allowed in self.allowed_email_domains:
            if domain_lower.endswith(f".{allowed}"):
                return True

        return False

    def _check_phones(self, text: str) -> list[HeuristicMatch]:
        """Detect US phone numbers (with allowlist filtering)."""
        matches = []
        for match in self.phone_us_pattern.finditer(text):
            phone = match.group()

            # Normalize to XXX-XXX-XXXX format for checking
            normalized = re.sub(r"[^0-9]", "", phone)
            normalized = f"{normalized[:3]}-{normalized[3:6]}-{normalized[6:]}"

            # Check if allowlisted
            prefix = normalized[:6]  # First 6 chars (XXX-XX)
            if prefix in self.allowed_phone_prefixes:
                continue

            matches.append(
                HeuristicMatch(
                    pattern_name="phone_us",
                    matched_text=phone,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.9,  # Slightly lower (could be other numbers)
                    suggested_category=PIICategory.PII_DIRECT,
                )
            )
        return matches

    def _check_ssns(self, text: str) -> list[HeuristicMatch]:
        """Detect SSN patterns (with allowlist filtering)."""
        matches = []
        for match in self.ssn_pattern.finditer(text):
            ssn = match.group()

            # Check if allowlisted
            if ssn in self.allowed_ssn_patterns:
                continue

            # Check if starts with 9XX (not issued)
            if ssn.startswith("9"):
                continue

            # Check if middle group is 00 (not issued)
            if ssn[4:6] == "00":
                continue

            matches.append(
                HeuristicMatch(
                    pattern_name="ssn",
                    matched_text=ssn,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.95,
                    suggested_category=PIICategory.PII_DIRECT,
                )
            )
        return matches

    def _check_credit_cards(self, text: str) -> list[HeuristicMatch]:
        """Detect credit card numbers (with Luhn validation and test card filtering)."""
        matches = []
        for match in self.credit_card_pattern.finditer(text):
            card = match.group()

            # Check if it's a test card
            if card in self.test_credit_cards:
                continue

            # Validate with Luhn algorithm
            if not self._luhn_check(card):
                continue

            matches.append(
                HeuristicMatch(
                    pattern_name="credit_card",
                    matched_text=card,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.95,
                    suggested_category=PIICategory.FINANCIAL,
                )
            )
        return matches

    def _luhn_check(self, card_number: str) -> bool:
        """Validate credit card number using Luhn algorithm.

        Args:
            card_number: Card number as string

        Returns:
            True if passes Luhn validation
        """
        digits = [int(d) for d in card_number]
        checksum = 0

        # Process from right to left
        for i, digit in enumerate(reversed(digits)):
            if i % 2 == 1:  # Every second digit from the right
                digit *= 2
                if digit > 9:
                    digit -= 9
            checksum += digit

        return checksum % 10 == 0

    def _check_aws_keys(self, text: str) -> list[HeuristicMatch]:
        """Detect AWS access keys (with example key filtering)."""
        matches = []
        for match in self.aws_key_pattern.finditer(text):
            key = match.group()

            # Check if allowlisted example key
            if key in self.allowed_aws_keys:
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
        for match in self.stripe_live_pattern.finditer(text):
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
        for match in self.github_token_pattern.finditer(text):
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

    def _check_pem_blocks(self, text: str) -> list[HeuristicMatch]:
        """Detect PEM-encoded private keys."""
        matches = []
        for match in self.pem_block_pattern.finditer(text):
            key_header = match.group()

            matches.append(
                HeuristicMatch(
                    pattern_name="pem_private_key",
                    matched_text=key_header,
                    start=match.start(),
                    end=match.end(),
                    confidence=1.0,
                    suggested_category=PIICategory.CREDENTIALS,
                )
            )
        return matches
