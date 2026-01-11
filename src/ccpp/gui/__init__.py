"""Interactive GUI client for PII-masked chat.

This package provides a Gradio-based GUI for real-time PII detection and masking.
"""

from ccpp.gui.state import PIIClientState
from ccpp.gui.app import create_gui

__all__ = ["PIIClientState", "create_gui"]
