"""State management for GUI client."""

import logging
import os
import time
from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv

from ccpp.config import get_masking_config, get_stage1_config, get_stage2_config, load_config
from ccpp.gui.instrumented_lock import InstrumentedRLock
from ccpp.infer.guard import ExchangePIIGuard
from ccpp.infer.heuristics import FastHeuristics
from ccpp.infer.stage1_router import Stage1Router
from ccpp.infer.stage2_redactor import Stage2Redactor
from ccpp.types import BufferMetadata, CharClassification

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class PIIClientState:
    """Manages state for the interactive PII GUI client.

    This class maintains all state for the Gradio application, including:
    - User input buffer and timing
    - Risk history for visualization
    - Conversation history
    - PII guard components
    - LLM client

    Thread-safe for use in Gradio's concurrent event handling.
    """

    def __init__(
        self,
        stream_break_timeout: float = 3.0,
        environment: str = "default",
    ):
        """Initialize client state.

        Args:
            stream_break_timeout: Seconds to wait before processing buffer
            environment: Config environment (default, dev, prod)
        """
        self.stream_break_timeout = stream_break_timeout

        # Load configuration
        config = load_config(environment=environment)

        # Initialize PII guard components
        self.stage1 = Stage1Router(
            llm_config=get_stage1_config(config),
            mock_mode=False,  # Use real qwen3:1.7b model
        )
        self.stage2 = Stage2Redactor(
            llm_config=get_stage2_config(config),
            mock_mode=False,  # Use real qwen3:1.7b model
        )
        self.heuristics = FastHeuristics()

        # Warm up both models so the first real request isn't slow. MLX compiles
        # Metal kernels lazily on first use; Stage 2's generate path is only
        # exercised on the first send, so without this the first masked message
        # pays a ~20s compilation cost. Doing it here moves that to startup.
        self._warmup()

        self.guard = ExchangePIIGuard(
            stage1=self.stage1,
            stage2=self.stage2,
            heuristics=self.heuristics,
            stream_break_timeout=config.streaming.stream_break_timeout_ms / 1000.0,
            risk_threshold_high=config.streaming.t_high,
            risk_threshold_low=config.streaming.t_low,
            risk_threshold_immediate=config.streaming.get("risk_threshold", 0.7),
            ema_beta=config.streaming.ema_beta,
        )

        # Store thresholds for easy access
        self.t_high = config.streaming.t_high
        self.t_low = config.streaming.t_low

        # Masking-output settings (single source shared by all masking call sites)
        self.masking = get_masking_config(config)

        # Initialize Anthropic client
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("⚠️  Warning: ANTHROPIC_API_KEY not found in .env")
            print("   LLM responses will not work.")
            self.anthropic = None
        else:
            self.anthropic = Anthropic(api_key=api_key)

        # State variables
        self.buffer = ""
        # Append-only input model: text committed (through the last space) and
        # locked from editing. Space commits the current token.
        self.committed_text = ""
        self.risk_history = []  # [(char_idx, p_risk, ema, any_risk), ...] for current buffer
        self.archived_risk_history = []  # Historical data from previous buffers for smooth chart transitions
        self.conversation = []  # Enhanced with metadata field
        self.last_input_time = None
        self.processed_buffer = ""  # Last buffer sent to LLM
        self.is_processing = False  # Currently processing/waiting for LLM
        self.should_interrupt = False  # User typed during LLM response
        self.last_classified_len = 0  # Length of buffer when we last classified
        self.is_classifying = False  # Currently running Stage 1 classification

        # GUI debugging metadata (for hover tooltips)
        self.current_char_data: list[CharClassification] = []  # Per-char for current buffer
        self.current_buffer_metadata: Optional[BufferMetadata] = None  # For current buffer

        # History size limit (keep last N exchanges)
        self.max_history_exchanges = 30

        # Thread safety for concurrent Gradio events
        # Use InstrumentedRLock for debugging race conditions
        # (logs contention and long holds - see docs/stream.md)
        self.lock = InstrumentedRLock("state")

        # Timer state tracking (for reduced logging)
        self._last_should_process_reason: Optional[str] = None
        self._tick_count = 0

        # Pending classification queue: list of (space_position, text_snapshot, conversation_snapshot)
        # Classifications are queued by on_user_type and processed by timer
        self.pending_classifications: list[tuple[int, str, list]] = []

    def _warmup(self) -> None:
        """Run one throwaway inference per stage to trigger MLX kernel
        compilation at startup instead of on the first user request."""
        try:
            t = time.time()
            self.stage1.classify([], "warmup")
            self.stage2.redact([], "warmup name is Jane Doe")
            logger.info(f"[warmup] models warmed in {time.time() - t:.1f}s")
        except Exception as e:
            logger.warning(f"[warmup] failed (first request may be slow): {e}")

    def reset(self):
        """Reset state for new conversation."""
        with self.lock:
            self.buffer = ""
            self.committed_text = ""
            self.risk_history = []
            self.archived_risk_history = []
            self.conversation = []
            self.last_input_time = None
            self.processed_buffer = ""
            self.is_processing = False
            self.should_interrupt = False
            self.last_classified_len = 0
            self.is_classifying = False
            self.current_char_data = []
            self.current_buffer_metadata = None
            self.pending_classifications = []
            self.guard.reset()

    def add_to_conversation(self, message: dict):
        """Add message to conversation and prune old history.

        Args:
            message: Message dict with role, content, and optional metadata
        """
        with self.lock:
            self.conversation.append(message)

            # Prune old history to prevent unbounded growth
            if len(self.conversation) > self.max_history_exchanges * 2:  # user+assistant pairs
                self.conversation = self.conversation[-self.max_history_exchanges * 2:]

    def should_process_buffer(self) -> bool:
        """Check if buffer should be processed (stream break detected).

        Returns:
            True if stream break timeout reached and buffer not yet processed
        """
        from ccpp.logging_config import TRACE

        self._tick_count += 1

        with self.lock:
            # Determine reason for not processing (if any)
            reason = None

            if self.is_processing:
                reason = "processing"
            elif not self.buffer:
                reason = "no_buffer"
            elif self.is_classifying:
                reason = "classifying"
            elif self.pending_classifications:
                reason = "pending_classifications"
            elif self.buffer == self.processed_buffer:
                reason = "already_processed"
            elif self.last_input_time is None:
                reason = "no_input_time"
            else:
                elapsed = time.time() - self.last_input_time
                if elapsed < self.stream_break_timeout:
                    reason = "waiting"

            # Only log on state transitions or every 20 ticks (10s at 500ms interval)
            if reason != self._last_should_process_reason:
                if reason:
                    logger.log(TRACE, f"[timer] state={reason} buf_len={len(self.buffer)}")
                self._last_should_process_reason = reason
            elif self._tick_count % 20 == 0 and reason:
                # Periodic heartbeat when idle
                elapsed = time.time() - self.last_input_time if self.last_input_time else 0
                logger.log(TRACE, f"[timer] heartbeat: state={reason} buf_len={len(self.buffer)} idle={elapsed:.1f}s")

            # NOTE: We removed the word-boundary check here. Previously we required
            # buffer[-1].isspace() before processing, but this caused a bug where
            # typing "hello world" (no trailing space) would never trigger stream break.
            # The 3s timeout should fire regardless of whether user ended on a space.

            return reason is None
