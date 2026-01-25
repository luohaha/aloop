"""Agent event system for UI integration."""

from dataclasses import dataclass
from typing import Any, Dict, List, Protocol


@dataclass
class AgentEvent:
    """Base class for agent events."""

    pass


@dataclass
class IterationStarted(AgentEvent):
    """Emitted when an iteration starts."""

    iteration: int
    max_iterations: int


@dataclass
class ThinkingEvent(AgentEvent):
    """Emitted with thinking/reasoning content."""

    content: str


@dataclass
class ToolCallStarted(AgentEvent):
    """Emitted when a tool call begins."""

    tool_name: str
    arguments: Dict[str, Any]
    tool_call_id: str = ""


@dataclass
class ToolCallCompleted(AgentEvent):
    """Emitted when a tool call completes."""

    tool_name: str
    tool_call_id: str
    result: str
    success: bool = True


@dataclass
class AssistantResponse(AgentEvent):
    """Emitted with assistant text content."""

    content: str
    is_final: bool = False


@dataclass
class MemoryCompressed(AgentEvent):
    """Emitted when memory compression occurs."""

    tokens_saved: int


@dataclass
class ErrorEvent(AgentEvent):
    """Emitted when an error occurs."""

    error: str
    recoverable: bool = True


class EventHandler(Protocol):
    """Protocol for event handlers."""

    def __call__(self, event: AgentEvent) -> None:
        """Handle an agent event."""
        ...


class AgentEventEmitter:
    """Mixin class that provides event emission capabilities."""

    def __init__(self) -> None:
        self._event_handlers: List[EventHandler] = []

    def add_event_handler(self, handler: EventHandler) -> None:
        """Register an event handler."""
        self._event_handlers.append(handler)

    def remove_event_handler(self, handler: EventHandler) -> None:
        """Remove an event handler."""
        if handler in self._event_handlers:
            self._event_handlers.remove(handler)

    def clear_event_handlers(self) -> None:
        """Remove all event handlers."""
        self._event_handlers.clear()

    def emit_event(self, event: AgentEvent) -> None:
        """Emit an event to all registered handlers."""
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception:
                # Don't let handler errors break the agent
                pass
