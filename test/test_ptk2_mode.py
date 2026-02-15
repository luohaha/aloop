from utils.tui.ptk2_mode import (
    drop_visible_prefix_preserving_sgr,
    next_follow_tail_state,
    normalize_output_chunk,
    split_incomplete_ansi_suffix,
    strip_ansi,
)


def test_strip_ansi_removes_escape_sequences() -> None:
    assert strip_ansi("\x1b[31mERR\x1b[0m") == "ERR"


def test_strip_ansi_removes_osc_sequences() -> None:
    assert strip_ansi("x\x1b]0;title\x07y") == "xy"


def test_normalize_output_chunk_normalizes_crlf_and_cr() -> None:
    raw = "a\r\nb\rc"
    assert normalize_output_chunk(raw) == "a\nb\nc"


def test_normalize_output_chunk_keeps_sgr_but_strips_control_noise() -> None:
    raw = "\x1b[31mA\x1b[0m\bB"
    assert normalize_output_chunk(raw) == "\x1b[31mA\x1b[0mB"


def test_normalize_output_chunk_strips_non_sgr_csi_sequences() -> None:
    raw = "\x1b[2J\x1b[H\x1b[31mA\x1b[0m"
    assert normalize_output_chunk(raw) == "\x1b[31mA\x1b[0m"


def test_next_follow_tail_state_from_scroll_events() -> None:
    assert (
        next_follow_tail_state(current_follow_tail=True, scroll_delta=-1, at_bottom=False) is False
    )
    assert (
        next_follow_tail_state(current_follow_tail=False, scroll_delta=1, at_bottom=False) is False
    )
    assert next_follow_tail_state(current_follow_tail=False, scroll_delta=1, at_bottom=True) is True
    assert next_follow_tail_state(current_follow_tail=True, scroll_delta=0, at_bottom=False) is True


def test_split_incomplete_ansi_suffix_carries_fragment() -> None:
    head, carry = split_incomplete_ansi_suffix("A\x1b[31")
    assert head == "A"
    assert carry == "\x1b[31"

    head, carry = split_incomplete_ansi_suffix("\x1b")
    assert head == ""
    assert carry == "\x1b"

    head, carry = split_incomplete_ansi_suffix("A\x1b[31mB")
    assert head == "A\x1b[31mB"
    assert carry == ""

    # Incomplete OSC should be carried too.
    head, carry = split_incomplete_ansi_suffix("X\x1b]0;title")
    assert head == "X"
    assert carry.startswith("\x1b]0;title")


def test_drop_visible_prefix_preserves_sgr_and_drops_visible_chars() -> None:
    s = "\x1b[31mRED\x1b[0mXYZ"
    out = drop_visible_prefix_preserving_sgr(s, 3)
    assert strip_ansi(out) == "XYZ"
