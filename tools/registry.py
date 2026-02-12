"""Centralized tool registry for creating and managing tool instances."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tools.advanced_file_ops import GlobTool, GrepTool
from tools.base import BaseTool
from tools.file_ops import FileReadTool, FileWriteTool
from tools.shell import ShellTool
from tools.shell_background import BackgroundTaskManager, ShellTaskStatusTool
from tools.smart_edit import SmartEditTool
from tools.web_fetch import WebFetchTool
from tools.web_search import WebSearchTool

if TYPE_CHECKING:
    from agent.base import BaseAgent

# Core tools: name -> class (instantiated without agent reference)
CORE_TOOLS: dict[str, type[BaseTool]] = {
    "read_file": FileReadTool,
    "write_file": FileWriteTool,
    "web_search": WebSearchTool,
    "web_fetch": WebFetchTool,
    "glob_files": GlobTool,
    "grep_content": GrepTool,
    "smart_edit": SmartEditTool,
    "shell": ShellTool,
    "shell_task_status": ShellTaskStatusTool,
}

# Names of tools requiring agent reference (added after agent construction)
AGENT_TOOL_NAMES: set[str] = {"explore_context", "parallel_execute"}

# Tools requiring shared BackgroundTaskManager
_TASK_MANAGER_TOOLS = {"shell", "shell_task_status"}


def _get_agent_tool_classes() -> dict[str, type]:
    """Lazy import of agent-dependent tool classes to avoid circular imports."""
    from tools.explore import ExploreTool
    from tools.parallel_execute import ParallelExecutionTool

    return {
        "explore_context": ExploreTool,
        "parallel_execute": ParallelExecutionTool,
    }


def create_core_tools(
    names: list[str] | None = None,
    task_manager: BackgroundTaskManager | None = None,
) -> list[BaseTool]:
    """Create core tool instances.

    Args:
        names: Tool names to create. None = all core tools.
        task_manager: Optional shared BackgroundTaskManager instance.

    Returns:
        List of instantiated tool objects.
    """
    if task_manager is None:
        task_manager = BackgroundTaskManager.get_instance()

    target = names if names is not None else list(CORE_TOOLS.keys())
    tools: list[BaseTool] = []

    for name in target:
        if name not in CORE_TOOLS:
            continue
        cls = CORE_TOOLS[name]
        if name in _TASK_MANAGER_TOOLS:
            tools.append(cls(task_manager=task_manager))  # type: ignore[call-arg]
        else:
            tools.append(cls())

    return tools


def add_agent_tools(agent: BaseAgent, names: list[str] | None = None) -> None:
    """Add agent-reference tools to an existing agent.

    Args:
        agent: Agent instance to add tools to.
        names: Tool names to add. None = all agent tools.
    """
    classes = _get_agent_tool_classes()
    target = names if names is not None else list(classes.keys())

    for name in target:
        if name in classes:
            agent.tool_executor.add_tool(classes[name](agent))


def get_all_tool_names() -> list[str]:
    """Return all known tool names (core + agent)."""
    return list(CORE_TOOLS.keys()) + list(_get_agent_tool_classes().keys())
