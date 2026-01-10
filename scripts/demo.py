#!/usr/bin/env python3
"""Demo script for streaming PII masking.

This script demonstrates the CC++-inspired streaming PII detection and masking
system with real-time visualization of risk scores and masking decisions.
"""

import time
import sys
from ccpp.infer.guard import ExchangePIIGuard


# ANSI color codes for terminal output
class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"


def print_risk_bar(ema_risk: float, threshold_high: float = 0.6):
    """Print a visual risk meter."""
    bar_length = 30
    filled = int(bar_length * min(ema_risk, 1.0))
    empty = bar_length - filled

    # Color based on risk level
    if ema_risk >= threshold_high:
        color = Colors.RED
    elif ema_risk >= 0.3:
        color = Colors.YELLOW
    else:
        color = Colors.GREEN

    bar = color + "█" * filled + Colors.DIM + "░" * empty + Colors.RESET
    return f"Risk: {bar} {ema_risk:.3f}"


def stream_text(text: str, guard: ExchangePIIGuard, delay: float = 0.05, verbose: bool = True):
    """Stream text character-by-character through the guard.

    Args:
        text: Text to stream
        guard: PII guard instance
        delay: Delay between characters (seconds)
        verbose: If True, show detailed risk updates
    """
    print(f"\n{Colors.BOLD}Streaming:{Colors.RESET} {Colors.CYAN}{text}{Colors.RESET}")
    print(f"{Colors.DIM}{'='*60}{Colors.RESET}")

    accumulated = ""
    last_ema = 0.0

    for char in text:
        accumulated += char
        emit, events = guard.ingest_chunk(char)

        # Show risk updates
        for event in events:
            if event["type"] == "risk_update":
                ema_risk = event["ema_risk"]

                # Only print if risk changed significantly or verbose mode
                if verbose or abs(ema_risk - last_ema) > 0.05:
                    print(f"  {accumulated[:40]:40s} | {print_risk_bar(ema_risk)}")
                    last_ema = ema_risk

        time.sleep(delay)

    # Force emit
    emit, events = guard.force_emit()

    print(f"{Colors.DIM}{'='*60}{Colors.RESET}")

    # Show result
    for event in events:
        if event["type"] == "masked":
            print(f"{Colors.BOLD}Result:{Colors.RESET} {Colors.RED}MASKED{Colors.RESET}")
            print(f"  Found {event['num_entities']} PII entities:")
            for entity in event["entities"]:
                print(f"    • {Colors.MAGENTA}{entity['text']}{Colors.RESET} ({entity['category']})")
            print(f"\n{Colors.BOLD}Output:{Colors.RESET} {Colors.GREEN}{emit}{Colors.RESET}")
        elif event["type"] == "passed":
            print(f"{Colors.BOLD}Result:{Colors.RESET} {Colors.GREEN}PASSED{Colors.RESET} (no PII detected)")
            print(f"{Colors.BOLD}Output:{Colors.RESET} {emit}")

    return emit


def run_demo():
    """Run the demo scenarios."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}")
    print("  CC++ Streaming PII Masking Demo")
    print(f"{'='*60}{Colors.RESET}\n")

    print("This demo showcases real-time PII detection and masking")
    print("using a CC++-inspired two-stage classifier cascade.")
    print(f"\n{Colors.DIM}Press Ctrl+C to exit at any time.{Colors.RESET}")

    # Initialize guard
    guard = ExchangePIIGuard(
        risk_threshold_high=0.6,
        # reset_ema_on_stream_break=False (default: EMA decays naturally)
    )

    # Scenario 1: Email detection
    print(f"\n{Colors.BOLD}Scenario 1: Email Detection{Colors.RESET}")
    stream_text(
        "Hi, my email address is john.doe@company.com",
        guard,
        delay=0.03,
        verbose=False,
    )
    guard.reset()

    # Scenario 2: Phone number
    print(f"\n{Colors.BOLD}Scenario 2: Phone Number{Colors.RESET}")
    stream_text(
        "You can reach me at 415-867-5309",
        guard,
        delay=0.03,
        verbose=False,
    )
    guard.reset()

    # Scenario 3: Benign text
    print(f"\n{Colors.BOLD}Scenario 3: Benign Text{Colors.RESET}")
    stream_text(
        "Hello! How are you doing today?",
        guard,
        delay=0.03,
        verbose=False,
    )
    guard.reset()

    # Scenario 4: Multiple PII entities
    print(f"\n{Colors.BOLD}Scenario 4: Multiple PII Entities{Colors.RESET}")
    stream_text(
        "Contact: alice@company.com or call 555-123-4567",
        guard,
        delay=0.03,
        verbose=False,
    )
    guard.reset()

    # Scenario 5: Partial entity (speculative detection)
    print(f"\n{Colors.BOLD}Scenario 5: Partial Entity (Speculative){Colors.RESET}")
    print(f"{Colors.DIM}Demonstrates catching partial PII like '702...'{Colors.RESET}")
    stream_text(
        "My number is 702-555-8888",
        guard,
        delay=0.05,
        verbose=True,  # Show detailed risk progression
    )
    guard.reset()

    # Scenario 6: API key
    print(f"\n{Colors.BOLD}Scenario 6: API Key Detection{Colors.RESET}")
    stream_text(
        "Here's my key: sk_live_abc123def456",
        guard,
        delay=0.03,
        verbose=False,
    )

    print(f"\n{Colors.BOLD}{Colors.GREEN}✓ Demo completed!{Colors.RESET}\n")


def interactive_mode():
    """Run interactive mode where user can type text."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}")
    print("  Interactive Mode")
    print(f"{'='*60}{Colors.RESET}\n")

    print("Type text and press Enter to see it processed.")
    print(f"{Colors.DIM}Type 'exit' or 'quit' to exit.{Colors.RESET}\n")

    guard = ExchangePIIGuard(reset_ema_on_stream_break=True)

    while True:
        try:
            text = input(f"{Colors.BOLD}> {Colors.RESET}")

            if text.lower() in ["exit", "quit", "q"]:
                print("Goodbye!")
                break

            if not text.strip():
                continue

            # Process text
            for char in text:
                guard.ingest_chunk(char)

            emit, events = guard.force_emit()

            # Show result
            print(f"{Colors.BOLD}Output:{Colors.RESET} {Colors.GREEN}{emit}{Colors.RESET}")

            for event in events:
                if event["type"] == "masked":
                    print(f"{Colors.RED}⚠ Masked {event['num_entities']} PII entities{Colors.RESET}")

            guard.reset()
            print()

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except EOFError:
            print("\n\nGoodbye!")
            break


def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] in ["-i", "--interactive"]:
        interactive_mode()
    else:
        try:
            run_demo()
        except KeyboardInterrupt:
            print(f"\n\n{Colors.DIM}Demo interrupted.{Colors.RESET}")


if __name__ == "__main__":
    main()
