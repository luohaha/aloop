"""Short-term memory management without silent eviction."""

from typing import List

from llm.base import LLMMessage


class ShortTermMemory:
    """Manages recent messages in a growable list.

    Unlike the previous deque-based implementation, messages are never
    silently evicted.  The ``max_size`` parameter serves only as an
    emergency cap — ``is_full()`` returns True when the cap is reached,
    signalling that compression should happen.
    """

    def __init__(self, max_size: int = 500):
        """Initialize short-term memory.

        Args:
            max_size: Emergency cap on message count (triggers compression)
        """
        self.max_size = max_size
        self.messages: List[LLMMessage] = []

    def add_message(self, message: LLMMessage) -> None:
        """Add a message to short-term memory.

        Messages are never silently dropped.  Callers should check
        ``is_full()`` and trigger compression instead.

        Args:
            message: LLMMessage to add
        """
        self.messages.append(message)

    def get_messages(self) -> List[LLMMessage]:
        """Get all messages in short-term memory.

        Returns:
            List of messages, oldest to newest
        """
        return list(self.messages)

    def clear(self) -> List[LLMMessage]:
        """Clear all messages and return them.

        Returns:
            List of all messages that were cleared
        """
        messages = list(self.messages)
        self.messages.clear()
        return messages

    def remove_first(self, count: int) -> List[LLMMessage]:
        """Remove the first N messages (oldest) from memory.

        This is useful after compression to remove only the compressed messages
        while preserving any new messages that arrived during compression.

        Args:
            count: Number of messages to remove from the front

        Returns:
            List of removed messages
        """
        count = min(count, len(self.messages))
        removed = self.messages[:count]
        self.messages = self.messages[count:]
        return removed

    def is_full(self) -> bool:
        """Check if short-term memory has reached the emergency cap.

        Returns:
            True if at or above the emergency cap
        """
        return len(self.messages) >= self.max_size

    def count(self) -> int:
        """Get current message count.

        Returns:
            Number of messages in short-term memory
        """
        return len(self.messages)

    def remove_last(self, count: int = 1) -> None:
        """Remove the last N messages (newest) from memory.

        This is useful for rolling back incomplete exchanges (e.g., after interruption).

        Args:
            count: Number of messages to remove from the end (default: 1)
        """
        count = min(count, len(self.messages))
        if count > 0:
            self.messages = self.messages[:-count]
