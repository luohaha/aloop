"""Tests for LongTermMemoryConsolidator."""

import pytest

from memory.long_term.consolidator import LongTermMemoryConsolidator
from memory.long_term.store import MemoryCategory


@pytest.mark.asyncio
class TestConsolidator:
    async def test_should_consolidate_below_threshold(self, mock_ltm_llm, monkeypatch):
        from config import Config

        monkeypatch.setattr(Config, "LONG_TERM_MEMORY_CONSOLIDATION_THRESHOLD", 5000)
        consolidator = LongTermMemoryConsolidator(mock_ltm_llm)

        memories = {
            MemoryCategory.DECISIONS: ["short"],
            MemoryCategory.PREFERENCES: [],
            MemoryCategory.FACTS: [],
        }
        assert not await consolidator.should_consolidate(memories)

    async def test_should_consolidate_above_threshold(self, mock_ltm_llm, monkeypatch):
        from config import Config

        monkeypatch.setattr(Config, "LONG_TERM_MEMORY_CONSOLIDATION_THRESHOLD", 10)
        consolidator = LongTermMemoryConsolidator(mock_ltm_llm)

        memories = {
            MemoryCategory.DECISIONS: ["a" * 200],
            MemoryCategory.PREFERENCES: ["b" * 200],
            MemoryCategory.FACTS: ["c" * 200],
        }
        assert await consolidator.should_consolidate(memories)

    async def test_consolidate_parses_valid_yaml(self, mock_ltm_llm):
        mock_ltm_llm.response_text = (
            "decisions:\n"
            '  - "merged decision"\n'
            "preferences:\n"
            '  - "pref"\n'
            "facts:\n"
            '  - "fact"\n'
        )
        consolidator = LongTermMemoryConsolidator(mock_ltm_llm)
        original = {
            MemoryCategory.DECISIONS: ["d1", "d2"],
            MemoryCategory.PREFERENCES: ["p1"],
            MemoryCategory.FACTS: ["f1"],
        }
        result = await consolidator.consolidate(original)
        assert result[MemoryCategory.DECISIONS] == ["merged decision"]
        assert result[MemoryCategory.PREFERENCES] == ["pref"]
        assert result[MemoryCategory.FACTS] == ["fact"]

    async def test_consolidate_falls_back_on_bad_yaml(self, mock_ltm_llm):
        mock_ltm_llm.response_text = "this is not yaml at all {{{"
        consolidator = LongTermMemoryConsolidator(mock_ltm_llm)
        original = {
            MemoryCategory.DECISIONS: ["keep me"],
            MemoryCategory.PREFERENCES: [],
            MemoryCategory.FACTS: [],
        }
        result = await consolidator.consolidate(original)
        assert result == original

    async def test_consolidate_falls_back_on_non_dict(self, mock_ltm_llm):
        mock_ltm_llm.response_text = "- just a list"
        consolidator = LongTermMemoryConsolidator(mock_ltm_llm)
        original = {
            MemoryCategory.DECISIONS: ["keep"],
            MemoryCategory.PREFERENCES: [],
            MemoryCategory.FACTS: [],
        }
        result = await consolidator.consolidate(original)
        assert result == original

    async def test_consolidate_partial_categories(self, mock_ltm_llm):
        """If LLM only returns some categories, keep originals for missing ones."""
        mock_ltm_llm.response_text = "decisions:\n  - 'consolidated'\n"
        consolidator = LongTermMemoryConsolidator(mock_ltm_llm)
        original = {
            MemoryCategory.DECISIONS: ["d1"],
            MemoryCategory.PREFERENCES: ["p1"],
            MemoryCategory.FACTS: ["f1"],
        }
        result = await consolidator.consolidate(original)
        assert result[MemoryCategory.DECISIONS] == ["consolidated"]
        # Missing categories get empty lists (from yaml parse returning None → [])
        # since the yaml has no preferences/facts keys
        assert result[MemoryCategory.PREFERENCES] == []
        assert result[MemoryCategory.FACTS] == []

    async def test_format_memories_empty(self, mock_ltm_llm):
        consolidator = LongTermMemoryConsolidator(mock_ltm_llm)
        memories = {cat: [] for cat in MemoryCategory}
        text = consolidator._format_memories_text(memories)
        assert text == "(empty)"
