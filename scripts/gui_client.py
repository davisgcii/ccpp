#!/usr/bin/env python3
"""Launcher for PII-masked chat GUI client.

A Gradio-based pop-up window that shows:
- Real-time risk metrics as user types
- Visual risk indicators under words
- Side-by-side original vs masked text
- Streaming LLM responses with interruption handling

Usage:
    uv run python scripts/gui_client.py
    uv run python scripts/gui_client.py --timeout 5.0
    uv run python scripts/gui_client.py --share  # Create public link
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ccpp.gui.state import PIIClientState
from ccpp.gui.app import create_gui


def main():
    """Main entry point for GUI client."""
    parser = argparse.ArgumentParser(
        description="Interactive GUI client for PII-masked chat"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="Stream break timeout in seconds (default: 3.0)",
    )
    parser.add_argument(
        "--env",
        type=str,
        default="default",
        choices=["default", "dev", "prod"],
        help="Configuration environment (default: default)",
    )
    parser.add_argument(
        "--share",
        action="store_true",
        help="Create public share link via Gradio",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7860,
        help="Port to run server on (default: 7860)",
    )

    args = parser.parse_args()

    # Create state
    print("=" * 60)
    print("PII-Masked Chat GUI Client")
    print("=" * 60)
    print(f"Stream break timeout: {args.timeout}s")
    print(f"Configuration: {args.env}")
    print()
    print("Initializing components...")

    state = PIIClientState(
        stream_break_timeout=args.timeout,
        environment=args.env,
    )

    print("✅ Client initialized!")
    print()
    print("Launching GUI...")
    print("=" * 60)

    # Create and launch GUI
    demo = create_gui(state)
    demo.launch(
        share=args.share,
        server_name="127.0.0.1",
        server_port=args.port,
        show_error=True,
    )


if __name__ == "__main__":
    main()
