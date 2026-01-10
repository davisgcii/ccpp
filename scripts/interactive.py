#!/usr/bin/env python3
"""Interactive PII-masked chat client.

A real-time terminal interface for chatting with an LLM while streaming
your input through the PII classifier. Shows risk scores, EMA, and masking
events in real-time.

Usage:
    uv run python scripts/interactive.py --backend ollama
    uv run python scripts/interactive.py --backend anthropic --llm-name claude
"""

import argparse
import sys
import time
import threading
import os
from pathlib import Path
from typing import Optional
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.ccpp.infer.guard import ExchangePIIGuard
from src.ccpp.infer.stage1_router import Stage1Router
from src.ccpp.infer.stage2_redactor import Stage2Redactor
from src.ccpp.infer.heuristics import FastHeuristics
from src.ccpp.llm.factory import create_backend_from_config
from src.ccpp.llm.base import GenerationConfig


# Load environment variables from .env
load_dotenv()


class InteractiveClient:
    """Interactive terminal client for PII-masked chat."""

    def __init__(
        self,
        stage1_config_path: str,
        stage2_config_path: str,
        llm_backend: str = "anthropic",
        llm_model: str = "claude-3-5-haiku-20241022",
        pause_timeout: float = 3.0,
        mock_mode: bool = False,
    ):
        """Initialize interactive client.

        Args:
            stage1_config_path: Path to Stage 1 config YAML
            stage2_config_path: Path to Stage 2 config YAML
            llm_backend: Backend for LLM responses ("anthropic", "openai", "ollama")
            llm_model: Model name for LLM responses
            pause_timeout: Seconds of typing pause before finalizing buffer
            mock_mode: If True, use mock classification (no real models)
        """
        self.console = Console()
        self.pause_timeout = pause_timeout
        self.mock_mode = mock_mode

        # Load configs
        with open(stage1_config_path) as f:
            self.stage1_config = yaml.safe_load(f)
        with open(stage2_config_path) as f:
            self.stage2_config = yaml.safe_load(f)

        # Initialize guard components
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
        )

        # Initialize LLM backend for responses
        llm_config = {
            "backend": llm_backend,
            "model_name": llm_model,
        }
        self.llm_backend = create_backend_from_config(llm_config)
        self.llm_gen_config = GenerationConfig(
            max_tokens=2048,
            temperature=0.7,
            do_sample=True,
        )

        # State
        self.conversation_history = []  # List of {"role": ..., "content": ...}
        self.current_buffer = ""
        self.last_keystroke_time = None
        self.is_typing = False
        self.is_llm_responding = False

        # Metrics for display
        self.current_risk = 0.0
        self.current_ema = 0.0
        self.events_log = []
        self.masked_count = 0
        self.safe_count = 0

    def add_event(self, event_type: str, message: str):
        """Add event to log.

        Args:
            event_type: Type of event (risk_update, masked, safe, etc.)
            message: Event message
        """
        timestamp = time.strftime("%H:%M:%S")
        self.events_log.append(f"[{timestamp}] {event_type}: {message}")
        # Keep last 10 events
        if len(self.events_log) > 10:
            self.events_log.pop(0)

    def process_keystroke(self, char: str):
        """Process a single keystroke.

        Args:
            char: Character typed
        """
        self.current_buffer += char
        self.last_keystroke_time = time.time()
        self.is_typing = True

        # Stream character through guard
        emit_text, events = self.guard.ingest_chunk(char)

        # Process events
        for event in events:
            if event["type"] == "risk_update":
                self.current_risk = event["risk_score"]
                self.current_ema = event["ema_risk"]
                self.add_event("RISK", f"Risk={self.current_risk:.2f}, EMA={self.current_ema:.2f}")
            elif event["type"] == "masked":
                self.masked_count += 1
                original = event.get("original_text", "")
                masked = event.get("masked_text", "")
                self.add_event("MASKED", f'"{original[:30]}..." → "{masked[:30]}..."')
            elif event["type"] == "passed":
                self.safe_count += 1

    def finalize_buffer(self) -> str:
        """Finalize current buffer and return masked text.

        Returns:
            Masked/safe text ready to send to LLM
        """
        # Force emit any remaining text
        final_text, events = self.guard.force_emit()

        # Process final events
        for event in events:
            if event["type"] == "masked":
                self.masked_count += 1
                original = event.get("original_text", "")
                masked = event.get("masked_text", "")
                self.add_event("MASKED", f'Final: "{original[:30]}..." → "{masked[:30]}..."')

        self.add_event("FINALIZED", f"Buffer finalized: {len(final_text)} chars")

        # Reset buffer
        utterance = final_text
        self.current_buffer = ""
        self.is_typing = False

        return utterance

    def get_llm_response(self, user_message: str) -> str:
        """Get LLM response to user message.

        Args:
            user_message: User's (possibly masked) message

        Returns:
            LLM response (not passed through classifier for now)
        """
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message,
        })

        # Get LLM response (streaming)
        self.is_llm_responding = True
        self.add_event("LLM", "Generating response...")

        try:
            # For now, use non-streaming to simplify
            # TODO: Add streaming LLM response display
            response = self.llm_backend.generate(
                self.conversation_history,
                self.llm_gen_config,
            )

            # Add to history
            self.conversation_history.append({
                "role": "assistant",
                "content": response,
            })

            self.is_llm_responding = False
            self.add_event("LLM", f"Response received: {len(response)} chars")

            return response

        except Exception as e:
            self.is_llm_responding = False
            self.add_event("ERROR", f"LLM failed: {str(e)}")
            return f"[Error: {str(e)}]"

    def create_layout(self) -> Layout:
        """Create terminal layout.

        Returns:
            Rich Layout object
        """
        layout = Layout()

        # Split into top and bottom
        layout.split_column(
            Layout(name="main", ratio=3),
            Layout(name="input", size=5),
        )

        # Split main into left (conversation) and right (metrics)
        layout["main"].split_row(
            Layout(name="conversation", ratio=2),
            Layout(name="metrics", ratio=1),
        )

        return layout

    def render_conversation(self) -> Panel:
        """Render conversation history.

        Returns:
            Panel with conversation
        """
        text = Text()

        for msg in self.conversation_history[-10:]:  # Last 10 messages
            role = msg["role"]
            content = msg["content"]

            if role == "user":
                text.append(f"You: ", style="bold cyan")
                text.append(f"{content}\n\n")
            else:
                text.append(f"Assistant: ", style="bold green")
                text.append(f"{content}\n\n")

        if not text:
            text.append("Conversation will appear here...\n", style="dim")

        return Panel(text, title="Conversation", border_style="blue")

    def render_metrics(self) -> Panel:
        """Render metrics panel.

        Returns:
            Panel with metrics
        """
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold")
        table.add_column()

        # Current state
        if self.is_typing:
            state = Text("TYPING", style="bold yellow")
        elif self.is_llm_responding:
            state = Text("LLM RESPONDING", style="bold magenta")
        else:
            state = Text("IDLE", style="dim")

        table.add_row("State:", state)
        table.add_row("", "")

        # Risk metrics
        risk_color = "green" if self.current_risk < 0.3 else "yellow" if self.current_risk < 0.7 else "red"
        table.add_row("Current Risk:", Text(f"{self.current_risk:.2f}", style=risk_color))

        ema_color = "green" if self.current_ema < 0.3 else "yellow" if self.current_ema < 0.7 else "red"
        table.add_row("EMA Risk:", Text(f"{self.current_ema:.2f}", style=ema_color))
        table.add_row("", "")

        # Counts
        table.add_row("Masked:", str(self.masked_count))
        table.add_row("Safe:", str(self.safe_count))
        table.add_row("", "")

        # Events log
        table.add_row("Recent Events:", "")
        for event in self.events_log[-5:]:
            table.add_row("", Text(event, style="dim"))

        return Panel(table, title="Metrics", border_style="green")

    def render_input(self) -> Panel:
        """Render input area.

        Returns:
            Panel with input area
        """
        text = Text()

        if self.is_typing:
            text.append("Typing: ", style="bold yellow")
            text.append(self.current_buffer)
            text.append(" ▊", style="bold")  # Cursor
        else:
            text.append("Press SPACE to start typing, ESC to quit", style="dim")

        return Panel(text, title="Input", border_style="yellow")

    def run(self):
        """Run interactive client."""
        # NOTE: This is a simplified version that simulates the flow
        # For a full implementation, we'd need proper terminal input handling
        # using libraries like `prompt_toolkit` or `curses`

        self.console.print("[bold cyan]PII-Masked Interactive Chat[/bold cyan]")
        self.console.print(f"Backend: {self.stage1_config.get('backend', 'mock')}")
        self.console.print(f"Pause timeout: {self.pause_timeout}s")
        self.console.print()
        self.console.print("[dim]Note: This is a simplified demo. For full interactive typing,")
        self.console.print("a more sophisticated terminal UI library would be needed.[/dim]")
        self.console.print()

        # Simplified demo: prompt for input, process, show response
        while True:
            try:
                # Get user input
                user_input = self.console.input("[bold cyan]You:[/bold cyan] ")

                if not user_input.strip():
                    continue

                if user_input.lower() in ["quit", "exit", "q"]:
                    break

                # Simulate streaming through classifier
                self.console.print("[dim]Processing through PII classifier...[/dim]")

                for char in user_input:
                    self.process_keystroke(char)
                    # In real implementation, this would show real-time updates

                # Finalize buffer
                time.sleep(0.5)  # Simulate pause detection
                masked_text = self.finalize_buffer()

                # Show masked version if different
                if masked_text != user_input:
                    self.console.print(f"[yellow]Masked:[/yellow] {masked_text}")

                # Get LLM response
                with self.console.status("[bold magenta]Assistant is typing...[/bold magenta]"):
                    response = self.get_llm_response(masked_text)

                self.console.print(f"[bold green]Assistant:[/bold green] {response}")
                self.console.print()

                # Show metrics
                self.console.print(f"[dim]Risk: {self.current_risk:.2f} | EMA: {self.current_ema:.2f} | Masked: {self.masked_count} | Safe: {self.safe_count}[/dim]")
                self.console.print()

            except KeyboardInterrupt:
                break
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")
                break

        self.console.print("\n[bold]Goodbye![/bold]")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Interactive PII-masked chat client")
    parser.add_argument(
        "--stage1-config",
        default="configs/stage1_llm.yaml",
        help="Path to Stage 1 config YAML",
    )
    parser.add_argument(
        "--stage2-config",
        default="configs/stage2_llm.yaml",
        help="Path to Stage 2 config YAML",
    )
    parser.add_argument(
        "--backend",
        default="anthropic",
        choices=["anthropic", "openai", "ollama"],
        help="LLM backend for responses",
    )
    parser.add_argument(
        "--llm-model",
        help="LLM model name (defaults based on backend)",
    )
    parser.add_argument(
        "--pause-timeout",
        type=float,
        default=3.0,
        help="Typing pause timeout in seconds (default: 3.0)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock classification (no real models)",
    )

    args = parser.parse_args()

    # Set default model based on backend
    if args.llm_model is None:
        if args.backend == "anthropic":
            args.llm_model = "claude-3-5-haiku-20241022"
        elif args.backend == "openai":
            args.llm_model = "gpt-4o-mini"
        elif args.backend == "ollama":
            args.llm_model = "qwen:4b"

    # Check for API key if using API backend
    if args.backend == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not found in environment.")
        print("Please set it in your .env file or export it.")
        return 1

    if args.backend == "openai" and not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not found in environment.")
        print("Please set it in your .env file or export it.")
        return 1

    # Create and run client
    client = InteractiveClient(
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
