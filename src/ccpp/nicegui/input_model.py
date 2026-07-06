"""Append-only input model for the streaming demo.

The demo simulates transcribed speech: hitting **space** ends a token and
"commits" it (it is fed to the guard and can no longer be edited). The user may
still edit the in-progress token after the last space, but backspacing across a
space (into committed text) is ignored.

These are pure functions so the rules are unit-tested without the NiceGUI loop.
"""

from __future__ import annotations


def committed_prefix(text: str) -> tuple[str, str]:
    """Split ``text`` into (committed, in_progress) at the last space.

    Committed is everything through the last space (inclusive); in_progress is
    the token currently being typed after it.

    >>> committed_prefix("my email is")
    ('my email ', 'is')
    >>> committed_prefix("hello")
    ('', 'hello')
    """
    idx = text.rfind(" ")
    if idx == -1:
        return ("", text)
    return (text[: idx + 1], text[idx + 1 :])


def reconcile_input(new_text: str, committed: str) -> tuple[str, bool]:
    """Enforce that already-committed text cannot be edited or deleted.

    Args:
        new_text: The textarea value after the user's keystroke.
        committed: The text already committed to the guard (locked).

    Returns:
        (accepted_text, reverted). If ``new_text`` still starts with the
        committed prefix, it is accepted unchanged. Otherwise the edit reached
        into committed text (e.g. backspace right after a space) and is
        rejected — the value snaps back to ``committed``.
    """
    if new_text.startswith(committed):
        return (new_text, False)
    return (committed, True)


def newly_committed_tokens(prev_committed: str, new_committed: str) -> list[str]:
    """Return the tokens committed by this keystroke.

    ``new_committed`` always extends ``prev_committed`` (callers guarantee
    append-only). The delta may contain one or more whitespace-delimited tokens
    (e.g. on paste). Each returned token keeps its trailing space so it can be
    fed straight to ``guard.ingest_chunk``.

    >>> newly_committed_tokens("my ", "my email is ")
    ['email ', 'is ']
    """
    if not new_committed.startswith(prev_committed):
        # Defensive: shouldn't happen after reconcile_input, treat all as new.
        prev_committed = ""
    delta = new_committed[len(prev_committed) :]
    if not delta:
        return []
    # Re-attach the trailing space to each token.
    tokens = [t + " " for t in delta.split(" ") if t]
    return tokens
