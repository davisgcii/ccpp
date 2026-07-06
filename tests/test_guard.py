"""Tests for ExchangePIIGuard streaming orchestration (PR4).

Exercises the previously-untested core: the hold-back buffer, the overlap tail
that catches boundary-split PII, the stream-break emit (including the
trailing-pause path), and the split of emit into evaluate/flush that lets a GUI
review panel approve spans before masking.
"""

import time

from ccpp.infer.guard import EmitDecision, ExchangePIIGuard
from ccpp.infer.heuristics import FastHeuristics
from ccpp.types import MaskSpan, PIICategory, RedactorOutput, RiskScore


class FakeStage1:
    """Deterministic Stage 1: always returns the configured score."""

    def __init__(self, score: float = 0.0):
        self.score = score

    def classify(self, messages, text) -> RiskScore:
        return RiskScore(score=self.score)


class FakeStage2:
    """Deterministic Stage 2: masks configured entities that appear in the window."""

    def __init__(self, entities=None):
        # list of (entity_text, PIICategory)
        self._entities = entities or []

    def redact(self, messages, window) -> RedactorOutput:
        spans = [
            MaskSpan(entity_text=e, category=c)
            for e, c in self._entities
            if e in window
        ]
        return RedactorOutput(spans=spans)


def make_guard(score=0.0, entities=None, **kwargs):
    return ExchangePIIGuard(
        stage1=FakeStage1(score),
        stage2=FakeStage2(entities),
        heuristics=FastHeuristics(),
        risk_threshold_immediate=0.7,
        stream_break_timeout=2.0,
        **kwargs,
    )


class TestBuffering:
    def test_chunks_accumulate_without_emitting(self):
        guard = make_guard(score=0.0)
        emit, _ = guard.ingest_chunk("hello ")
        assert emit == ""
        emit, _ = guard.ingest_chunk("there ")
        assert emit == ""
        assert guard.buffer.raw_text == "hello there "

    def test_force_emit_passes_safe_text(self):
        guard = make_guard(score=0.0)
        guard.ingest_chunk("just a normal sentence ")
        emit, events = guard.force_emit()
        assert emit == "just a normal sentence "
        assert any(e["type"] == "passed" for e in events)
        assert guard.buffer.raw_text == ""

    def test_force_emit_masks_when_risk_high(self):
        guard = make_guard(score=0.9, entities=[("john@x.com", PIICategory.CONTACT)])
        guard.ingest_chunk("email john@x.com ")
        emit, events = guard.force_emit()
        assert "john@x.com" not in emit
        assert "[CONTACT]" in emit
        assert any(e["type"] == "masked" for e in events)


class TestNoOverlap:
    """The overlap tail was removed: each buffer is evaluated on its own text;
    cross-buffer risk continuity is carried by the EMA, not by retained text."""

    def test_flush_retains_no_text(self):
        guard = make_guard(score=0.9, entities=[("a@b.com", PIICategory.CONTACT)])
        guard.ingest_chunk("mail a@b.com")
        guard.force_emit()
        assert guard.buffer.raw_text == ""
        assert not hasattr(guard.buffer, "overlap_tail")

    def test_next_buffer_evaluated_on_its_own_text(self):
        guard = make_guard(score=0.9, entities=[("415-555-0147", PIICategory.CONTACT)])
        guard.ingest_chunk("call me at 415-555")
        guard.force_emit()
        guard.ingest_chunk("-0147 thanks")
        decision = guard.evaluate_buffer()
        # Stage 2 sees only the current buffer — no prior text spliced in.
        assert decision.text == "-0147 thanks"

    def test_ema_persists_across_flush(self):
        """EMA carries cross-buffer risk continuity (not reset on flush)."""
        guard = make_guard(score=0.9)
        guard.ingest_chunk("my ssn is 123")
        ema_before = guard.risk_state.ema_risk
        assert ema_before > 0
        guard.force_emit()
        assert guard.risk_state.ema_risk == ema_before


class TestStreamBreak:
    def test_auto_emit_on_next_chunk_after_pause(self):
        guard = make_guard(score=0.0)
        guard.ingest_chunk("first utterance ")
        # Simulate a pause longer than the timeout.
        guard.last_token_time = time.time() - 5.0
        emit, events = guard.ingest_chunk("second")
        assert emit == "first utterance "
        assert any(e["type"] == "stream_break" for e in events)

    def test_poll_stream_break_fires_on_trailing_pause(self):
        """The trailing-pause fix: no further chunk, poll still emits."""
        guard = make_guard(score=0.0)
        guard.ingest_chunk("trailing utterance ")
        guard.last_token_time = time.time() - 5.0
        emit, events = guard.poll_stream_break()
        assert emit == "trailing utterance "
        assert any(e["type"] == "stream_break" for e in events)
        assert guard.buffer.raw_text == ""

    def test_poll_does_nothing_before_timeout(self):
        guard = make_guard(score=0.0)
        guard.ingest_chunk("recent ")
        emit, events = guard.poll_stream_break()
        assert emit == ""
        assert guard.buffer.raw_text == "recent "

    def test_check_stream_break_false_suppresses_auto_emit(self):
        """GUI path: caller owns the emit trigger, no auto-emit on pause."""
        guard = make_guard(score=0.0)
        guard.ingest_chunk("first ", check_stream_break=False)
        guard.last_token_time = time.time() - 5.0
        emit, _ = guard.ingest_chunk("second", check_stream_break=False)
        assert emit == ""
        assert guard.buffer.raw_text == "first second"


class TestEvaluateFlushFlow:
    def test_evaluate_does_not_flush(self):
        guard = make_guard(score=0.9, entities=[("a@b.com", PIICategory.CONTACT)])
        guard.ingest_chunk("mail a@b.com ")
        decision = guard.evaluate_buffer()
        assert isinstance(decision, EmitDecision)
        assert decision.should_mask
        # Buffer is untouched — caller can show a review panel first.
        assert guard.buffer.raw_text == "mail a@b.com "

    def test_flush_emitted_clears_buffer(self):
        guard = make_guard(score=0.9, entities=[("a@b.com", PIICategory.CONTACT)])
        guard.ingest_chunk("mail a@b.com ")
        guard.evaluate_buffer()
        guard.flush_emitted()
        assert guard.buffer.raw_text == ""
        assert guard.any_risk_in_buffer is False

    def test_evaluate_safe_when_low_risk(self):
        guard = make_guard(score=0.0)
        guard.ingest_chunk("nothing sensitive ")
        decision = guard.evaluate_buffer()
        assert decision.should_mask is False
        assert decision.redactor_output is None
