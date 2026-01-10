#!/usr/bin/env python3
"""Real-time interactive PII-masked chat client.

A live terminal interface that shows character-by-character PII classification
with real-time risk scores, EMA updates, and masking events.

Usage:
    uv run python scripts/interactive_realtime.py --backend anthropic
    uv run python scripts/interactive_realtime.py --mock
"""

import argparse
import sys
import time
import threading
from pathlib import Path
from typing import Optional
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from blessed import Terminal
from datetime import datetime

from src.ccpp.infer.guard import ExchangePIIGuard
from src.ccpp.infer.stage1_router import Stage1Router
from src.ccpp.infer.stage2_redactor import Stage2Redactor
from src.ccpp.infer.heuristics import FastHeuristics
from src.ccpp.llm.factory import create_backend_from_config
from src.ccpp.llm.base import GenerationConfig


# Load environment variables
load_dotenv()


class RealtimeClient:
    """Real-time interactive chat client with live PII classification."""

    def __init__(
        self,
        stage1_config_path: str,
        stage2_config_path: str,
        llm_backend: str = "anthropic",
        llm_model: str = "claude-3-5-haiku-20241022",
        pause_timeout: float = 3.0,
        mock_mode: bool = False,
    ):
        """Initialize real-time client."""
        self.term = Terminal()
        self.pause_timeout = pause_timeout
        self.mock_mode = mock_mode

        # Load configs
        with open(stage1_config_path) as f:
            self.stage1_config = yaml.safe_load(f)
        with open(stage2_config_path) as f:
            self.stage2_config = yaml.safe_load(f)

        # Initialize guard
        if mock_mode:
            self.stage1 = Stage1Router(mock_mode=True)
            self.stage2 = Stage2Redactor(mock_mode=True)
        else:
            self.stage1 = Stage1Router(llm_config=self.stage1_config, mock_mode=False)
            self.stage2 = Stage2Redactor(llm_config=self.stage2_config, mock_mode=False)

        self.heuristics = FastHeuristics()
        self.guard = ExchangePIIGuard(
            stage1_router=self.stage1,
            stage2_redactor=self.stage2,
            heuristics=self.heuristics,
            stream_break_timeout=pause_timeout,
        )

        # Initialize LLM backend
        llm_config = {"backend": llm_backend, "model_name": llm_model}
        self.llm_backend = create_backend_from_config(llm_config)
        self.llm_gen_config = GenerationConfig(
            max_tokens=2048,
            temperature=0.7,
            do_sample=True,
        )

        # State
        self.conversation = []
        self.current_buffer = ""
        self.last_keystroke_time = None
        self.is_typing = False

        # Metrics
        self.current_risk = 0.0
        self.current_ema = 0.0
        self.is_escalated = False
        self.events = []
        self.masked_count = 0
        self.safe_count = 0

        # Display state
        self.status_message = ""
        self.llm_response = ""
        self.is_llm_responding = False

    def add_event(self, event_type: str, message: str):
        """Add event to log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.events.append(f"[{timestamp}] {event_type}: {message}")
        if len(self.events) > 8:
            self.events.pop(0)

    def draw_ui(self):
        """Draw the UI."""
        print(self.term.home + self.term.clear)

        # Header
        print(self.term.bold + self.term.cyan + "═" * self.term.width)
        title = " PII-Masked Real-Time Chat "
        print(self.term.center(title).rstrip())
        backend_info = f"Classifier: {self.stage1_config.get('backend', 'mock')} | LLM: {self.llm_backend.__class__.__name__}"
        print(self.term.center(backend_info).rstrip())
        print("═" * self.term.width + self.term.normal)
        print()

        # Conversation history (top section)
        print(self.term.bold + "Conversation:" + self.term.normal)
        print("─" * self.term.width)

        # Show last 5 exchanges
        for msg in self.conversation[-10:]:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                print(self.term.cyan + f"You: " + self.term.normal + content)
            else:
                print(self.term.green + f"Assistant: " + self.term.normal + content)
            print()

        # Current LLM response (if generating)
        if self.is_llm_responding:
            print(self.term.green + "Assistant: " + self.term.normal + self.term.italic + "(typing...)" + self.term.normal)
            if self.llm_response:
                print(self.llm_response)
            print()

        print("─" * self.term.width)
        print()

        # Input area
        print(self.term.bold + "Your input:" + self.term.normal)

        # Show buffer with risk coloring
        if self.current_buffer:
            if self.current_risk < 0.3:
                color = self.term.green
            elif self.current_risk < 0.7:
                color = self.term.yellow
            else:
                color = self.term.red

            print(color + self.current_buffer + self.term.normal, end="")

            if self.is_typing:
                print(self.term.bold + "▊" + self.term.normal, end="")  # Cursor

        print()
        print()

        # Metrics panel
        print("─" * self.term.width)

        # Risk metrics in a compact format
        risk_bar = self._create_risk_bar(self.current_risk)
        ema_bar = self._create_risk_bar(self.current_ema)

        escalated_str = self.term.red + "ESCALATED" if self.is_escalated else self.term.dim + "normal"

        metrics_line = (
            f"Risk: {self.current_risk:.2f} {risk_bar} | "
            f"EMA: {self.current_ema:.2f} {ema_bar} | "
            f"State: {escalated_str}{self.term.normal} | "
            f"Masked: {self.masked_count} | Safe: {self.safe_count}"
        )
        print(metrics_line)
        print()

        # Events log
        print(self.term.bold + "Recent Events:" + self.term.normal)
        for event in self.events[-5:]:
            print(self.term.dim + event + self.term.normal)
        print()

        # Footer
        print("─" * self.term.width)
        if self.status_message:
            print(self.term.yellow + self.status_message + self.term.normal)
        else:
            print(self.term.dim + "Type your message. Press ENTER to send, ESC to quit." + self.term.normal)

    def _create_risk_bar(self, value: float) -> str:
        """Create a visual risk bar."""
        bar_length = 10
        filled = int(value * bar_length)

        if value < 0.3:
            color = self.term.green
        elif value < 0.7:
            color = self.term.yellow
        else:
            color = self.term.red

        bar = color + "█" * filled + self.term.dim + "░" * (bar_length - filled) + self.term.normal
        return f"[{bar}]"

    def process_keystroke(self, char: str):
        """Process a keystroke."""
        self.current_buffer += char
        self.last_keystroke_time = time.time()
        self.is_typing = True

        # Stream through guard
        emit_text, events = self.guard.ingest_chunk(char)

        # Process events
        for event in events:
            if event["type"] == "risk_update":
                self.current_risk = event["risk_score"]
                self.current_ema = event["ema_risk"]
                self.is_escalated = event.get("is_escalated", False)
            elif event["type"] == "masked":
                self.masked_count += 1
                original = event.get("original_text", "")[:20]
                masked = event.get("masked_text", "")[:20]
                self.add_event("MASK", f'"{original}..." → "{masked}..."')
            elif event["type"] == "passed":
                self.safe_count += 1
                self.add_event("SAFE", "Buffer passed")

    def finalize_and_send(self):
        """Finalize buffer and send to LLM."""
        if not self.current_buffer.strip():
            return

        # Force emit
        final_text, events = self.guard.force_emit()

        # Process final events
        for event in events:
            if event["type"] == "masked":
                self.masked_count += 1
                self.add_event("MASK", "Final masking applied")

        # Add to conversation
        self.conversation.append({"role": "user", "content": final_text})
        self.add_event("SENT", f"Message sent: {len(final_text)} chars")

        # Clear buffer
        self.current_buffer = ""
        self.is_typing = False

        # Get LLM response
        self.get_llm_response(final_text)

    def get_llm_response(self, user_message: str):
        """Get LLM response (in a thread to avoid blocking UI)."""
        def _generate():
            self.is_llm_responding = True
            self.llm_response = ""
            self.status_message = "Assistant is thinking..."

            try:
                # Stream response
                full_response = ""
                for chunk in self.llm_backend.stream_generate(
                    self.conversation,
                    self.llm_gen_config,
                ):
                    full_response += chunk
                    self.llm_response = full_response
                    self.draw_ui()
                    time.sleep(0.02)  # Small delay for smooth streaming

                # Add to conversation
                self.conversation.append({"role": "assistant", "content": full_response})
                self.add_event("LLM", f"Response: {len(full_response)} chars")

            except Exception as e:
                error_msg = f"Error: {str(e)}"
                self.conversation.append({"role": "assistant", "content": error_msg})
                self.add_event("ERROR", str(e))

            finally:
                self.is_llm_responding = False
                self.llm_response = ""
                self.status_message = ""

        # Run in thread
        threading.Thread(target=_generate, daemon=True).start()

    def run(self):
        """Run the interactive client."""
        with self.term.cbreak(), self.term.hidden_cursor():
            self.status_message = "Ready! Start typing..."
            self.draw_ui()

            while True:
                # Get keystroke (non-blocking with timeout)
                key = self.term.inkey(timeout=0.1)

                if key:
                    # Handle special keys
                    if key.code == self.term.KEY_ESCAPE:
                        break
                    elif key.code == self.term.KEY_ENTER:
                        self.finalize_and_send()
                        # Wait for LLM response to complete
                        while self.is_llm_responding:
                            time.sleep(0.1)
                        self.draw_ui()
                    elif key.code == self.term.KEY_BACKSPACE or key.code == self.term.KEY_DELETE:
                        if self.current_buffer:
                            self.current_buffer = self.current_buffer[:-1]
                            self.draw_ui()
                    elif key.is_sequence:
                        # Ignore other special keys
                        pass
                    else:
                        # Regular character
                        self.process_keystroke(key)
                        self.draw_ui()

                # Check for typing pause
                if self.is_typing and self.last_keystroke_time:
                    if time.time() - self.last_keystroke_time >= self.pause_timeout:
                        self.status_message = f"Pause detected ({self.pause_timeout}s) - finalizing buffer..."
                        self.draw_ui()
                        time.sleep(0.5)
                        # Don't auto-send, just show pause detected
                        self.status_message = "Press ENTER to send, or continue typing..."
                        self.is_typing = False
                        self.draw_ui()

        # Cleanup
        print(self.term.clear)
        print(self.term.normal + "Goodbye!")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Real-time PII-masked chat")
    parser.add_argument(
        "--stage1-config",
        default="configs/stage1_llm.yaml",
        help="Stage 1 config path",
    )
    parser.add_argument(
        "--stage2-config",
        default="configs/stage2_llm.yaml",
        help="Stage 2 config path",
    )
    parser.add_argument(
        "--backend",
        default="anthropic",
        choices=["anthropic", "openai", "ollama"],
        help="LLM backend",
    )
    parser.add_argument("--llm-model", help="LLM model name")
    parser.add_argument(
        "--pause-timeout",
        type=float,
        default=3.0,
        help="Typing pause timeout (seconds)",
    )
    parser.add_argument("--mock", action="store_true", help="Use mock mode")

    args = parser.parse_args()

    # Set default model
    if args.llm_model is None:
        if args.backend == "anthropic":
            args.llm_model = "claude-3-5-haiku-20241022"
        elif args.backend == "openai":
            args.llm_model = "gpt-4o-mini"
        elif args.backend == "ollama":
            args.llm_model = "qwen:4b"

    # Create and run client
    client = RealtimeClient(
        stage1_config_path=args.stage1_config,
        stage2_config_path=args.stage2_config,
        llm_backend=args.backend,
        llm_model=args.llm_model,
        pause_timeout=args.pause_timeout,
        mock_mode=args.mock,
    )

    client.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
