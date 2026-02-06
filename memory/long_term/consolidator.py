"""LLM-based consolidation for long-term memory.

When total memory exceeds a token threshold the consolidator asks an LLM to
merge duplicates, remove stale entries, and compress the content.
"""

import logging
from typing import TYPE_CHECKING

from config import Config
from llm.message_types import LLMMessage

from .store import MemoryCategory

if TYPE_CHECKING:
    from llm import LiteLLMAdapter

logger = logging.getLogger(__name__)

# Rough chars-per-token ratio for estimation
_CHARS_PER_TOKEN = 3.5

CONSOLIDATION_PROMPT = """\
You are a memory consolidation assistant. Below are long-term memory entries \
organized by category. Your job is to consolidate them:

1. Merge overlapping or duplicate entries into single, clear statements.
2. Remove entries that are outdated or no longer useful.
3. Preserve all important, actionable information.
4. Keep each entry as a single concise statement.
5. Target at least 40% reduction in total entries while retaining key information.

Return ONLY valid YAML with exactly this structure (no extra keys, no commentary):

decisions:
  - "entry"
preferences:
  - "entry"
facts:
  - "entry"

CURRENT MEMORIES:
{memories_text}"""


class LongTermMemoryConsolidator:
    """Consolidates long-term memories using an LLM when they exceed a size threshold."""

    def __init__(self, llm: "LiteLLMAdapter"):
        self.llm = llm

    async def should_consolidate(
        self,
        memories: dict[MemoryCategory, list[str]],
    ) -> bool:
        """Check whether total memory content exceeds the consolidation threshold."""
        threshold = Config.LONG_TERM_MEMORY_CONSOLIDATION_THRESHOLD
        total_text = self._format_memories_text(memories)
        estimated_tokens = int(len(total_text) / _CHARS_PER_TOKEN)
        return estimated_tokens > threshold

    async def consolidate(
        self,
        memories: dict[MemoryCategory, list[str]],
    ) -> dict[MemoryCategory, list[str]]:
        """Ask LLM to consolidate memories across all categories.

        Returns:
            Consolidated mapping of category → entries.
        """
        memories_text = self._format_memories_text(memories)
        prompt = CONSOLIDATION_PROMPT.format(memories_text=memories_text)

        response = await self.llm.call_async(
            messages=[LLMMessage(role="user", content=prompt)],
            max_tokens=4096,
        )

        text = response.content if isinstance(response.content, str) else ""
        return self._parse_response(text, memories)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_memories_text(memories: dict[MemoryCategory, list[str]]) -> str:
        """Format all memories into a single text block for the prompt."""
        parts: list[str] = []
        for cat in MemoryCategory:
            entries = memories.get(cat, [])
            if entries:
                lines = "\n".join(f'  - "{e}"' for e in entries)
                parts.append(f"{cat.value}:\n{lines}")
        return "\n\n".join(parts) if parts else "(empty)"

    @staticmethod
    def _parse_response(
        text: str,
        original: dict[MemoryCategory, list[str]],
    ) -> dict[MemoryCategory, list[str]]:
        """Parse LLM YAML response, falling back to original on failure."""
        import yaml

        try:
            data = yaml.safe_load(text)
        except Exception:
            logger.warning("Failed to parse consolidation response as YAML")
            return original

        if not isinstance(data, dict):
            logger.warning("Consolidation response is not a mapping")
            return original

        result: dict[MemoryCategory, list[str]] = {}
        for cat in MemoryCategory:
            raw = data.get(cat.value, [])
            if isinstance(raw, list):
                result[cat] = [str(e) for e in raw if e]
            else:
                # Keep original if category is malformed
                result[cat] = original.get(cat, [])
        return result
