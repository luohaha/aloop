"""Core memory manager that orchestrates all memory operations."""

import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from config import Config
from llm.content_utils import content_has_tool_calls
from llm.message_types import LLMMessage
from utils import terminal_ui
from utils.tui.progress import AsyncSpinner

from .compressor import WorkingMemoryCompressor
from .short_term import ShortTermMemory
from .token_tracker import TokenTracker
from .types import CompressedMemory, CompressionStrategy

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from llm import LiteLLMAdapter

    from .long_term import LongTermMemoryManager


class CompressionUrgency:
    """Urgency levels for compression decisions."""

    NONE = "none"
    SOFT = "soft"  # 60% of hard limit → partial compression
    HARD = "hard"  # Hard limit → full compression
    EMERGENCY = "emergency"  # Emergency cap → full compression


class MemoryManager:
    """Central memory management system with built-in persistence.

    The persistence store is fully owned by MemoryManager and should not
    be created or passed in from outside.
    """

    def __init__(
        self,
        llm: "LiteLLMAdapter",
        session_id: Optional[str] = None,
    ):
        """Initialize memory manager.

        Args:
            llm: LLM instance for compression
            session_id: Optional session ID (if resuming session)
        """
        self.llm = llm

        # Store is fully owned by MemoryManager
        from .store import YamlFileMemoryStore

        self._store = YamlFileMemoryStore()

        # Lazy session creation: only create when first message is added
        # If session_id is provided (resuming), use it immediately
        if session_id is not None:
            self.session_id = session_id
            self._session_created = True
        else:
            self.session_id = None
            self._session_created = False

        # Initialize components using Config directly
        self.short_term = ShortTermMemory(max_size=Config.MEMORY_SHORT_TERM_SIZE)
        self.compressor = WorkingMemoryCompressor(llm)
        self.token_tracker = TokenTracker()

        # Storage for system messages
        self.system_messages: List[LLMMessage] = []

        # State tracking
        self.current_tokens = 0
        self.was_compressed_last_iteration = False
        self.last_compression_savings = 0
        self.compression_count = 0

        # API-grounded token tracking (Step 2)
        self._last_api_context_tokens: Optional[int] = None
        self._estimated_delta_tokens: int = 0

        # Optional callback to get current todo context for compression
        self._todo_context_provider: Optional[Callable[[], Optional[str]]] = None

        # Long-term memory (cross-session)
        self._long_term = None
        if Config.LONG_TERM_MEMORY_ENABLED:
            from .long_term import LongTermMemoryManager

            self._long_term = LongTermMemoryManager(llm)

    @classmethod
    async def from_session(
        cls,
        session_id: str,
        llm: "LiteLLMAdapter",
    ) -> "MemoryManager":
        """Load a MemoryManager from a saved session.

        Args:
            session_id: Session ID to load
            llm: LLM instance for compression

        Returns:
            MemoryManager instance with loaded state
        """
        manager = cls(llm=llm, session_id=session_id)

        # Load session data
        session_data = await manager._store.load_session(session_id)
        if not session_data:
            raise ValueError(f"Session {session_id} not found")

        # Restore state
        manager.system_messages = session_data["system_messages"]

        # Add messages to short-term memory (including any summary messages)
        for msg in session_data["messages"]:
            manager.short_term.add_message(msg)

        # Recalculate tokens
        manager.current_tokens = manager._recalculate_current_tokens()

        logger.info(
            f"Loaded session {session_id}: "
            f"{len(session_data['messages'])} messages, "
            f"{manager.current_tokens} tokens"
        )

        return manager

    @staticmethod
    async def list_sessions(limit: int = 50) -> List[Dict[str, Any]]:
        """List saved sessions.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of session summaries
        """
        from .store import YamlFileMemoryStore

        store = YamlFileMemoryStore()
        return await store.list_sessions(limit=limit)

    @staticmethod
    async def find_latest_session() -> Optional[str]:
        """Find the most recently updated session ID.

        Returns:
            Session ID or None if no sessions exist
        """
        from .store import YamlFileMemoryStore

        store = YamlFileMemoryStore()
        return await store.find_latest_session()

    @staticmethod
    async def find_session_by_prefix(prefix: str) -> Optional[str]:
        """Find a session by ID prefix.

        Args:
            prefix: Prefix of session UUID

        Returns:
            Full session ID or None
        """
        from .store import YamlFileMemoryStore

        store = YamlFileMemoryStore()
        return await store.find_session_by_prefix(prefix)

    async def _ensure_session(self) -> None:
        """Lazily create session when first needed.

        This avoids creating empty sessions when MemoryManager is instantiated
        but no messages are ever added (e.g., user exits before running any task).

        Raises:
            RuntimeError: If session creation fails
        """
        if not self._session_created:
            try:
                self.session_id = await self._store.create_session()
                self._session_created = True
                logger.info(f"Created new session: {self.session_id}")
            except Exception as e:
                logger.error(f"Failed to create session: {e}")
                raise RuntimeError(f"Failed to create memory session: {e}") from e

    async def add_message(self, message: LLMMessage, actual_tokens: Dict[str, int] = None) -> None:
        """Add a message to memory and trigger compression if needed.

        Args:
            message: Message to add
            actual_tokens: Optional dict with actual token counts from LLM response
                          Format: {"input": int, "output": int}
        """
        # Ensure session exists before adding messages
        await self._ensure_session()

        # Track system messages separately
        if message.role == "system":
            self.system_messages.append(message)
            return

        # Count tokens (use actual if provided, otherwise estimate)
        if actual_tokens:
            # Use actual token counts from LLM response
            input_tokens = actual_tokens.get("input", 0)
            output_tokens = actual_tokens.get("output", 0)

            self.token_tracker.add_input_tokens(input_tokens)
            self.token_tracker.add_output_tokens(output_tokens)

            # API-grounded tracking: use API-reported input_tokens as authoritative
            # context size (it includes everything sent to the API)
            self._last_api_context_tokens = input_tokens + output_tokens
            self._estimated_delta_tokens = 0

            # Log API usage separately
            logger.debug(
                f"API usage: input={input_tokens}, output={output_tokens}, "
                f"total={input_tokens + output_tokens}"
            )
        else:
            # Non-API messages: estimate only this message's tokens and add to delta
            provider = self.llm.provider_name.lower()
            model = self.llm.model
            msg_tokens = self.token_tracker.count_message_tokens(message, provider, model)
            self._estimated_delta_tokens += msg_tokens

        # Add to short-term memory
        self.short_term.add_message(message)

        # Update current_tokens using grounded tracking when available
        if self._last_api_context_tokens is not None:
            self.current_tokens = self._last_api_context_tokens + self._estimated_delta_tokens
        else:
            # Fall back to full estimation (before first API call)
            self.current_tokens = self._recalculate_current_tokens()

        # Log memory state (stored content size, not API usage)
        logger.debug(
            f"Memory state: {self.current_tokens} stored tokens, "
            f"{self.short_term.count()}/{Config.MEMORY_SHORT_TERM_SIZE} messages, "
            f"full={self.short_term.is_full()}"
        )

        # Check if compression is needed
        self.was_compressed_last_iteration = False
        urgency = self._get_compression_urgency()
        if urgency != CompressionUrgency.NONE:
            logger.info(f"🗜️  Triggering compression: urgency={urgency}")
            await self.compress(urgency=urgency)
        else:
            # Log compression check details
            logger.debug(
                f"Compression check: stored={self.current_tokens}, "
                f"threshold={Config.MEMORY_COMPRESSION_THRESHOLD}, "
                f"soft_threshold={int(Config.MEMORY_COMPRESSION_THRESHOLD * Config.MEMORY_SOFT_THRESHOLD_RATIO)}, "
                f"messages={self.short_term.count()}"
            )

    def get_context_for_llm(self) -> List[LLMMessage]:
        """Get optimized context for LLM call.

        Returns:
            List of messages: system messages + short-term messages (which includes summaries)
        """
        context = []

        # 1. Add system messages (always included)
        context.extend(self.system_messages)

        # 2. Add short-term memory (includes summary messages and recent messages)
        context.extend(self.short_term.get_messages())

        return context

    @property
    def long_term(self) -> Optional["LongTermMemoryManager"]:
        """Access the long-term memory manager (None if disabled)."""
        return self._long_term

    def set_todo_context_provider(self, provider: Callable[[], Optional[str]]) -> None:
        """Set a callback to provide current todo context for compression.

        The provider should return a formatted string of current todo items,
        or None if no todos exist. This context will be injected into
        compression summaries to preserve task state.

        Args:
            provider: Callable that returns current todo context string or None
        """
        self._todo_context_provider = provider

    async def compress(
        self, strategy: str = None, urgency: str = CompressionUrgency.HARD
    ) -> Optional[CompressedMemory]:
        """Compress current short-term memory.

        After compression, the compressed messages (including any summary as user message)
        are put back into short_term as regular messages.

        Args:
            strategy: Compression strategy (None = auto-select)
            urgency: Compression urgency level (SOFT = partial, HARD/EMERGENCY = full)

        Returns:
            CompressedMemory object if compression was performed
        """
        messages = self.short_term.get_messages()
        message_count = len(messages)

        if not messages:
            logger.warning("No messages to compress")
            return None

        # For SOFT urgency, only compress the oldest portion
        if urgency == CompressionUrgency.SOFT and message_count > 4:
            split = self._find_safe_split_point(messages)
            if split > 0 and split < message_count:
                return await self._compress_partial(messages, split, strategy)

        # Full compression (HARD / EMERGENCY / fallback from SOFT)
        # Auto-select strategy if not specified
        if strategy is None:
            strategy = self._select_strategy(messages)

        logger.info(f"🗜️  Compressing {message_count} messages using {strategy} strategy")

        try:
            # Get todo context if provider is set
            todo_context = None
            if self._todo_context_provider:
                todo_context = self._todo_context_provider()

            # Perform compression with TUI spinner
            async with AsyncSpinner(terminal_ui.console, "Compressing memory..."):
                compressed = await self.compressor.compress(
                    messages,
                    strategy=strategy,
                    target_tokens=self._calculate_target_tokens(),
                    todo_context=todo_context,
                )

            # Track compression results
            self.compression_count += 1
            self.was_compressed_last_iteration = True
            self.last_compression_savings = compressed.token_savings

            # Update token tracker
            self.token_tracker.add_compression_savings(compressed.token_savings)
            self.token_tracker.add_compression_cost(compressed.compressed_tokens)

            # Remove compressed messages from short-term memory
            self.short_term.remove_first(message_count)

            # Get any remaining messages (added after compression started)
            remaining_messages = self.short_term.get_messages()
            self.short_term.clear()

            # Add compressed messages (summary + preserved, already combined by compressor)
            for msg in compressed.messages:
                self.short_term.add_message(msg)

            # Add any remaining messages
            for msg in remaining_messages:
                self.short_term.add_message(msg)

            # Reset API-grounded tracking after compression (context has changed)
            self._last_api_context_tokens = None
            self._estimated_delta_tokens = 0

            # Update current token count
            old_tokens = self.current_tokens
            self.current_tokens = self._recalculate_current_tokens()

            # Log compression results
            logger.info(
                f"✅ Compression complete: {compressed.original_tokens} → {compressed.compressed_tokens} tokens "
                f"({compressed.savings_percentage:.1f}% saved, ratio: {compressed.compression_ratio:.2f}), "
                f"context: {old_tokens} → {self.current_tokens} tokens, "
                f"short_term now has {self.short_term.count()} messages"
            )

            return compressed

        except Exception as e:
            logger.error(f"Compression failed: {e}")
            return None

    async def _compress_partial(
        self,
        messages: List[LLMMessage],
        split: int,
        strategy: str = None,
    ) -> Optional[CompressedMemory]:
        """Compress only the oldest portion of messages (soft compression).

        Args:
            messages: All messages
            split: Index to split at (compress messages[:split], keep messages[split:])
            strategy: Compression strategy (None = auto-select)

        Returns:
            CompressedMemory object if compression was performed
        """
        to_compress = messages[:split]
        to_keep = messages[split:]

        if strategy is None:
            strategy = self._select_strategy(to_compress)

        logger.info(
            f"🗜️  Soft compression: compressing {len(to_compress)} of {len(messages)} messages "
            f"(keeping {len(to_keep)}), strategy={strategy}"
        )

        try:
            todo_context = None
            if self._todo_context_provider:
                todo_context = self._todo_context_provider()

            async with AsyncSpinner(terminal_ui.console, "Compressing memory (partial)..."):
                compressed = await self.compressor.compress(
                    to_compress,
                    strategy=strategy,
                    target_tokens=self._calculate_target_tokens(),
                    todo_context=todo_context,
                )

            self.compression_count += 1
            self.was_compressed_last_iteration = True
            self.last_compression_savings = compressed.token_savings

            self.token_tracker.add_compression_savings(compressed.token_savings)
            self.token_tracker.add_compression_cost(compressed.compressed_tokens)

            # Remove the compressed portion from short-term
            self.short_term.remove_first(len(messages))

            # Get any remaining messages (added during compression)
            extra = self.short_term.get_messages()
            self.short_term.clear()

            # Rebuild: compressed summary + kept messages + any extras
            for msg in compressed.messages:
                self.short_term.add_message(msg)
            for msg in to_keep:
                self.short_term.add_message(msg)
            for msg in extra:
                self.short_term.add_message(msg)

            # Reset API-grounded tracking after compression
            self._last_api_context_tokens = None
            self._estimated_delta_tokens = 0

            old_tokens = self.current_tokens
            self.current_tokens = self._recalculate_current_tokens()

            logger.info(
                f"✅ Soft compression complete: {compressed.original_tokens} → {compressed.compressed_tokens} tokens "
                f"({compressed.savings_percentage:.1f}% saved), "
                f"context: {old_tokens} → {self.current_tokens} tokens, "
                f"short_term now has {self.short_term.count()} messages"
            )

            return compressed

        except Exception as e:
            logger.error(f"Partial compression failed: {e}")
            return None

    def _find_safe_split_point(self, messages: List[LLMMessage]) -> int:
        """Find a safe split point near the midpoint that doesn't break tool pairs.

        Args:
            messages: Messages to split

        Returns:
            Index to split at (compress messages[:index], keep messages[index:])
        """
        target = len(messages) // 2
        if target <= 0:
            return 0

        # Find tool pairs to know which indices must stay together
        tool_pairs, orphaned = self.compressor._find_tool_pairs(messages)

        # Build set of indices that are part of tool pairs
        pair_boundaries: set[int] = set()
        for assistant_idx, response_idx in tool_pairs:
            pair_boundaries.add(assistant_idx)
            pair_boundaries.add(response_idx)

        # Scan backward from target to find a split that doesn't break pairs
        for candidate in range(target, 0, -1):
            # Check: no pair spans the boundary (one index < candidate, another >= candidate)
            safe = True
            for assistant_idx, response_idx in tool_pairs:
                if assistant_idx < candidate <= response_idx:
                    safe = False
                    break
                if response_idx < candidate <= assistant_idx:
                    safe = False
                    break
            if safe:
                return candidate

        # No safe split found near midpoint, fall back to compressing everything
        return 0

    def _get_compression_urgency(self) -> str:
        """Determine compression urgency level.

        Returns:
            CompressionUrgency level
        """
        if not Config.MEMORY_ENABLED:
            return CompressionUrgency.NONE

        # Emergency: message count safety net
        if self.short_term.is_full():
            return CompressionUrgency.EMERGENCY

        # Hard limit: must compress
        if self.current_tokens > Config.MEMORY_COMPRESSION_THRESHOLD:
            return CompressionUrgency.HARD

        # Soft threshold: partial compression
        soft_threshold = int(
            Config.MEMORY_COMPRESSION_THRESHOLD * Config.MEMORY_SOFT_THRESHOLD_RATIO
        )
        if self.current_tokens > soft_threshold:
            return CompressionUrgency.SOFT

        return CompressionUrgency.NONE

    def _should_compress(self) -> tuple[bool, Optional[str]]:
        """Check if compression should be triggered.

        Returns:
            Tuple of (should_compress, reason)
        """
        urgency = self._get_compression_urgency()
        if urgency == CompressionUrgency.NONE:
            return False, None
        return True, f"urgency={urgency}"

    def _select_strategy(self, messages: List[LLMMessage]) -> str:
        """Auto-select compression strategy based on message characteristics.

        Args:
            messages: Messages to analyze

        Returns:
            Strategy name
        """
        # Check for tool calls
        has_tool_calls = any(self._message_has_tool_calls(msg) for msg in messages)

        # Select strategy
        if has_tool_calls:
            # Preserve tool calls
            return CompressionStrategy.SELECTIVE
        elif len(messages) < 5:
            # Too few messages, just delete
            return CompressionStrategy.DELETION
        else:
            # Default: sliding window
            return CompressionStrategy.SLIDING_WINDOW

    def _message_has_tool_calls(self, message: LLMMessage) -> bool:
        """Check if message contains tool calls.

        Handles both new format (tool_calls field) and legacy format (content blocks).

        Args:
            message: Message to check

        Returns:
            True if contains tool calls
        """
        # New format: check tool_calls field
        if hasattr(message, "tool_calls") and message.tool_calls:
            return True

        # New format: tool role message
        if message.role == "tool":
            return True

        # Legacy/centralized check on content
        return content_has_tool_calls(message.content)

    def _calculate_target_tokens(self) -> int:
        """Calculate target token count for compression.

        Returns:
            Target token count
        """
        original_tokens = self.current_tokens
        target = int(original_tokens * Config.MEMORY_COMPRESSION_RATIO)
        return max(target, 500)  # Minimum 500 tokens for summary

    def _recalculate_current_tokens(self) -> int:
        """Recalculate current token count from scratch.

        Returns:
            Current token count
        """
        provider = self.llm.provider_name.lower()
        model = self.llm.model

        total = 0

        # Count system messages
        for msg in self.system_messages:
            total += self.token_tracker.count_message_tokens(msg, provider, model)

        # Count short-term messages (includes summary messages)
        for msg in self.short_term.get_messages():
            total += self.token_tracker.count_message_tokens(msg, provider, model)

        return total

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics.

        Returns:
            Dict with statistics
        """
        return {
            "current_tokens": self.current_tokens,
            "total_input_tokens": self.token_tracker.total_input_tokens,
            "total_output_tokens": self.token_tracker.total_output_tokens,
            "compression_count": self.compression_count,
            "total_savings": self.token_tracker.compression_savings,
            "compression_cost": self.token_tracker.compression_cost,
            "net_savings": self.token_tracker.compression_savings
            - self.token_tracker.compression_cost,
            "short_term_count": self.short_term.count(),
            "total_cost": self.token_tracker.get_total_cost(self.llm.model),
        }

    async def save_memory(self):
        """Save current memory state to store.

        This saves the complete memory state including:
        - System messages
        - Short-term messages (which includes summary messages after compression)

        Call this method after completing a task or at key checkpoints.
        """
        # Skip if no session was created (no messages were ever added)
        if not self._store or not self._session_created or not self.session_id:
            logger.debug("Skipping save_memory: no session created")
            return

        messages = self.short_term.get_messages()

        # Skip saving if there are no messages (empty conversation)
        if not messages and not self.system_messages:
            logger.debug(f"Skipping save_memory: no messages to save for session {self.session_id}")
            return

        await self._store.save_memory(
            session_id=self.session_id,
            system_messages=self.system_messages,
            messages=messages,
        )
        logger.info(f"Saved memory state for session {self.session_id}")

    def reset(self):
        """Reset memory manager state."""
        self.short_term.clear()
        self.system_messages.clear()
        self.token_tracker.reset()
        self.current_tokens = 0
        self.was_compressed_last_iteration = False
        self.last_compression_savings = 0
        self.compression_count = 0
        self._last_api_context_tokens = None
        self._estimated_delta_tokens = 0

    def rollback_incomplete_exchange(self) -> None:
        """Rollback the last incomplete assistant response with tool_calls.

        This is used when a task is interrupted before tool execution completes.
        It removes the assistant message if it contains tool_calls but no results.
        The user message is preserved so the agent can see the original question.

        This prevents API errors about missing tool responses on the next turn.
        """
        messages = self.short_term.get_messages()
        if not messages:
            return

        # Check if last message is an assistant message with tool_calls
        last_msg = messages[-1]
        if last_msg.role == "assistant" and self._message_has_tool_calls(last_msg):
            # Remove only the assistant message with tool_calls
            # Keep the user message so the agent can still see the question
            self.short_term.remove_last(1)
            logger.debug("Removed incomplete assistant message with tool_calls")

            # Recalculate token count
            self.current_tokens = self._recalculate_current_tokens()
