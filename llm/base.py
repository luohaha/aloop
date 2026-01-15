"""Base data structures for LLM interface."""
from typing import Any, Dict, Optional
from dataclasses import dataclass


@dataclass
class LLMMessage:
    """Unified message format across all LLM providers."""
    role: str  # "user", "assistant", "system"
    content: Any  # Can be string or list of content blocks


@dataclass
class LLMResponse:
    """Unified response format across all LLM providers."""
    content: Any  # Response content (text or content blocks)
    stop_reason: str  # "end_turn", "tool_use", "max_tokens", etc.
    usage: Optional[Dict[str, int]] = None  # Token usage: {"input_tokens": int, "output_tokens": int}


@dataclass
class ToolCall:
    """Unified tool call format."""
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ToolResult:
    """Unified tool result format."""
    tool_call_id: str
    content: str
