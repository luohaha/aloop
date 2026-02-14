#!/usr/bin/env python3
"""Benchmark interactive command-flow latency across TUI modes.

Modes covered:
- default (no OURO_TUI)
- ptk2    (OURO_TUI=ptk2)

This is a command-flow benchmark, not just startup timing:
- startup
- /help /stats /resume /theme /verbose /compact
- /model (open + pick current)
- /skills (open + pick list)
- /reset /exit

Method notes:
- Uses PTY for realistic TUI timing and redraw behavior.
- Matches markers incrementally (only output produced after each command).
- Repeats runs and reports mean/p50/min/max per step.
"""

from __future__ import annotations

import contextlib
import os
import pty
import re
import select
import statistics
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
OSC_RE = re.compile(r"\x1b\].*?(?:\x07|\x1b\\)")
WHITESPACE_RE = re.compile(r"\s+")


STEP_DEFS: list[tuple[str, str, list[str], float]] = [
    ("help", "/help\r", ["Available Commands:", "Keyboard", "model edit"], 10.0),
    ("stats", "/stats\r", ["Memory Statistics"], 8.0),
    (
        "resume",
        "/resume\r",
        ["Recent Sessions:", "No saved sessions found.", "Usage: /resume"],
        8.0,
    ),
    ("theme", "/theme\r", ["Switched to light theme", "Switched to dark theme"], 8.0),
    ("verbose", "/verbose\r", ["Verbose thinking display"], 8.0),
    (
        "compact",
        "/compact\r",
        ["Nothing to compress.", "No messages to compress", "Compressed "],
        10.0,
    ),
    ("model_open", "/model\r", ["Select Model"], 8.0),
    ("model_pick", "\r", ["Switched to model:", "Failed to switch to model"], 8.0),
    ("skills_open", "/skills\r", ["Choose an action", "Skills\nChoose an action"], 8.0),
    (
        "skills_pick",
        "\r",
        ["Installed Skills:", "No installed skills found", "skill-installer", "skill-creator"],
        8.0,
    ),
    ("reset", "/reset\r", ["Memory cleared. Starting fresh conversation."], 8.0),
    ("exit", "/exit\r", ["Exiting interactive mode. Goodbye!"], 8.0),
]


def strip_ansi(text: str) -> str:
    text = OSC_RE.sub("", text)
    text = ANSI_RE.sub("", text)
    return text.replace("\r", "\n")


def compact(text: str) -> str:
    return WHITESPACE_RE.sub("", text)


class PtySession:
    def __init__(self, mode: str) -> None:
        env = os.environ.copy()
        env.pop("OURO_TUI", None)
        if mode != "default":
            env["OURO_TUI"] = mode

        master_fd, slave_fd = pty.openpty()
        self.master_fd = master_fd
        self.proc = subprocess.Popen(  # noqa: S603
            ["uv", "run", "ouro"],
            cwd=str(REPO_ROOT),
            env=env,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
        )
        os.close(slave_fd)
        self.buffer = ""

    def read_some(self, timeout: float = 0.05) -> None:
        ready, _, _ = select.select([self.master_fd], [], [], timeout)
        if not ready:
            return
        try:
            data = os.read(self.master_fd, 65536)
        except OSError:
            return
        if not data:
            return
        self.buffer = (self.buffer + strip_ansi(data.decode("utf-8", errors="ignore")))[-260000:]

    def wait_for(self, patterns: list[str], timeout: float, since_len: int) -> bool:
        compact_patterns = [compact(p) for p in patterns]
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.read_some(0.05)
            hay = self.buffer[since_len:]
            hay_compact = compact(hay)
            for pattern, pattern_compact in zip(patterns, compact_patterns):
                if pattern in hay or pattern_compact in hay_compact:
                    return True
            if self.proc.poll() is not None:
                return False
        return False

    def send(self, text: str) -> None:
        os.write(self.master_fd, text.encode("utf-8"))

    def close(self) -> None:
        try:
            if self.proc.poll() is None:
                self.send("/exit\r")
                start = time.monotonic()
                while self.proc.poll() is None and time.monotonic() - start < 2:
                    self.read_some(0.05)
                if self.proc.poll() is None:
                    self.proc.terminate()
        finally:
            with contextlib.suppress(OSError):
                os.close(self.master_fd)


def run_once(mode: str) -> dict[str, float] | None:
    session = PtySession(mode)
    try:
        metrics: dict[str, float] = {}

        startup_idx = len(session.buffer)
        t0 = time.monotonic()
        if not session.wait_for(
            ["Interactive mode started. Type your message or use commands."],
            timeout=30,
            since_len=startup_idx,
        ):
            return None
        metrics["startup"] = time.monotonic() - t0

        for step_name, payload, markers, timeout in STEP_DEFS:
            step_idx = len(session.buffer)
            start = time.monotonic()
            session.send(payload)
            ok = session.wait_for(markers, timeout=timeout, since_len=step_idx)
            if not ok:
                return None
            metrics[step_name] = time.monotonic() - start

        return metrics
    finally:
        session.close()


def summarize(samples: list[float]) -> str:
    return (
        f"{statistics.mean(samples):.3f} "
        f"(p50 {statistics.median(samples):.3f}, min {min(samples):.3f}, max {max(samples):.3f})"
    )


def main() -> int:
    modes = ["default", "ptk2"]
    runs = int(os.environ.get("TUI_BENCH_RUNS", "5"))
    step_names = ["startup"] + [name for name, _, _, _ in STEP_DEFS]

    for mode in modes:
        metrics_by_step: dict[str, list[float]] = {name: [] for name in step_names}
        pass_count = 0

        for _ in range(runs):
            sample = run_once(mode)
            if sample is None:
                continue
            pass_count += 1
            for name in step_names:
                metrics_by_step[name].append(sample[name])

        fail_count = runs - pass_count
        print(f"mode={mode} runs={runs} pass={pass_count} fail={fail_count}")
        if pass_count == 0:
            continue
        for name in step_names:
            print(f"  {name:11}: {summarize(metrics_by_step[name])}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
