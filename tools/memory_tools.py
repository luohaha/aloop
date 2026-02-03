"""Memory tools for long-term knowledge persistence.

These tools allow the AI to autonomously save and recall important information
across sessions, enabling persistent learning and context retention.
"""

from typing import Any, Optional

from memory.long_term import LongTermMemory

from .base import BaseTool

# Shared instance for tools to use
_long_term_memory: Optional[LongTermMemory] = None


def get_long_term_memory() -> LongTermMemory:
    """Get or create the shared LongTermMemory instance."""
    global _long_term_memory
    if _long_term_memory is None:
        _long_term_memory = LongTermMemory()
    return _long_term_memory


class MemorySaveTool(BaseTool):
    """Tool for saving important information to long-term memory.

    Use this tool to persist knowledge that should be remembered across sessions:
    - User preferences and working styles
    - Project-specific conventions and rules
    - Important decisions and their rationale
    - Frequently referenced facts or information
    """

    @property
    def name(self) -> str:
        return "memory_save"

    @property
    def description(self) -> str:
        return """Save important information to long-term memory for future reference.

USE THIS TOOL WHEN:
- You learn a user preference (e.g., "user prefers pytest over unittest")
- You discover project conventions (e.g., "this project uses snake_case")
- An important decision is made (e.g., "decided to use Redis for caching")
- Information will likely be useful in future sessions

CATEGORIES:
- "preferences": User preferences and working styles
- "project": Project-specific rules and conventions
- "decision": Important decisions and rationale
- "fact": General facts or reference information
- "general": Default category for other information

TIPS:
- Be specific and concise in what you save
- Include context (why this matters)
- Don't save trivial or temporary information"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "content": {
                "type": "string",
                "description": "The information to remember. Be specific and include relevant context.",
            },
            "category": {
                "type": "string",
                "description": "Category for organization: preferences, project, decision, fact, or general",
                "default": "general",
            },
        }

    async def execute(self, content: str, category: str = "general") -> str:
        """Save information to long-term memory."""
        if not content or not content.strip():
            return "Error: Content cannot be empty."

        # Validate category
        valid_categories = {"preferences", "project", "decision", "fact", "general"}
        if category.lower() not in valid_categories:
            category = "general"

        memory = get_long_term_memory()
        saved = await memory.save(content=content.strip(), category=category.lower())

        return f"Saved to long-term memory (ID: {saved.id}, category: {saved.category}). Keywords: {', '.join(saved.keywords[:5])}"


class MemoryRecallTool(BaseTool):
    """Tool for recalling information from long-term memory.

    Use this tool to retrieve previously saved knowledge that may be
    relevant to the current task or conversation.
    """

    @property
    def name(self) -> str:
        return "memory_recall"

    @property
    def description(self) -> str:
        return """Search long-term memory for relevant information.

USE THIS TOOL WHEN:
- Starting a new task (check for relevant preferences/conventions)
- Uncertain about user preferences or project rules
- Need to recall a previous decision or its rationale
- Looking for previously saved reference information

SEARCH TIPS:
- Use descriptive queries with key terms
- Filter by category if you know what type of information you need
- Results are ranked by relevance

Returns memories matching your query, sorted by relevance score."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "query": {
                "type": "string",
                "description": "Search query describing what you're looking for",
            },
            "category": {
                "type": "string",
                "description": "Optional: filter by category (preferences, project, decision, fact, general)",
                "default": "",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 5)",
                "default": 5,
            },
        }

    async def execute(self, query: str, category: str = "", limit: int = 5) -> str:
        """Search long-term memory for relevant information."""
        if not query or not query.strip():
            return "Error: Query cannot be empty."

        memory = get_long_term_memory()

        # Handle category filter
        category_filter = category.strip().lower() if category else None
        if category_filter and category_filter not in {
            "preferences",
            "project",
            "decision",
            "fact",
            "general",
        }:
            category_filter = None

        # Ensure limit is reasonable
        limit = max(1, min(20, limit))

        results = await memory.search(
            query=query.strip(),
            category=category_filter,
            limit=limit,
        )

        if not results:
            return "No relevant memories found."

        # Format results
        output_lines = [f"Found {len(results)} relevant memories:\n"]

        for i, result in enumerate(results, 1):
            m = result.memory
            output_lines.append(f"{i}. [{m.category}] (score: {result.score:.1f})")
            output_lines.append(f"   {m.content}")
            output_lines.append(f"   (ID: {m.id}, saved: {m.created_at[:10]})")
            output_lines.append("")

        return "\n".join(output_lines)
