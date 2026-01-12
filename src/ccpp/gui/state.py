"""State management for GUI client."""

import os
import time
from threading import RLock
from typing import Optional
from dotenv import load_dotenv
from anthropic import Anthropic

from ccpp.infer.guard import ExchangePIIGuard
from ccpp.infer.stage1_router import Stage1Router
from ccpp.infer.stage2_redactor import Stage2Redactor
from ccpp.infer.heuristics import FastHeuristics
from ccpp.config import load_config, get_stage1_config, get_stage2_config
from ccpp.types import CharClassification, BufferMetadata

# Load environment variables
load_dotenv()


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

        self.guard = ExchangePIIGuard(
            stage1=self.stage1,
            stage2=self.stage2,
            heuristics=self.heuristics,
            stream_break_timeout=config.streaming.stream_break_timeout_ms / 1000.0,
            risk_threshold_high=config.streaming.t_high,
            risk_threshold_low=config.streaming.t_low,
            ema_beta=config.streaming.ema_beta,
        )

        # Store thresholds for easy access
        self.t_high = config.streaming.t_high
        self.t_low = config.streaming.t_low

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
        # Use RLock (reentrant) to allow nested lock acquisition
        # (e.g., check_and_process_buffer -> add_to_conversation)
        self.lock = RLock()

    def reset(self):
        """Reset state for new conversation."""
        with self.lock:
            self.buffer = ""
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
        import logging
        logger = logging.getLogger(__name__)

        with self.lock:
            # Don't process if already processing or no buffer
            if self.is_processing:
                logger.debug("[should_process_buffer] Already processing, returning False")
                return False
            if not self.buffer:
                logger.debug("[should_process_buffer] No buffer, returning False")
                return False

            # Don't process if a classification is still running
            if self.is_classifying:
                logger.debug("[should_process_buffer] Classification in progress, returning False")
                return False

            # Check if buffer already processed
            if self.buffer == self.processed_buffer:
                logger.debug(f"[should_process_buffer] Buffer already processed ('{self.buffer[:30]}...'), returning False")
                return False

            # NOTE: We removed the word-boundary check here. Previously we required
            # buffer[-1].isspace() before processing, but this caused a bug where
            # typing "hello world" (no trailing space) would never trigger stream break.
            # The 3s timeout should fire regardless of whether user ended on a space.

            # Check if enough time has passed
            if self.last_input_time is None:
                logger.debug("[should_process_buffer] No last_input_time, returning False")
                return False

            elapsed = time.time() - self.last_input_time
            should_process = elapsed >= self.stream_break_timeout
            logger.debug(f"[should_process_buffer] elapsed={elapsed:.2f}s, timeout={self.stream_break_timeout}s, should_process={should_process}")
            return should_process
