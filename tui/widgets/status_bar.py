"""Status bar widget displaying session statistics."""

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static


class StatusBar(Widget):
    """Bottom status bar with turn count, tokens, cost, and compressions."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: $surface-darken-2;
        layout: horizontal;
    }

    StatusBar > .status-item {
        width: auto;
        padding: 0 1;
    }

    StatusBar > .status-separator {
        width: 1;
        color: $text-muted;
    }

    StatusBar > .status-turn {
        color: $text;
    }

    StatusBar > .status-tokens {
        color: $warning;
    }

    StatusBar > .status-cost {
        color: $success;
    }

    StatusBar > .status-compressions {
        color: $primary;
    }

    StatusBar > .status-spacer {
        width: 1fr;
    }

    StatusBar > .status-hint {
        color: $text-muted;
    }
    """

    turn: reactive[int] = reactive(0)
    input_tokens: reactive[int] = reactive(0)
    output_tokens: reactive[int] = reactive(0)
    cost: reactive[float] = reactive(0.0)
    compressions: reactive[int] = reactive(0)

    def compose(self) -> ComposeResult:
        yield Static(self._format_turn(), id="status-turn", classes="status-item status-turn")
        yield Static("\u2502", classes="status-separator")
        yield Static(self._format_tokens(), id="status-tokens", classes="status-item status-tokens")
        yield Static("\u2502", classes="status-separator")
        yield Static(self._format_cost(), id="status-cost", classes="status-item status-cost")
        yield Static("\u2502", classes="status-separator")
        yield Static(
            self._format_compressions(),
            id="status-compressions",
            classes="status-item status-compressions",
        )
        yield Static("", classes="status-spacer")
        yield Static("F1: Help | Ctrl+D: Exit", classes="status-item status-hint")

    def _format_turn(self) -> str:
        return f"Turn {self.turn}"

    def _format_tokens(self) -> str:
        in_k = self.input_tokens / 1000 if self.input_tokens >= 1000 else self.input_tokens
        out_k = self.output_tokens / 1000 if self.output_tokens >= 1000 else self.output_tokens
        in_fmt = f"{in_k:.1f}k" if self.input_tokens >= 1000 else str(self.input_tokens)
        out_fmt = f"{out_k:.1f}k" if self.output_tokens >= 1000 else str(self.output_tokens)
        return f"\u2191{in_fmt} \u2193{out_fmt}"

    def _format_cost(self) -> str:
        return f"${self.cost:.4f}"

    def _format_compressions(self) -> str:
        return f"{self.compressions} compressions"

    def watch_turn(self, value: int) -> None:
        try:
            self.query_one("#status-turn", Static).update(self._format_turn())
        except Exception:
            pass

    def watch_input_tokens(self, value: int) -> None:
        try:
            self.query_one("#status-tokens", Static).update(self._format_tokens())
        except Exception:
            pass

    def watch_output_tokens(self, value: int) -> None:
        try:
            self.query_one("#status-tokens", Static).update(self._format_tokens())
        except Exception:
            pass

    def watch_cost(self, value: float) -> None:
        try:
            self.query_one("#status-cost", Static).update(self._format_cost())
        except Exception:
            pass

    def watch_compressions(self, value: int) -> None:
        try:
            self.query_one("#status-compressions", Static).update(self._format_compressions())
        except Exception:
            pass

    def update_stats(
        self,
        turn: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cost: float | None = None,
        compressions: int | None = None,
    ) -> None:
        """Update multiple stats at once."""
        if turn is not None:
            self.turn = turn
        if input_tokens is not None:
            self.input_tokens = input_tokens
        if output_tokens is not None:
            self.output_tokens = output_tokens
        if cost is not None:
            self.cost = cost
        if compressions is not None:
            self.compressions = compressions
