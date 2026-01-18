"""Tool for retrieving externally stored tool results."""

import logging
from typing import TYPE_CHECKING, Any, Dict

from .base import BaseTool

if TYPE_CHECKING:
    from memory import MemoryManager

logger = logging.getLogger(__name__)


class RetrieveToolResultTool(BaseTool):
    """Retrieve full content of externally stored tool results.

    When tool results are too large, they are stored externally and only
    a summary/reference is kept in memory. This tool allows retrieving
    the full content when needed.
    """

    def __init__(self, memory_manager: "MemoryManager"):
        """Initialize tool.

        Args:
            memory_manager: MemoryManager instance with tool result storage
        """
        self.memory_manager = memory_manager

    @property
    def name(self) -> str:
        return "retrieve_tool_result"

    @property
    def description(self) -> str:
        return (
            "Retrieve the full content of a tool result that was stored externally. "
            "Use this when you see a '[Tool Result #...]' reference in the conversation "
            "and need to access the complete output. The result_id can be found in the "
            "reference message (e.g., 'Tool Result #read_file_abc123')."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "result_id": {
                "type": "string",
                "description": (
                    "The ID of the stored tool result (found in the reference message, "
                    "e.g., 'read_file_abc123')"
                ),
            }
        }

    def execute(self, result_id: str) -> str:
        """Retrieve a stored tool result.

        Args:
            result_id: ID of the stored result

        Returns:
            Full content or error message
        """
        try:
            # Retrieve the result
            content = self.memory_manager.retrieve_tool_result(result_id)

            if content is None:
                return (
                    f"Error: Tool result '{result_id}' not found in storage. "
                    f"It may have been cleaned up or the ID is incorrect."
                )

            # Get metadata for context
            metadata = self.memory_manager.tool_result_store.get_metadata(result_id)
            header = f"[Retrieved Tool Result #{result_id}]\n"
            if metadata:
                header += f"Tool: {metadata['tool_name']}\n"
                header += f"Size: {metadata['content_length']} characters\n"
                header += f"Created: {metadata['created_at']}\n\n"

            return header + content

        except Exception as e:
            logger.error(f"Error retrieving tool result {result_id}: {e}")
            return f"Error retrieving tool result: {str(e)}"
