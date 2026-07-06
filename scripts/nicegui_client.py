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
import os
import platform
import subprocess
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ccpp.gui.state import PIIClientState
from ccpp.nicegui.app import create_app


# Keep the machine awake for at most this long, so a forgotten idle demo can't
# hold your Mac awake indefinitely. `-t` caps the assertion even alongside `-w`.
_CAFFEINATE_TIMEOUT_S = 300  # 5 minutes


def prevent_app_nap() -> None:
    """Stop macOS from throttling this background process (App Nap).

    A backgrounded server process gets its threads throttled, which makes MLX
    inference 20-40x slower and degrade over a session. `caffeinate` holds
    "stay active" assertions; `-w <pid>` releases them when this process exits,
    and `-t` releases them after a timeout so an idle demo can't keep the Mac
    awake forever. No-op off macOS.
    """
    if platform.system() != "Darwin":
        return
    try:
        subprocess.Popen(
            ["caffeinate", "-dimsu", "-t", str(_CAFFEINATE_TIMEOUT_S),
             "-w", str(os.getpid())],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        print(f"  App Nap: disabled for {_CAFFEINATE_TIMEOUT_S // 60} min (caffeinate)")
    except FileNotFoundError:
        print("  App Nap: caffeinate not found — inference may throttle")


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

    # Keep macOS from throttling us before we load + warm up the models.
    prevent_app_nap()

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
        # Default is 3s: if the event loop stalls briefly (a heavy render, an
        # occasional slow inference), the client declares "connection lost" and
        # reconnects — and the reconnect's page rebuild then starves the in-flight
        # MLX worker, ballooning a 0.5s inference into 20s+. For a local
        # single-user demo, be very patient instead of triggering that spiral.
        reconnect_timeout=60.0,
    )


if __name__ == "__main__":
    main()
