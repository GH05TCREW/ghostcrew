"""MCP tool wrapper for PentestAgent."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..runtime import Runtime
    from ..tools import Tool
    from .manager import MCPManager, MCPServer


def create_mcp_tool(
    tool_def: dict, server: "MCPServer", manager: "MCPManager"
) -> "Tool":
    """
    Create a Tool instance from an MCP tool definition.

    Args:
        tool_def: The MCP tool definition
        server: The MCP server that provides this tool
        manager: The MCP manager for making calls

    Returns:
        A Tool instance that wraps the MCP tool
    """
    from ..tools import Tool, ToolSchema

    async def execute_mcp(arguments: dict, runtime: "Runtime") -> str:
        """Execute this MCP tool."""
        # Get the tool name (without mcp_ prefix)
        original_name = tool_def["name"]

        try:
            result = await manager.call_tool(server.name, original_name, arguments)

            # Format result
            if isinstance(result, list):
                formatted_parts = []
                for item in result:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            formatted_parts.append(item.get("text", ""))
                        elif item.get("type") == "image":
                            formatted_parts.append(
                                f"[Image: {item.get('mimeType', 'unknown')}]"
                            )
                        elif item.get("type") == "resource":
                            formatted_parts.append(
                                f"[Resource: {item.get('uri', 'unknown')}]"
                            )
                        else:
                            formatted_parts.append(str(item))
                    else:
                        formatted_parts.append(str(item))
                return "\n".join(formatted_parts)

            return str(result)

        except Exception as e:
            return f"MCP tool error: {str(e)}"

    # Convert MCP schema to our schema format
    input_schema = tool_def.get("inputSchema", {})
    schema = ToolSchema(
        type=input_schema.get("type", "object"),
        properties=input_schema.get("properties", {}),
        required=input_schema.get("required", []),
    )

    # Create unique name with server prefix
    tool_name = f"mcp_{server.name}_{tool_def['name']}"

    return Tool(
        name=tool_name,
        description=tool_def.get("description", f"MCP tool from {server.name}"),
        schema=schema,
        execute_fn=execute_mcp,
        category=f"mcp:{server.name}",
        metadata={
            "mcp_server": server.name,
            "mcp_tool": tool_def["name"],
            "original_schema": input_schema,
        },
    )


def format_mcp_result(result: Any) -> str:
    """
    Format an MCP tool result for display.

    Args:
        result: The raw MCP result

    Returns:
        Formatted string
    """
    if isinstance(result, list):
        parts = []
        for item in result:
            if isinstance(item, dict):
                content_type = item.get("type", "unknown")

                if content_type == "text":
                    parts.append(item.get("text", ""))
                elif content_type == "image":
                    mime = item.get("mimeType", "unknown")
                    data_preview = item.get("data", "")[:50]
                    parts.append(f"[Image ({mime}): {data_preview}...]")
                elif content_type == "resource":
                    uri = item.get("uri", "unknown")
                    parts.append(f"[Resource: {uri}]")
                else:
                    parts.append(str(item))
            else:
                parts.append(str(item))

        return "\n".join(parts)

    elif isinstance(result, dict):
        if "content" in result:
            return format_mcp_result(result["content"])
        return str(result)

    return str(result)
