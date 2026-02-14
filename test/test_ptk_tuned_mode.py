import os

from utils.tui.input_handler import InputHandler


def test_ptk_tuned_mode_reduces_escape_timeouts(monkeypatch) -> None:
    monkeypatch.setenv("OURO_TUI", "ptk")
    handler = InputHandler(history_file=None, commands=["help"])  # create PromptSession
    assert handler.session.app.ttimeoutlen == 0.05
    assert handler.session.app.timeoutlen == 0.2


def test_default_mode_keeps_prompt_toolkit_defaults(monkeypatch) -> None:
    monkeypatch.delenv("OURO_TUI", raising=False)
    handler = InputHandler(history_file=None, commands=["help"])
    assert handler.session.app.ttimeoutlen == 0.5
    assert handler.session.app.timeoutlen == 1.0
