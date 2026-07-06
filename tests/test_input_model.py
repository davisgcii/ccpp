"""Tests for the append-only input model (PR4)."""

from ccpp.nicegui.input_model import (
    committed_prefix,
    newly_committed_tokens,
    reconcile_input,
)


class TestCommittedPrefix:
    def test_no_space_nothing_committed(self):
        assert committed_prefix("hello") == ("", "hello")

    def test_splits_at_last_space(self):
        assert committed_prefix("my email is") == ("my email ", "is")

    def test_trailing_space_commits_everything(self):
        assert committed_prefix("my email ") == ("my email ", "")


class TestReconcileInput:
    def test_appending_is_accepted(self):
        assert reconcile_input("my email is", "my email ") == ("my email is", False)

    def test_backspace_after_space_is_reverted(self):
        # committed "my email ", user backspaced the space -> "my email"
        text, reverted = reconcile_input("my email", "my email ")
        assert reverted is True
        assert text == "my email "

    def test_editing_committed_region_is_reverted(self):
        text, reverted = reconcile_input("my emaXl is", "my email ")
        assert reverted is True
        assert text == "my email "

    def test_editing_in_progress_token_is_allowed(self):
        # in-progress token edits (after the last committed space) are fine
        assert reconcile_input("my email i", "my email ") == ("my email i", False)


class TestNewlyCommittedTokens:
    def test_single_new_token(self):
        assert newly_committed_tokens("my ", "my email ") == ["email "]

    def test_multiple_new_tokens(self):
        assert newly_committed_tokens("my ", "my email is ") == ["email ", "is "]

    def test_no_new_commit(self):
        assert newly_committed_tokens("my email ", "my email ") == []

    def test_from_empty(self):
        assert newly_committed_tokens("", "hello there ") == ["hello ", "there "]
