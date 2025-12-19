"""Tool system for PentestAgent."""

from .executor import ToolExecutor
from .loader import discover_tools, get_tool_info, load_all_tools, reload_tools
from .registry import (
    Tool,
    ToolSchema,
    clear_tools,
    disable_tool,
    enable_tool,
    get_all_tools,
    get_tool,
    get_tool_names,
    get_tools_by_category,
    register_tool,
    register_tool_instance,
)

# Auto-load all built-in tools on import
_loaded = load_all_tools()

__all__ = [
    # Registry
    "Tool",
    "ToolSchema",
    "register_tool",
    "get_all_tools",
    "get_tool",
    "register_tool_instance",
    "get_tools_by_category",
    "enable_tool",
    "disable_tool",
    "get_tool_names",
    "clear_tools",
    # Executor
    "ToolExecutor",
    # Loader
    "load_all_tools",
    "get_tool_info",
    "reload_tools",
    "discover_tools",
]
