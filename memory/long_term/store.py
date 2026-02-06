"""Git-backed store for long-term memory.

Memory files live in ~/.aloop/memory/ as YAML files, managed by a local git repo
for change tracking and concurrency detection.
"""

import asyncio
import logging
import os
import shutil
import subprocess
from enum import Enum
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


class MemoryCategory(str, Enum):
    """Categories for long-term memory entries."""

    DECISIONS = "decisions"
    PREFERENCES = "preferences"
    FACTS = "facts"


class GitMemoryStore:
    """Git-backed store for long-term memory YAML files.

    Handles repo initialization, reading YAML files, HEAD-based change detection,
    and saving + committing (used only by the consolidator).
    Agent writes are done directly via file/shell tools.
    """

    def __init__(self, memory_dir: Optional[str] = None):
        if memory_dir is None:
            from utils.runtime import get_memory_dir

            memory_dir = get_memory_dir()
        self.memory_dir = memory_dir
        self._loaded_head: Optional[str] = None

    # ------------------------------------------------------------------
    # Git infrastructure
    # ------------------------------------------------------------------

    async def ensure_repo(self) -> None:
        """Initialize a git repo in memory_dir if one doesn't exist."""
        os.makedirs(self.memory_dir, exist_ok=True)
        git_dir = os.path.join(self.memory_dir, ".git")
        if not os.path.isdir(git_dir):
            await self._run_git("init")
            logger.info("Initialized long-term memory git repo at %s", self.memory_dir)

    async def get_current_head(self) -> Optional[str]:
        """Return current HEAD commit hash, or None if no commits yet."""
        try:
            out = await self._run_git("rev-parse", "HEAD")
            return out.strip() or None
        except subprocess.CalledProcessError:
            return None

    async def has_changed_since_load(self) -> bool:
        """Return True if HEAD differs from the snapshot taken at load time."""
        current = await self.get_current_head()
        return current != self._loaded_head

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def load_all(self) -> dict[MemoryCategory, list[str]]:
        """Read all category YAML files and snapshot the HEAD hash.

        Returns:
            Mapping of category to list of memory entry strings.
        """
        await self.ensure_repo()
        self._loaded_head = await self.get_current_head()

        memories: dict[MemoryCategory, list[str]] = {}
        for cat in MemoryCategory:
            path = os.path.join(self.memory_dir, f"{cat.value}.yaml")
            entries = await asyncio.to_thread(self._read_yaml, path)
            memories[cat] = entries
        return memories

    @staticmethod
    def _read_yaml(path: str) -> list[str]:
        """Synchronously read a memory YAML file.

        Expected schema — a plain YAML list::

            - "some memory"
            - "another memory"
        """
        if not os.path.isfile(path):
            return []
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, list):
                return []
            return [str(e) for e in data if e]
        except Exception:
            logger.warning("Failed to read memory file %s", path, exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Write (used by consolidator only)
    # ------------------------------------------------------------------

    async def save_and_commit(
        self,
        memories: dict[MemoryCategory, list[str]],
        message: str,
    ) -> None:
        """Write all category files and create a git commit.

        This is intended for the consolidator after merging/pruning entries.
        Normal agent writes go through file tools + shell git commands.
        """
        await self.ensure_repo()

        for cat in MemoryCategory:
            path = os.path.join(self.memory_dir, f"{cat.value}.yaml")
            entries = memories.get(cat, [])
            await asyncio.to_thread(self._write_yaml, path, entries)

        await self._run_git("add", "-A")

        # Only commit if there are staged changes
        try:
            await self._run_git("diff", "--cached", "--quiet")
            # No changes staged — skip commit
            return
        except subprocess.CalledProcessError:
            # Changes exist — proceed to commit
            pass

        await self._run_git("commit", "-m", message)

    @staticmethod
    def _write_yaml(path: str, entries: list[str]) -> None:
        """Synchronously write a memory YAML file."""
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(entries, f, default_flow_style=False, allow_unicode=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _run_git(self, *args: str) -> str:
        """Execute a git command in memory_dir via subprocess."""
        git_bin = shutil.which("git") or "git"
        cmd = [git_bin, "-C", self.memory_dir, *args]
        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
