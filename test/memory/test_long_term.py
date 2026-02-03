"""Tests for long-term memory system."""

import pytest

from memory.long_term import LongTermMemory


@pytest.fixture
async def memory(tmp_path):
    """Create a LongTermMemory instance with a temp directory."""
    memory_dir = str(tmp_path / "memory")
    mem = LongTermMemory(memory_dir=memory_dir)
    return mem


class TestLongTermMemory:
    """Tests for LongTermMemory class."""

    async def test_save_creates_memory(self, memory):
        """Test that save creates a memory with correct fields."""
        saved = await memory.save("User prefers pytest", category="preferences")

        assert saved.id is not None
        assert saved.content == "User prefers pytest"
        assert saved.category == "preferences"
        assert saved.created_at is not None
        assert len(saved.keywords) > 0

    async def test_save_extracts_keywords(self, memory):
        """Test that keywords are extracted from content."""
        saved = await memory.save("User prefers pytest over unittest for testing Python code")

        # Should extract meaningful keywords
        keywords_lower = [k.lower() for k in saved.keywords]
        assert "pytest" in keywords_lower
        assert "unittest" in keywords_lower
        assert "python" in keywords_lower

    async def test_save_filters_stop_words(self, memory):
        """Test that stop words are filtered from keywords."""
        saved = await memory.save("The user is a developer who likes to code")

        keywords_lower = [k.lower() for k in saved.keywords]
        # Stop words should be filtered
        assert "the" not in keywords_lower
        assert "is" not in keywords_lower
        assert "to" not in keywords_lower
        # Meaningful words should be kept
        assert "user" in keywords_lower
        assert "developer" in keywords_lower

    async def test_save_persists_to_file(self, memory, tmp_path):
        """Test that memories are persisted to YAML file."""
        await memory.save("Test memory content", category="test")

        # Check file exists
        memory_file = tmp_path / "memory" / "memories.yaml"
        assert memory_file.exists()

        # Check content
        content = memory_file.read_text()
        assert "Test memory content" in content
        assert "category: test" in content

    async def test_search_returns_relevant_results(self, memory):
        """Test that search returns relevant memories."""
        await memory.save("User prefers pytest for testing", category="preferences")
        await memory.save("Project uses black for formatting", category="project")
        await memory.save("Always use type hints in Python", category="preferences")

        results = await memory.search("pytest testing")

        assert len(results) > 0
        # First result should be about pytest
        assert "pytest" in results[0].memory.content.lower()

    async def test_search_filters_by_category(self, memory):
        """Test that search can filter by category."""
        await memory.save("User prefers pytest", category="preferences")
        await memory.save("Project uses pytest", category="project")

        results = await memory.search("pytest", category="preferences")

        assert len(results) == 1
        assert results[0].memory.category == "preferences"

    async def test_search_respects_limit(self, memory):
        """Test that search respects the limit parameter."""
        for i in range(10):
            await memory.save(f"Memory about Python topic {i}", category="fact")

        results = await memory.search("Python", limit=3)

        assert len(results) <= 3

    async def test_search_returns_empty_for_no_matches(self, memory):
        """Test that search returns empty list when nothing matches with high min_score."""
        await memory.save("User prefers pytest", category="preferences")

        # Use higher min_score to exclude results that only have recency bonus
        results = await memory.search("completely unrelated xyz123", min_score=30.0)

        assert len(results) == 0

    async def test_search_fuzzy_matching(self, memory):
        """Test that fuzzy matching works for similar terms."""
        await memory.save("User prefers pytest for testing Python applications")

        # Should match despite slight differences
        results = await memory.search("pytest python test")

        assert len(results) > 0
        assert results[0].score > 0

    async def test_list_all_returns_all_memories(self, memory):
        """Test that list_all returns all stored memories."""
        await memory.save("Memory 1", category="a")
        await memory.save("Memory 2", category="b")
        await memory.save("Memory 3", category="a")

        all_memories = await memory.list_all()

        assert len(all_memories) == 3

    async def test_list_all_filters_by_category(self, memory):
        """Test that list_all can filter by category."""
        await memory.save("Memory 1", category="a")
        await memory.save("Memory 2", category="b")
        await memory.save("Memory 3", category="a")

        filtered = await memory.list_all(category="a")

        assert len(filtered) == 2
        assert all(m.category == "a" for m in filtered)

    async def test_delete_removes_memory(self, memory):
        """Test that delete removes a memory by ID."""
        saved = await memory.save("To be deleted", category="test")
        memory_id = saved.id

        result = await memory.delete(memory_id)

        assert result is True
        all_memories = await memory.list_all()
        assert len(all_memories) == 0

    async def test_delete_returns_false_for_unknown_id(self, memory):
        """Test that delete returns False for non-existent ID."""
        result = await memory.delete("nonexistent")

        assert result is False

    async def test_clear_removes_all_memories(self, memory):
        """Test that clear removes all memories."""
        await memory.save("Memory 1")
        await memory.save("Memory 2")
        await memory.save("Memory 3")

        deleted = await memory.clear()

        assert deleted == 3
        all_memories = await memory.list_all()
        assert len(all_memories) == 0

    async def test_clear_by_category(self, memory):
        """Test that clear can target a specific category."""
        await memory.save("Memory 1", category="keep")
        await memory.save("Memory 2", category="delete")
        await memory.save("Memory 3", category="delete")

        deleted = await memory.clear(category="delete")

        assert deleted == 2
        remaining = await memory.list_all()
        assert len(remaining) == 1
        assert remaining[0].category == "keep"

    async def test_persistence_across_instances(self, tmp_path):
        """Test that memories persist across different instances."""
        memory_dir = str(tmp_path / "memory")

        # Save with first instance
        mem1 = LongTermMemory(memory_dir=memory_dir)
        await mem1.save("Persistent memory", category="test")

        # Load with new instance
        mem2 = LongTermMemory(memory_dir=memory_dir)
        results = await mem2.search("Persistent")

        assert len(results) == 1
        assert results[0].memory.content == "Persistent memory"

    async def test_chinese_content_and_keywords(self, memory):
        """Test that Chinese content is handled correctly."""
        saved = await memory.save("用户偏好使用中文注释编写代码", category="preferences")

        # Should extract Chinese keywords
        assert len(saved.keywords) > 0

        # Should be searchable
        results = await memory.search("中文注释")
        assert len(results) > 0

    async def test_keyword_extraction_limits(self, memory):
        """Test that keyword extraction is limited to prevent excessive keywords."""
        # Create content with many words
        long_content = " ".join([f"word{i}" for i in range(100)])
        saved = await memory.save(long_content)

        # Keywords should be limited
        assert len(saved.keywords) <= 20


class TestKeywordExtraction:
    """Tests for keyword extraction functionality."""

    async def test_extracts_meaningful_words(self, memory):
        """Test extraction of meaningful words."""
        saved = await memory.save("Python developer prefers pytest framework")

        keywords = [k.lower() for k in saved.keywords]
        assert "python" in keywords
        assert "developer" in keywords
        assert "pytest" in keywords
        assert "framework" in keywords

    async def test_handles_mixed_language(self, memory):
        """Test handling of mixed language content."""
        saved = await memory.save("User prefers Python 用户喜欢")

        # Should have both English and Chinese keywords
        assert len(saved.keywords) > 0

    async def test_deduplicates_keywords(self, memory):
        """Test that duplicate keywords are removed."""
        saved = await memory.save("python Python PYTHON pyTHon")

        # Should only have one 'python' keyword
        keywords_lower = [k.lower() for k in saved.keywords]
        assert keywords_lower.count("python") == 1


class TestSearchScoring:
    """Tests for search scoring functionality."""

    async def test_exact_match_scores_higher(self, memory):
        """Test that exact keyword matches score higher than fuzzy matches."""
        await memory.save("pytest is the best testing framework", category="fact")
        await memory.save("testing code is important", category="fact")

        results = await memory.search("pytest")

        # pytest exact match should be first
        assert "pytest" in results[0].memory.content.lower()
        assert results[0].score > results[1].score if len(results) > 1 else True

    async def test_category_match_adds_score(self, memory):
        """Test that matching category in query adds to score."""
        await memory.save("Use pytest for testing", category="preferences")

        results = await memory.search("preferences testing")

        # Should have higher score due to category match
        assert len(results) > 0
        assert results[0].memory.category == "preferences"

    async def test_min_score_filtering(self, memory):
        """Test that results below min_score are filtered out."""
        await memory.save("completely unrelated content xyz")

        results = await memory.search("pytest testing", min_score=50.0)

        # Should filter out low-scoring results
        for result in results:
            assert result.score >= 50.0
