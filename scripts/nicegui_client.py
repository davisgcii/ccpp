#!/usr/bin/env python3
"""Launcher for NiceGUI PII-masked chat client (Apple Design).

An alternative to the Gradio GUI with:
- Apple-inspired design (light theme, SF Pro, iMessage-style bubbles)
- Real-time ECharts risk visualization (no ASCII art)
- Pre-send review panel with per-entity approve/reject
- Streaming LLM responses
- WebSocket-based updates (no polling)

Usage:
    uv run python scripts/nicegui_client.py
    uv run python scripts/nicegui_client.py --timeout 5.0
    uv run python scripts/nicegui_client.py --port 8080
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ccpp.gui.state import PIIClientState
from ccpp.nicegui.app import create_app


def main():
    """Main entry point for NiceGUI client."""
    parser = argparse.ArgumentParser(
        description="Interactive NiceGUI client for PII-masked chat (Apple Design)"
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
        "--port",
        type=int,
        default=8080,
        help="Port to run server on (default: 8080)",
    )

    args = parser.parse_args()

    # Clear log files on startup
    import os
    log_file = "/tmp/gui_debug.log"
    prompt_log_file = "/tmp/prompt_logs.jsonl"
    for f in [log_file, prompt_log_file]:
        if os.path.exists(f):
            os.remove(f)
            print(f"Cleared old logs: {f}")

    # Create state
    print("=" * 60)
    print("PII-Masked Chat — NiceGUI Client")
    print("=" * 60)
    print(f"  Stream break timeout: {args.timeout}s")
    print(f"  Configuration: {args.env}")
    print(f"  Logs: {log_file}")
    print(f"  URL: http://127.0.0.1:{args.port}")
    print()
    print("  View logs: tail -f /tmp/gui_debug.log")
    print()
    print("Initializing components...")

    state = PIIClientState(
        stream_break_timeout=args.timeout,
        environment=args.env,
    )

    print("Components initialized.")
    print("Launching NiceGUI...")
    print("=" * 60)

    # Create page routes
    create_app(state)

    # Start server
    from nicegui import ui
    ui.run(
        host="127.0.0.1",
        port=args.port,
        title="PII Masking Demo",
        reload=False,
        show=True,
    )


if __name__ == "__main__":
    main()
