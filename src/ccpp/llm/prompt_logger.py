"""Lightweight prompt/response logging to a JSONL file.

Optimization: System prompts/templates are logged once per session,
then subsequent logs only include the dynamic parts (context + buffer).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from typing import Any, Dict, Optional, Set


_LOCK = threading.Lock()
_DEFAULT_LOG_PATH = "/tmp/prompt_logs.jsonl"

# Track which templates have been logged this session (by hash)
_logged_templates: Set[str] = set()

# Track if we've written the header comment this session
_header_written: bool = False

_LOG_HEADER = """# CC++ Prompt Logs
#
# NOTE: System prompts (instructions, examples, etc.) are logged ONCE at the start
# with kind="template". Subsequent log entries only include the dynamic part
# (Context + Buffer) to keep logs readable. Each entry has a "template_hash" field
# that references the full template logged earlier.
#
# To see the full prompt for any entry, find the matching template by hash.
#
# Emoji legend (for easy visual scanning):
#   📋 template     - System prompt (logged once per session)
#   🔍 classify     - Stage 1 classification (MLX/Ollama)
#   🤖 generate     - LLM generation (Anthropic/OpenAI)
#   ✂️  redact       - Stage 2 entity extraction
#   ❓ unknown      - Other/unrecognized kind
#
"""

# Emoji mapping for log kinds (makes scrolling through logs easier)
_KIND_EMOJI = {
    "template": "📋",
    "prefill_sequence_probs_batched": "🔍",
    "prefill_sequence_probs": "🔍",
    "classify": "🔍",
    "generate": "🤖",
    "redact": "✂️",
    "extract": "✂️",
}


def _log_path() -> str:
    return os.environ.get("CCPP_PROMPT_LOG_PATH", _DEFAULT_LOG_PATH)


def _hash_template(template: str) -> str:
    """Generate short hash for template identification."""
    return hashlib.md5(template.encode()).hexdigest()[:8]


def _extract_dynamic_part(prompt: str) -> Optional[str]:
    """Extract just the Context/Buffer/Answer part from a full prompt.

    Returns None if pattern not found (log full prompt as fallback).
    """
    # Look for markers that separate static template from dynamic content
    markers = ["# Your Turn", "# Current Request", "# Now classify"]

    for marker in markers:
        idx = prompt.find(marker)
        if idx != -1:
            # Return everything from the marker onwards
            return prompt[idx:]

    return None


def _extract_template_part(prompt: str) -> Optional[str]:
    """Extract the static template part (everything before dynamic content)."""
    markers = ["# Your Turn", "# Current Request", "# Now classify"]

    for marker in markers:
        idx = prompt.find(marker)
        if idx != -1:
            return prompt[:idx].strip()

    return None


def log_prompt_event(event: Dict[str, Any]) -> None:
    """Append a prompt/response event as JSONL.

    The caller should provide an event dict with prompt/response fields.

    Optimization: If the prompt contains a known template pattern,
    the template is logged once with kind="template", then subsequent
    events only log the dynamic part with a template_hash reference.
    """
    global _logged_templates

    prompt = event.get("prompt", "")

    # Try to separate template from dynamic content
    template_part = _extract_template_part(prompt)
    dynamic_part = _extract_dynamic_part(prompt)

    if template_part and dynamic_part:
        template_hash = _hash_template(template_part)

        # Log template once per session
        if template_hash not in _logged_templates:
            _logged_templates.add(template_hash)
            template_event = {
                "ts": time.time(),
                "kind": "template",
                "template_hash": template_hash,
                "backend": event.get("backend", "unknown"),
                "template": template_part,
            }
            _write_event(template_event)

        # Log event with just dynamic part
        event_copy = event.copy()
        event_copy["prompt"] = dynamic_part
        event_copy["template_hash"] = template_hash
        payload = {
            "ts": time.time(),
            **event_copy,
        }
    else:
        # No template pattern found - log full prompt
        payload = {
            "ts": time.time(),
            **event,
        }

    _write_event(payload)


def _write_event(payload: Dict[str, Any]) -> None:
    """Write event to log file (thread-safe).

    Each line is prefixed with an emoji based on kind for easy visual scanning.
    The emoji is outside the JSON so the JSON remains valid.
    """
    global _header_written

    try:
        # Get emoji for this kind (default to ❓ for unknown)
        kind = payload.get("kind", "")
        emoji = _KIND_EMOJI.get(kind, "❓")

        json_str = json.dumps(payload, ensure_ascii=True)
        line = f"{emoji} {json_str}"

        with _LOCK:
            log_file = _log_path()

            # Write header if this is a new/empty file
            if not _header_written:
                # Check if file is empty or doesn't exist
                try:
                    file_size = os.path.getsize(log_file)
                except OSError:
                    file_size = 0

                if file_size == 0:
                    with open(log_file, "w", encoding="utf-8") as handle:
                        handle.write(_LOG_HEADER)
                _header_written = True

            with open(log_file, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
    except Exception:
        # Never let logging break inference/GUI
        return


def reset_logged_templates() -> None:
    """Reset the logged templates set (for testing or new sessions)."""
    global _logged_templates, _header_written
    with _LOCK:
        _logged_templates.clear()
        _header_written = False
