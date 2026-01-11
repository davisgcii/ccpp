"""State management for GUI client."""

import os
import time
from threading import Lock
from dotenv import load_dotenv
from anthropic import Anthropic

from ccpp.infer.guard import ExchangePIIGuard
from ccpp.infer.stage1_router import Stage1Router
from ccpp.infer.stage2_redactor import Stage2Redactor
from ccpp.infer.heuristics import FastHeuristics
from ccpp.config import load_config, get_stage1_config, get_stage2_config

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
            mock_mode=True,  # Use mock mode for now
        )
        self.stage2 = Stage2Redactor(
            llm_config=get_stage2_config(config),
            mock_mode=True,  # Use mock mode for now
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
        self.risk_history = []  # [(char_idx, p_risk, ema, any_risk), ...]
        self.conversation = []
        self.last_input_time = None
        self.processed_buffer = ""  # Last buffer sent to LLM
        self.is_processing = False  # Currently processing/waiting for LLM
        self.should_interrupt = False  # User typed during LLM response

        # Thread safety for concurrent Gradio events
        self.lock = Lock()

    def reset(self):
        """Reset state for new conversation."""
        with self.lock:
            self.buffer = ""
            self.risk_history = []
            self.conversation = []
            self.last_input_time = None
            self.processed_buffer = ""
            self.is_processing = False
            self.should_interrupt = False
            self.guard.reset()

    def should_process_buffer(self) -> bool:
        """Check if buffer should be processed (stream break detected).

        Returns:
            True if stream break timeout reached and buffer not yet processed
        """
        with self.lock:
            # Don't process if already processing or no buffer
            if self.is_processing or not self.buffer:
                return False

            # Check if buffer already processed
            if self.buffer == self.processed_buffer:
                return False

            # Check if enough time has passed
            if self.last_input_time is None:
                return False

            elapsed = time.time() - self.last_input_time
            return elapsed >= self.stream_break_timeout
