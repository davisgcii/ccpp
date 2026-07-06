"""Tests for the shared PII pattern/allowlist module (PR3).

These lock in that FastHeuristics and the Stage 2 mock redactor share one source
of truth, so they cannot drift apart the way they previously had (e.g. the
"invalid" domain was allowlisted by heuristics but not by the Stage 2 mock).
"""

from ccpp.infer import patterns
from ccpp.infer.heuristics import FastHeuristics
from ccpp.infer.stage2_redactor import Stage2Redactor


class TestAllowedEmailDomain:
    def test_exact_allowlisted(self):
        assert patterns.is_allowed_email_domain("example.com")
        assert patterns.is_allowed_email_domain("localhost")
        assert patterns.is_allowed_email_domain("invalid")

    def test_subdomain_allowlisted(self):
        assert patterns.is_allowed_email_domain("mail.example.com")

    def test_real_domain_not_allowlisted(self):
        assert not patterns.is_allowed_email_domain("company.com")
        # bare "test" is allowlisted, but "test.com" is a real domain
        assert not patterns.is_allowed_email_domain("test.com")

    def test_case_insensitive(self):
        assert patterns.is_allowed_email_domain("Example.COM")


class TestConsumersAgree:
    """The two consumers must reach the same email-allowlisting decision."""

    def _heuristics_flags(self, text: str) -> bool:
        return any(m.pattern_name == "email" for m in FastHeuristics().detect(text))

    def _stage2_flags(self, text: str) -> bool:
        redactor = Stage2Redactor(mock_mode=True)
        return any(s.category.value == "contact" and "@" in s.entity_text
                   for s in redactor.redact([], text).spans)

    def test_agreement_across_domains(self):
        cases = {
            "reach me at a@company.com": True,      # real domain → flagged by both
            "docs use a@example.com here": False,   # allowlisted → skipped by both
            "ping a@x.invalid please": False,       # regression: both now skip "invalid"
            "mail a@mail.example.com now": False,    # subdomain of allowlisted
        }
        for text, expected in cases.items():
            assert self._heuristics_flags(text) == expected, text
            assert self._stage2_flags(text) == expected, text
