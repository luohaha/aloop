"""Long-term memory system for persistent knowledge storage.

This module provides a simple, agentic long-term memory system that allows
the AI to autonomously save and recall important information across sessions.
"""

import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import aiofiles
import aiofiles.os
import yaml

# Try to import rapidfuzz for better fuzzy matching, fall back to simple matching
try:
    from rapidfuzz import fuzz

    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False


@dataclass
class Memory:
    """A single memory entry."""

    id: str
    content: str
    category: str
    created_at: str
    keywords: list[str] = field(default_factory=list)


@dataclass
class SearchResult:
    """A memory search result with relevance score."""

    memory: Memory
    score: float


class LongTermMemory:
    """Long-term memory storage with keyword-based retrieval.

    Stores memories in a human-readable YAML file at ~/.aloop/memory/memories.yaml.
    Supports keyword extraction and fuzzy matching for retrieval.
    """

    VERSION = 1

    def __init__(self, memory_dir: Optional[str] = None):
        """Initialize long-term memory.

        Args:
            memory_dir: Optional custom directory for memory storage.
                       Defaults to ~/.aloop/memory/
        """
        if memory_dir is None:
            memory_dir = os.path.join(os.path.expanduser("~"), ".aloop", "memory")
        self.memory_dir = memory_dir
        self.memory_file = os.path.join(memory_dir, "memories.yaml")
        self._memories: list[Memory] = []
        self._loaded = False

    async def _ensure_dir(self) -> None:
        """Ensure the memory directory exists."""
        if not await aiofiles.os.path.exists(self.memory_dir):
            os.makedirs(self.memory_dir, exist_ok=True)

    async def _load(self) -> None:
        """Load memories from YAML file."""
        if self._loaded:
            return

        if not await aiofiles.os.path.exists(self.memory_file):
            self._memories = []
            self._loaded = True
            return

        async with aiofiles.open(self.memory_file, encoding="utf-8") as f:
            content = await f.read()

        if not content.strip():
            self._memories = []
            self._loaded = True
            return

        data = yaml.safe_load(content)
        if not data or "memories" not in data:
            self._memories = []
            self._loaded = True
            return

        self._memories = [
            Memory(
                id=m.get("id", str(uuid.uuid4())[:8]),
                content=m.get("content", ""),
                category=m.get("category", "general"),
                created_at=m.get("created_at", datetime.now().isoformat()),
                keywords=m.get("keywords", []),
            )
            for m in data.get("memories", [])
        ]
        self._loaded = True

    async def _save(self) -> None:
        """Save memories to YAML file."""
        await self._ensure_dir()

        data = {
            "version": self.VERSION,
            "updated_at": datetime.now().isoformat(),
            "memories": [
                {
                    "id": m.id,
                    "content": m.content,
                    "category": m.category,
                    "created_at": m.created_at,
                    "keywords": m.keywords,
                }
                for m in self._memories
            ],
        }

        yaml_content = yaml.dump(
            data, allow_unicode=True, default_flow_style=False, sort_keys=False
        )

        async with aiofiles.open(self.memory_file, "w", encoding="utf-8") as f:
            await f.write(yaml_content)

    def _extract_keywords(self, content: str) -> list[str]:
        """Extract keywords from content.

        Uses a simple approach: extract meaningful words, filter out common stop words,
        and keep unique terms.

        Args:
            content: The text to extract keywords from.

        Returns:
            List of keywords.
        """
        # Common stop words to filter out
        stop_words = {
            "a",
            "an",
            "the",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "of",
            "at",
            "by",
            "for",
            "with",
            "about",
            "against",
            "between",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "to",
            "from",
            "up",
            "down",
            "in",
            "out",
            "on",
            "off",
            "over",
            "under",
            "again",
            "further",
            "then",
            "once",
            "here",
            "there",
            "when",
            "where",
            "why",
            "how",
            "all",
            "each",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "no",
            "nor",
            "not",
            "only",
            "own",
            "same",
            "so",
            "than",
            "too",
            "very",
            "just",
            "and",
            "but",
            "if",
            "or",
            "because",
            "as",
            "until",
            "while",
            "this",
            "that",
            "these",
            "those",
            "it",
            "its",
            "i",
            "me",
            "my",
            "myself",
            "we",
            "our",
            "ours",
            "you",
            "your",
            "yours",
            "he",
            "him",
            "his",
            "she",
            "her",
            "hers",
            "they",
            "them",
            "their",
            "what",
            "which",
            "who",
            "whom",
            # Chinese stop words
            "的",
            "是",
            "在",
            "了",
            "和",
            "与",
            "也",
            "都",
            "而",
            "及",
            "着",
            "或",
            "一个",
            "没有",
            "我",
            "你",
            "他",
            "她",
            "它",
            "我们",
            "你们",
            "他们",
            "这",
            "那",
            "这个",
            "那个",
        }

        # Extract words (including Chinese characters)
        words = re.findall(r"[\w\u4e00-\u9fff]+", content.lower())

        # Filter and deduplicate
        keywords = []
        seen = set()
        for word in words:
            if word not in stop_words and len(word) > 1 and word not in seen:
                keywords.append(word)
                seen.add(word)

        return keywords[:20]  # Limit to top 20 keywords

    def _calculate_score(self, memory: Memory, query: str, query_keywords: list[str]) -> float:
        """Calculate relevance score for a memory.

        Uses a combination of:
        1. Exact keyword matches (highest weight)
        2. Fuzzy content matching
        3. Word overlap

        Args:
            memory: The memory to score.
            query: The search query.
            query_keywords: Pre-extracted keywords from query.

        Returns:
            Relevance score (0-100).
        """
        score = 0.0

        # 1. Exact keyword matches (40 points max)
        memory_keywords_lower = {k.lower() for k in memory.keywords}
        query_keywords_lower = {k.lower() for k in query_keywords}
        keyword_matches = len(memory_keywords_lower & query_keywords_lower)
        if query_keywords_lower:
            keyword_score = (keyword_matches / len(query_keywords_lower)) * 40
            score += keyword_score

        # 2. Fuzzy content matching (40 points max)
        if RAPIDFUZZ_AVAILABLE:
            # Use token_set_ratio for better partial matching
            fuzzy_score = fuzz.token_set_ratio(query.lower(), memory.content.lower())
            score += (fuzzy_score / 100) * 40
        else:
            # Simple substring matching fallback
            query_lower = query.lower()
            content_lower = memory.content.lower()
            if query_lower in content_lower:
                score += 40
            else:
                # Check for word overlap
                query_words = set(query_lower.split())
                content_words = set(content_lower.split())
                overlap = len(query_words & content_words)
                if query_words:
                    score += (overlap / len(query_words)) * 30

        # 3. Category bonus (10 points if category matches a keyword)
        if memory.category.lower() in query_keywords_lower:
            score += 10

        # 4. Recency bonus (10 points max, decay over time)
        try:
            created = datetime.fromisoformat(memory.created_at)
            days_old = (datetime.now() - created).days
            recency_score = max(0, 10 - (days_old / 30))  # Decay over 30 days
            score += recency_score
        except (ValueError, TypeError):
            pass

        return min(100, score)

    async def save(self, content: str, category: str = "general") -> Memory:
        """Save a new memory.

        Args:
            content: The content to remember.
            category: Category for organization (default: "general").
                     Common categories: preferences, project, decision, fact

        Returns:
            The created Memory object.
        """
        await self._load()

        memory = Memory(
            id=str(uuid.uuid4())[:8],
            content=content,
            category=category,
            created_at=datetime.now().isoformat(),
            keywords=self._extract_keywords(content),
        )

        self._memories.append(memory)
        await self._save()

        return memory

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 5,
        min_score: float = 10.0,
    ) -> list[SearchResult]:
        """Search for relevant memories.

        Args:
            query: Search query.
            category: Optional category filter.
            limit: Maximum number of results (default: 5).
            min_score: Minimum relevance score to include (default: 10.0).

        Returns:
            List of SearchResult objects sorted by relevance.
        """
        await self._load()

        if not self._memories:
            return []

        query_keywords = self._extract_keywords(query)
        results = []

        for memory in self._memories:
            # Filter by category if specified
            if category and memory.category.lower() != category.lower():
                continue

            score = self._calculate_score(memory, query, query_keywords)

            if score >= min_score:
                results.append(SearchResult(memory=memory, score=score))

        # Sort by score (highest first) and limit results
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    async def list_all(self, category: Optional[str] = None) -> list[Memory]:
        """List all memories, optionally filtered by category.

        Args:
            category: Optional category filter.

        Returns:
            List of Memory objects.
        """
        await self._load()

        if category:
            return [m for m in self._memories if m.category.lower() == category.lower()]
        return list(self._memories)

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID.

        Args:
            memory_id: The ID of the memory to delete.

        Returns:
            True if deleted, False if not found.
        """
        await self._load()

        for i, memory in enumerate(self._memories):
            if memory.id == memory_id:
                del self._memories[i]
                await self._save()
                return True

        return False

    async def clear(self, category: Optional[str] = None) -> int:
        """Clear memories, optionally only from a specific category.

        Args:
            category: Optional category to clear. If None, clears all.

        Returns:
            Number of memories deleted.
        """
        await self._load()

        if category:
            original_count = len(self._memories)
            self._memories = [m for m in self._memories if m.category.lower() != category.lower()]
            deleted = original_count - len(self._memories)
        else:
            deleted = len(self._memories)
            self._memories = []

        if deleted > 0:
            await self._save()

        return deleted
