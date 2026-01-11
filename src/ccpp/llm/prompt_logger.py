"""Lightweight prompt/response logging to a JSONL file."""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict


_LOCK = threading.Lock()
_DEFAULT_LOG_PATH = "/tmp/prompt_logs.jsonl"


def _log_path() -> str:
    return os.environ.get("CCPP_PROMPT_LOG_PATH", _DEFAULT_LOG_PATH)


def log_prompt_event(event: Dict[str, Any]) -> None:
    """Append a prompt/response event as JSONL.

    The caller should provide an event dict with prompt/response fields.
    """
    payload = {
        "ts": time.time(),
        **event,
    }
    try:
        line = json.dumps(payload, ensure_ascii=True)
        with _LOCK:
            with open(_log_path(), "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
    except Exception:
        # Never let logging break inference/GUI
        return
