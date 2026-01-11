#!/usr/bin/env python3
"""Lightweight interactive PII-masked chat client.

A simple, focused client for testing PII masking with real LLM conversations.

Features:
- User input streaming through ExchangePIIGuard
- Real-time risk meter display (P(RISK), EMA, any_risk_in_buffer)
- Masked user input sent to Claude API
- LLM responses streamed back (unmasked for now)
- Conversation history with masking indicators

Usage:
    uv run python scripts/client.py
    uv run python scripts/client.py --timeout 5.0  # Custom user timeout
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from anthropic import Anthropic

from src.ccpp.infer.guard import ExchangePIIGuard
from src.ccpp.infer.stage1_router import Stage1Router
from src.ccpp.infer.stage2_redactor import Stage2Redactor
from src.ccpp.infer.heuristics import FastHeuristics
from src.ccpp.config import load_config, get_stage1_config, get_stage2_config
from src.ccpp.types import ApprovedModel

# Load environment variables
load_dotenv()


class LightweightClient:
    """Lightweight interactive client for PII-masked chat."""

    def __init__(
        self,
        user_timeout: float = 3.0,
        environment: str = "default",
    ):
        """Initialize lightweight client.

        Args:
            user_timeout: Seconds to wait after user stops typing before processing
            environment: Config environment (default, dev, prod)
        """
        self.user_timeout = user_timeout
        self.conversation_history = []

        # Load configuration
        config = load_config(environment=environment)

        # Initialize PII guard components
        print("Initializing PII guard...")
        self.stage1 = Stage1Router(
            llm_config=get_stage1_config(config),
            mock_mode=True  # Use mock mode for now
        )
        self.stage2 = Stage2Redactor(
            llm_config=get_stage2_config(config),
            mock_mode=True  # Use mock mode for now
        )
        self.heuristics = FastHeuristics()

        self.guard = ExchangePIIGuard(
            stage1=self.stage1,
            stage2=self.stage2,
            heuristics=self.heuristics,
            stream_break_timeout=config.streaming.stream_break_timeout_ms / 1000.0,  # Convert ms to seconds
            risk_threshold_high=config.streaming.t_high,
            risk_threshold_low=config.streaming.t_low,
            ema_beta=config.streaming.ema_beta,
        )

        # Initialize Anthropic client
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("⚠️  Warning: ANTHROPIC_API_KEY not found in .env")
            print("   LLM responses will not work. Set your API key in .env")
            self.anthropic = None
        else:
            self.anthropic = Anthropic(api_key=api_key)

        print("✅ Client initialized!\n")

    def print_banner(self):
        """Print welcome banner."""
        print("=" * 70)
        print("  Lightweight PII-Masked Chat Client")
        print("=" * 70)
        print()
        print("How it works:")
        print("  1. Type your message (press SPACE to start typing)")
        print("  2. Press ENTER when done")
        print(f"  3. System waits {self.user_timeout}s for you to continue")
        print("  4. PII is detected and masked in real-time")
        print("  5. Masked message sent to Claude")
        print("  6. Response streamed back")
        print()
        print("Commands:")
        print("  /quit    - Exit the client")
        print("  /clear   - Clear conversation history")
        print("  /history - Show conversation history")
        print()
        print("=" * 70)
        print()

    def display_risk_meter(self, p_risk: float, ema: float, any_risk: bool):
        """Display real-time risk metrics.

        Args:
            p_risk: Current token's P(RISK) probability
            ema: Current EMA risk score
            any_risk: Whether any_risk_in_buffer flag is set
        """
        # Create simple bar charts
        def make_bar(value: float, width: int = 20) -> str:
            filled = int(value * width)
            return "█" * filled + "░" * (width - filled)

        p_risk_bar = make_bar(p_risk)
        ema_bar = make_bar(ema)
        risk_indicator = "🔴 YES" if any_risk else "🟢 NO"

        print(f"┌─ Risk Metrics {'─' * 52}┐")
        print(f"│ P(RISK):    [{p_risk_bar}] {p_risk:.3f} │")
        print(f"│ EMA:        [{ema_bar}] {ema:.3f} │")
        print(f"│ Any Risk:   {risk_indicator:30} │")
        print(f"└{'─' * 68}┘")

    def get_user_input(self) -> Optional[str]:
        """Get user input with space-to-start and timeout detection.

        Returns:
            User message, or None if command like /quit
        """
        print("\n[Press SPACE to start typing, then ENTER when done]")

        # Wait for space to start
        first_char = input().strip()
        if not first_char:
            return ""

        # Handle commands
        if first_char.startswith("/"):
            return first_char

        # Get rest of message
        print("Type your message (press ENTER when done):")
        message = first_char + " " + input()

        return message.strip()

    def process_user_message(self, message: str) -> tuple[str, list]:
        """Process user message through PII guard.

        Args:
            message: Raw user message

        Returns:
            Tuple of (masked_message, events)
        """
        # Reset guard for new message
        self.guard.reset()

        # Stream message character by character
        all_events = []
        masked_text = ""

        print("\n[Processing your message...]")

        for char in message:
            emit_text, events = self.guard.ingest_chunk(char)

            if emit_text:
                masked_text += emit_text

            if events:
                all_events.extend(events)

                # Display risk metrics from latest event
                for event in events:
                    if "risk_score" in event:
                        self.display_risk_meter(
                            p_risk=event.get("risk_score", 0.0),
                            ema=event.get("ema_risk", 0.0),
                            any_risk=event.get("any_risk_in_buffer", False),
                        )

        # Force emit remaining buffer
        final_emit, final_events = self.guard.force_emit()
        if final_emit:
            masked_text += final_emit
        if final_events:
            all_events.extend(final_events)

        return masked_text, all_events

    def get_llm_response(self, conversation_history: list) -> str:
        """Get LLM response from Claude.

        Args:
            conversation_history: List of message dicts

        Returns:
            LLM response text
        """
        if not self.anthropic:
            return "[LLM unavailable - no API key]"

        try:
            print("\n[Waiting for Claude...]")

            response = self.anthropic.messages.create(
                model=ApprovedModel.CLAUDE_HAIKU_4_5.value,
                max_tokens=1024,
                messages=conversation_history,
            )

            return response.content[0].text

        except Exception as e:
            return f"[LLM error: {e}]"

    def display_message(self, role: str, content: str, masked_version: Optional[str] = None):
        """Display a message with proper formatting.

        Args:
            role: Message role (user/assistant)
            content: Message content
            masked_version: If provided, show original was masked
        """
        prefix = "You: " if role == "user" else "Claude: "

        if masked_version and masked_version != content:
            print(f"\n{prefix}{content}")
            print(f"         ↑ (masked from: {masked_version})")
        else:
            print(f"\n{prefix}{content}")

    def run(self):
        """Run the interactive client."""
        self.print_banner()

        while True:
            # Get user input
            user_message = self.get_user_input()

            if user_message is None or not user_message:
                continue

            # Handle commands
            if user_message == "/quit":
                print("\nGoodbye!")
                break
            elif user_message == "/clear":
                self.conversation_history = []
                print("\n✅ Conversation history cleared")
                continue
            elif user_message == "/history":
                print("\n─── Conversation History ───")
                for i, msg in enumerate(self.conversation_history, 1):
                    print(f"{i}. {msg['role']}: {msg['content'][:80]}...")
                print("─" * 30)
                continue
            elif user_message.startswith("/"):
                print(f"Unknown command: {user_message}")
                continue

            # Process through PII guard
            masked_message, events = self.process_user_message(user_message)

            # Display what's being sent
            self.display_message("user", masked_message, user_message if masked_message != user_message else None)

            # Add to conversation history (send masked version)
            self.conversation_history.append({
                "role": "user",
                "content": masked_message,
            })

            # Get LLM response
            assistant_response = self.get_llm_response(self.conversation_history)

            # Display assistant response
            self.display_message("assistant", assistant_response)

            # Add to conversation history
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_response,
            })


def main():
    parser = argparse.ArgumentParser(
        description="Lightweight interactive PII-masked chat client"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="User input timeout in seconds (default: 3.0)",
    )
    parser.add_argument(
        "--env",
        type=str,
        default="default",
        choices=["default", "dev", "prod"],
        help="Configuration environment (default: default)",
    )

    args = parser.parse_args()

    # Create and run client
    client = LightweightClient(
        user_timeout=args.timeout,
        environment=args.env,
    )
    client.run()


if __name__ == "__main__":
    main()
