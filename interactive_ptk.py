"""Experimental prompt_toolkit-tuned interactive mode.

This mode keeps the *existing* interactive session logic intact, but improves
input/output smoothness by:
- Wrapping the interactive loop in `prompt_toolkit.patch_stdout()` so that Rich
  output doesn't corrupt the input prompt.
- Optionally tuning prompt_toolkit escape timeouts via the existing InputHandler
  (see utils/tui/input_handler.py).

Enable by setting:

    OURO_TUI=ptk

This is intended as a low-risk stepping stone toward a fully unified
prompt_toolkit UI, without losing any existing commands or behavior.
"""

from __future__ import annotations

from prompt_toolkit.patch_stdout import patch_stdout

from config import Config
from interactive import run_interactive_mode
from utils import terminal_ui


async def run_interactive_mode_ptk(agent) -> None:
    """Run the existing interactive mode under prompt_toolkit stdout patching."""

    # Preserve feature set: we still run the same InteractiveSession implementation.
    # patch_stdout prevents concurrent writes to stdout from breaking the prompt.
    old_status_bar = Config.TUI_STATUS_BAR

    try:
        with patch_stdout(raw=True):
            terminal_ui.print_info("PTK-tuned interactive mode enabled (OURO_TUI=ptk).")
            await run_interactive_mode(agent)
    finally:
        # Restore any config changes for safety (even if we tweak flags later).
        Config.TUI_STATUS_BAR = old_status_bar
