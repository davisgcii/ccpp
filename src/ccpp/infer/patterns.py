"""Shared regex patterns and allowlists for PII detection.

Single source of truth used by both :class:`~ccpp.infer.heuristics.FastHeuristics`
(the pre-Stage-1 fast path) and the Stage 2 mock redactor. Keeping these here
avoids the two modules drifting apart (they previously defined overlapping
email/phone/SSN/key patterns with subtly different allowlists).
"""

import re

# -----------------------------------------------------------------------------
# Patterns
# -----------------------------------------------------------------------------

EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

AWS_ACCESS_KEY = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
STRIPE_LIVE_KEY = re.compile(r"\bsk_live_[a-zA-Z0-9]+\b")
GITHUB_TOKEN = re.compile(r"\bghp_[a-zA-Z0-9]{36}\b")

# Combined key pattern for callers (Stage 2 mock) that scan for any API key in
# one pass rather than per-provider.
API_KEY = re.compile(r"\b(sk_live_[a-zA-Z0-9]+|AKIA[0-9A-Z]{16}|ghp_[a-zA-Z0-9]{36})\b")

# -----------------------------------------------------------------------------
# Allowlists (documentation / test / placeholder values that must not be flagged)
# -----------------------------------------------------------------------------

# RFC 2606 / RFC 6761 reserved domains plus common placeholders.
ALLOWED_EMAIL_DOMAINS = frozenset(
    {"example.com", "example.org", "example.net", "test", "invalid", "localhost"}
)

# AWS documentation example access key.
ALLOWED_AWS_KEYS = frozenset({"AKIAIOSFODNN7EXAMPLE"})

# Obvious placeholder phone prefixes (555-01XX reserved for fiction, etc.).
TEST_PHONE_PREFIXES = ("555-01", "555-555", "000-", "999-", "123-")

# Obvious placeholder SSNs.
TEST_SSNS = frozenset({"000-00-0000", "999-99-9999", "123-45-6789"})


def is_allowed_email_domain(domain: str) -> bool:
    """Return True if ``domain`` is an allowlisted (non-PII) email domain.

    Matches exact allowlisted domains and any subdomain of one
    (e.g. ``mail.example.com``).
    """
    domain_lower = domain.lower()
    if domain_lower in ALLOWED_EMAIL_DOMAINS:
        return True
    return any(domain_lower.endswith(f".{allowed}") for allowed in ALLOWED_EMAIL_DOMAINS)
