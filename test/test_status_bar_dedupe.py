from rich.console import Console

from utils.tui.status_bar import StatusBar


def test_status_bar_dedupes_identical_shows_when_enabled() -> None:
    console = Console(record=True, width=120)
    bar = StatusBar(console, dedupe_prints=True)
    bar.update(mode="LOOP", model_name="test-model")

    bar.show()
    first = console.export_text(clear=False)

    bar.show()
    second = console.export_text(clear=False)

    assert second == first


def test_status_bar_prints_again_when_state_changes() -> None:
    console = Console(record=True, width=120)
    bar = StatusBar(console, dedupe_prints=True)
    bar.update(mode="LOOP", model_name="test-model")

    bar.show()
    first = console.export_text(clear=False)

    bar.update(is_processing=True)
    bar.show()
    second = console.export_text(clear=False)

    assert second != first
