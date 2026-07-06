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


class TestOverlapTail:
    def test_overlap_catches_boundary_split_entity(self):
        """A phone split across two utterances is detected via the overlap tail."""
        guard = make_guard(score=0.9, entities=[("415-555-0147", PIICategory.CONTACT)])

        # First utterance ends mid-number; emit so it flushes but retains overlap.
        guard.ingest_chunk("call me at 415-555")
        guard.force_emit()
        assert guard.buffer.overlap_tail  # tail retained

        # Second utterance completes the number.
        guard.ingest_chunk("-0147 thanks")
        decision = guard.evaluate_buffer()

        # The window spans the boundary and Stage 2 sees the full number...
        assert "415-555-0147" in decision.window
        assert any(s.entity_text == "415-555-0147" for s in decision.redactor_output.spans)

    def test_without_overlap_the_split_is_not_detected(self):
        """Control: the raw second buffer alone does not contain the entity."""
        guard = make_guard(score=0.9, entities=[("415-555-0147", PIICategory.CONTACT)])
        guard.ingest_chunk("-0147 thanks")  # no prior context/overlap
        decision = guard.evaluate_buffer()
        assert "415-555-0147" not in decision.window


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

    def test_flush_emitted_clears_buffer_and_keeps_overlap(self):
        guard = make_guard(score=0.9, entities=[("a@b.com", PIICategory.CONTACT)])
        guard.ingest_chunk("mail a@b.com ")
        guard.evaluate_buffer()
        guard.flush_emitted()
        assert guard.buffer.raw_text == ""
        assert guard.buffer.overlap_tail == "mail a@b.com "
        assert guard.any_risk_in_buffer is False

    def test_evaluate_safe_when_low_risk(self):
        guard = make_guard(score=0.0)
        guard.ingest_chunk("nothing sensitive ")
        decision = guard.evaluate_buffer()
        assert decision.should_mask is False
        assert decision.redactor_output is None
