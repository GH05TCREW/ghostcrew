"""Tool registry for PentestAgent."""

from dataclasses import dataclass, field
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from ..runtime import Runtime


@dataclass
class ToolSchema:
    """JSON Schema for tool parameters."""

    type: str = "object"
    properties: Optional[Dict[str, Any]] = None
    required: Optional[List[str]] = None

    def __post_init__(self):
        if self.properties is None:
            self.properties = {}
        if self.required is None:
            self.required = []

    def to_dict(self) -> dict:
        """Convert to dictionary format."""
        return {
            "type": self.type,
            "properties": self.properties,
            "required": self.required,
        }


@dataclass
class Tool:
    """Represents a tool available to agents."""

    name: str
    description: str
    schema: ToolSchema
    execute_fn: Callable
    category: str = "general"
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    async def execute(self, arguments: dict, runtime: "Runtime") -> str:
        """
        Execute the tool with given arguments.

        Args:
            arguments: The arguments for the tool
            runtime: The runtime environment

        Returns:
            The tool execution result as a string
        """
        if not self.enabled:
            return f"Tool '{self.name}' is currently disabled."

        return await self.execute_fn(arguments, runtime)

    def to_llm_format(self) -> dict:
        """Convert to LLM function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": self.schema.type,
                    "properties": self.schema.properties or {},
                    "required": self.schema.required or [],
                },
            },
        }

    def validate_arguments(self, arguments: dict) -> tuple[bool, Optional[str]]:
        """
        Validate arguments against the schema.

        Args:
            arguments: The arguments to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields
        for required_field in self.schema.required or []:
            if required_field not in arguments:
                return False, f"Missing required field: {required_field}"

        # Type checking (basic)
        for key, value in arguments.items():
            if key in (self.schema.properties or {}):
                expected_type = self.schema.properties[key].get("type")
                if expected_type:
                    if not self._check_type(value, expected_type):
                        return (
                            False,
                            f"Invalid type for {key}: expected {expected_type}",
                        )

        return True, None

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if a value matches the expected type."""
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        expected = type_map.get(expected_type)
        if expected is None:
            return True  # Unknown type, allow

        return isinstance(value, expected)


# Global tool registry
_tools: Dict[str, Tool] = {}


def register_tool(
    name: str, description: str, schema: ToolSchema, category: str = "general"
) -> Callable:
    """
    Decorator to register a tool.

    Args:
        name: The tool name
        description: Description of what the tool does
        schema: The parameter schema
        category: Tool category for organization

    Returns:
        Decorator function
    """

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        async def wrapper(arguments: dict, runtime: "Runtime") -> str:
            return await fn(arguments, runtime)

        tool = Tool(
            name=name,
            description=description,
            schema=schema,
            execute_fn=wrapper,
            category=category,
        )
        _tools[name] = tool
        return wrapper

    return decorator


def get_all_tools() -> List[Tool]:
    """Get all registered tools."""
    return list(_tools.values())


def get_tool(name: str) -> Optional[Tool]:
    """Get a tool by name."""
    return _tools.get(name)


def register_tool_instance(tool: Tool) -> None:
    """
    Register a pre-built tool instance (used for MCP tools).

    Args:
        tool: The Tool instance to register
    """
    _tools[tool.name] = tool


def unregister_tool(name: str) -> bool:
    """
    Unregister a tool by name.

    Args:
        name: The tool name to unregister

    Returns:
        True if tool was unregistered, False if not found
    """
    if name in _tools:
        del _tools[name]
        return True
    return False


def get_tools_by_category(category: str) -> List[Tool]:
    """
    Get all tools in a specific category.

    Args:
        category: The category to filter by

    Returns:
        List of tools in that category
    """
    return [tool for tool in _tools.values() if tool.category == category]


def clear_tools() -> None:
    """Clear all registered tools."""
    _tools.clear()


def get_tool_names() -> List[str]:
    """Get list of all registered tool names."""
    return list(_tools.keys())


def enable_tool(name: str) -> bool:
    """Enable a tool by name."""
    tool = _tools.get(name)
    if tool:
        tool.enabled = True
        return True
    return False


def disable_tool(name: str) -> bool:
    """Disable a tool by name."""
    tool = _tools.get(name)
    if tool:
        tool.enabled = False
        return True
    return False
