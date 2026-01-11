"""Exchange PII Guard: Main orchestrator for streaming PII detection and masking.

This module coordinates the fast heuristics, Stage 1 router, and Stage 2 redactor
to provide continuous PII monitoring with masking at stream breaks.
"""

import time
from typing import Optional

from ccpp.types import HoldbackBuffer, RiskState
from ccpp.infer.heuristics import FastHeuristics
from ccpp.infer.stage1_router import Stage1Router
from ccpp.infer.stage2_redactor import Stage2Redactor


class ExchangePIIGuard:
    """Main orchestrator for streaming PII detection and masking.

    Continuously monitors streaming text, tracks risk with EMA smoothing,
    and applies masking at stream breaks when PII is detected.
    """

    def __init__(
        self,
        stage1: Optional[Stage1Router] = None,
        stage2: Optional[Stage2Redactor] = None,
        heuristics: Optional[FastHeuristics] = None,
        stream_break_timeout: float = 0.5,  # seconds
        risk_threshold_high: float = 0.6,
        risk_threshold_low: float = 0.3,
        risk_threshold_immediate: float = 0.7,  # For any_risk_in_buffer flag
        ema_beta: float = 0.85,
        reset_ema_on_stream_break: bool = False,  # Default: let EMA decay naturally
    ):
        """Initialize the PII guard.

        Args:
            stage1: Stage 1 router (creates default if None)
            stage2: Stage 2 redactor (creates default if None)
            heuristics: Fast heuristics (creates default if None)
            stream_break_timeout: Seconds of silence before emitting buffer
            risk_threshold_high: EMA threshold for escalation (T_high)
            risk_threshold_low: EMA threshold for de-escalation (T_low)
            risk_threshold_immediate: Individual token score that sets any_risk_flag
            ema_beta: EMA smoothing factor (higher = more smoothing)
            reset_ema_on_stream_break: If False (default), EMA decays naturally across breaks;
                                       if True, reset EMA to 0.0 after each utterance
        """
        # Initialize components (use mocks if not provided)
        self.stage1 = stage1 or Stage1Router(mock_mode=True)
        self.stage2 = stage2 or Stage2Redactor(mock_mode=True)
        self.heuristics = heuristics or FastHeuristics()

        # Configuration
        self.stream_break_timeout = stream_break_timeout
        self.risk_threshold_immediate = risk_threshold_immediate
        self.reset_ema_on_stream_break = reset_ema_on_stream_break

        # State
        self.buffer = HoldbackBuffer(max_overlap=64)
        self.risk_state = RiskState(
            beta=ema_beta,
            t_high=risk_threshold_high,
            t_low=risk_threshold_low,
        )
        self.messages: list[dict] = []  # Conversation history
        self.last_token_time: Optional[float] = None
        self.any_risk_in_buffer = False  # Track if any high-risk token in current buffer

    def ingest_chunk(self, text: str) -> tuple[str, list[dict]]:
        """Ingest new text chunk from stream.

        This is the main entry point for streaming text. Call this repeatedly
        with new chunks as they arrive.

        Args:
            text: New text chunk (can be single char, word, or sentence)

        Returns:
            Tuple of (emit_text, events):
            - emit_text: Masked text to emit (empty string if nothing to emit yet)
            - events: List of event dicts (e.g., {"type": "risk_escalated", "ema": 0.75})
        """
        events = []

        # 1. Append to buffer
        self.buffer.append(text)
        self.last_token_time = time.time()

        # 2. Run fast heuristics
        matches = self.heuristics.detect(self.buffer.raw_text)
        strong_match = self.heuristics.has_strong_match(matches)

        if strong_match:
            events.append({
                "type": "heuristic_match",
                "matches": [m.pattern_name for m in matches],
            })

        # 3. Run Stage 1 (per-token risk classification)
        risk = self.stage1.classify(self.messages, self.buffer.raw_text)
        is_escalated = self.risk_state.update(risk.score)

        # Track if any high-risk token in current buffer
        if risk.score >= self.risk_threshold_immediate:
            self.any_risk_in_buffer = True

        events.append({
            "type": "risk_update",
            "raw_risk": risk.score,
            "ema_risk": self.risk_state.ema_risk,
            "is_escalated": is_escalated,
        })

        # 4. Check for stream break
        if not self._check_stream_break():
            # No stream break yet, keep accumulating
            return ("", events)

        # Stream break detected!
        events.append({"type": "stream_break"})

        # 5. Masking decision (three conditions)
        should_mask = (
            self.any_risk_in_buffer
            or is_escalated
            or strong_match
        )

        if should_mask:
            # Run Stage 2 to extract entities
            window = self.buffer.get_window_with_overlap()
            redactor_output = self.stage2.redact(self.messages, window)

            # Apply masks
            masked = redactor_output.apply_masks(
                self.buffer.raw_text,
                mask_format="[{type}]"
            )

            events.append({
                "type": "masked",
                "num_entities": len(redactor_output.spans),
                "entities": [
                    {"text": s.entity_text, "category": s.category.value}
                    for s in redactor_output.spans
                ],
            })
        else:
            # No masking needed
            masked = self.buffer.raw_text
            events.append({"type": "passed"})

        # 6. Emit and reset
        emit_text = masked
        self.buffer.flush(keep_overlap=True)
        self.any_risk_in_buffer = False  # Always reset flag

        if self.reset_ema_on_stream_break:
            # Option A: Full reset (recommended)
            self.risk_state = RiskState(
                beta=self.risk_state.beta,
                t_high=self.risk_state.t_high,
                t_low=self.risk_state.t_low,
            )
        else:
            # Option B: Let decay naturally (for testing)
            self.risk_state.consecutive_high = 0
            self.risk_state.is_escalated = False

        return (emit_text, events)

    def _check_stream_break(self) -> bool:
        """Check if stream break timeout has been reached.

        Returns:
            True if enough time has elapsed since last token
        """
        if self.last_token_time is None:
            return False

        elapsed = time.time() - self.last_token_time
        return elapsed >= self.stream_break_timeout

    def force_emit(self) -> tuple[str, list[dict]]:
        """Force emission of current buffer (e.g., at end of conversation).

        This is useful when the stream ends without a natural break.

        Returns:
            Tuple of (emit_text, events)
        """
        if len(self.buffer) == 0:
            return ("", [])

        events = []
        events.append({"type": "force_emit"})

        # Run heuristics
        matches = self.heuristics.detect(self.buffer.raw_text)
        strong_match = self.heuristics.has_strong_match(matches)

        # Check current risk state
        is_escalated = self.risk_state.is_escalated

        # Masking decision
        should_mask = (
            self.any_risk_in_buffer
            or is_escalated
            or strong_match
        )

        if should_mask:
            # Run Stage 2
            window = self.buffer.get_window_with_overlap()
            redactor_output = self.stage2.redact(self.messages, window)
            masked = redactor_output.apply_masks(
                self.buffer.raw_text,
                mask_format="[{type}]"
            )
            events.append({
                "type": "masked",
                "num_entities": len(redactor_output.spans),
                "entities": [
                    {"text": s.entity_text, "category": s.category.value}
                    for s in redactor_output.spans
                ],
            })
        else:
            masked = self.buffer.raw_text
            events.append({"type": "passed"})

        # Reset
        emit_text = masked
        self.buffer.flush(keep_overlap=True)
        self.any_risk_in_buffer = False

        if self.reset_ema_on_stream_break:
            self.risk_state = RiskState(
                beta=self.risk_state.beta,
                t_high=self.risk_state.t_high,
                t_low=self.risk_state.t_low,
            )
        else:
            self.risk_state.consecutive_high = 0
            self.risk_state.is_escalated = False

        return (emit_text, events)

    def add_user_message(self, content: str):
        """Add user message to conversation history.

        Call this when the user sends a complete message.

        Args:
            content: User message content
        """
        self.messages.append({"role": "user", "content": content})

    def finalize_assistant_message(self, content: str):
        """Add complete assistant message to history.

        Call this after all assistant chunks have been processed and emitted.

        Args:
            content: Complete assistant message (after masking)
        """
        self.messages.append({"role": "assistant", "content": content})

    def reset(self):
        """Reset guard state (for new conversation)."""
        self.buffer = HoldbackBuffer(max_overlap=64)
        self.risk_state = RiskState(
            beta=self.risk_state.beta,
            t_high=self.risk_state.t_high,
            t_low=self.risk_state.t_low,
        )
        self.messages = []
        self.last_token_time = None
        self.any_risk_in_buffer = False
