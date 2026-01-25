"""TUI event definitions for agent-UI communication."""

from dataclasses import dataclass, field
from typing import Any, Dict

from textual.message import Message


@dataclass
class AgentEvent(Message):
    """Base class for agent events."""

    pass


@dataclass
class TurnStarted(AgentEvent):
    """Emitted when a new turn begins."""

    turn_number: int = 0


@dataclass
class TurnEnded(AgentEvent):
    """Emitted when a turn completes."""

    turn_number: int = 0


@dataclass
class IterationStarted(AgentEvent):
    """Emitted when an iteration starts within a turn."""

    iteration: int = 0
    max_iterations: int = 0


@dataclass
class ThinkingStarted(AgentEvent):
    """Emitted when the agent starts thinking."""

    pass


@dataclass
class ThinkingContent(AgentEvent):
    """Emitted with thinking/reasoning content."""

    content: str = ""


@dataclass
class ToolCallStarted(AgentEvent):
    """Emitted when a tool call begins."""

    tool_name: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    tool_call_id: str = ""


@dataclass
class ToolCallCompleted(AgentEvent):
    """Emitted when a tool call completes."""

    tool_name: str = ""
    tool_call_id: str = ""
    result: str = ""
    success: bool = True


@dataclass
class AssistantMessage(AgentEvent):
    """Emitted with assistant text content."""

    content: str = ""
    is_final: bool = False


@dataclass
class StreamingChunk(AgentEvent):
    """Emitted for streaming content chunks."""

    content: str = ""
    is_complete: bool = False


@dataclass
class MemoryCompressed(AgentEvent):
    """Emitted when memory compression occurs."""

    tokens_saved: int = 0


@dataclass
class ErrorOccurred(AgentEvent):
    """Emitted when an error occurs."""

    error: str = ""
    recoverable: bool = True


@dataclass
class AgentStats(AgentEvent):
    """Emitted with agent statistics update."""

    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    compressions: int = 0
    cost: float = 0.0
