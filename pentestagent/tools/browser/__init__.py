"""Browser automation tool for PentestAgent."""

from typing import TYPE_CHECKING

from ..registry import ToolSchema, register_tool

if TYPE_CHECKING:
    from ...runtime import Runtime


@register_tool(
    name="browser",
    description="Automate a headless browser. Actions: navigate, click, type, screenshot, get_content, get_links, get_forms, execute_js.",
    schema=ToolSchema(
        properties={
            "action": {
                "type": "string",
                "enum": [
                    "navigate",
                    "click",
                    "type",
                    "screenshot",
                    "get_content",
                    "get_links",
                    "get_forms",
                    "execute_js",
                ],
                "description": "The browser action to perform",
            },
            "url": {
                "type": "string",
                "description": "URL to navigate to (for 'navigate' action)",
            },
            "selector": {
                "type": "string",
                "description": "CSS selector for element (for 'click', 'type' actions)",
            },
            "text": {
                "type": "string",
                "description": "Text to type (for 'type' action)",
            },
            "javascript": {
                "type": "string",
                "description": "JavaScript code to execute (for 'execute_js' action)",
            },
            "wait_for": {
                "type": "string",
                "description": "CSS selector to wait for before continuing",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 30)",
                "default": 30,
            },
        },
        required=["action"],
    ),
    category="web",
)
async def browser(arguments: dict, runtime: "Runtime") -> str:
    """
    Perform browser automation actions.

    Args:
        arguments: Dictionary with action and related parameters
        runtime: The runtime environment

    Returns:
        Result of the browser action
    """
    action = arguments["action"]
    timeout = arguments.get("timeout", 30)

    try:
        result = await runtime.browser_action(
            action=action,
            url=arguments.get("url"),
            selector=arguments.get("selector"),
            text=arguments.get("text"),
            javascript=arguments.get("javascript"),
            wait_for=arguments.get("wait_for"),
            timeout=timeout,
        )

        return _format_browser_result(action, result)

    except Exception as e:
        return f"Browser action '{action}' failed: {str(e)}"


def _format_browser_result(action: str, result: dict) -> str:
    """Format browser action result for display."""
    # Check for errors first
    if "error" in result:
        return f"Browser error: {result['error']}"

    if action == "navigate":
        return f"Navigated to: {result.get('url', 'unknown')}\nTitle: {result.get('title', 'N/A')}"

    elif action == "screenshot":
        return f"Screenshot saved to: {result.get('path', 'unknown')}"

    elif action == "get_content":
        content = result.get("content", "")
        if len(content) > 5000:
            content = content[:5000] + "\n... (truncated)"
        return f"Page content:\n{content}"

    elif action == "get_links":
        links = result.get("links", [])
        if not links:
            return "No links found on page"

        formatted = ["Found links:"]
        for link in links[:50]:  # Limit to 50 links
            text = link.get("text", "").strip()[:50]
            href = link.get("href", "")
            formatted.append(f"  - [{text}] {href}")

        if len(links) > 50:
            formatted.append(f"  ... and {len(links) - 50} more links")

        return "\n".join(formatted)

    elif action == "get_forms":
        forms = result.get("forms", [])
        if not forms:
            return "No forms found on page"

        formatted = ["Found forms:"]
        for i, form in enumerate(forms):
            formatted.append(f"\nForm {i + 1}:")
            formatted.append(f"  Action: {form.get('action', 'N/A')}")
            formatted.append(f"  Method: {form.get('method', 'GET')}")
            inputs = form.get("inputs", [])
            if inputs:
                formatted.append("  Inputs:")
                for inp in inputs:
                    formatted.append(
                        f"    - {inp.get('name', 'unnamed')} ({inp.get('type', 'text')})"
                    )

        return "\n".join(formatted)

    elif action == "click":
        return f"Clicked element: {result.get('selector', 'unknown')}"

    elif action == "type":
        return f"Typed text into: {result.get('selector', 'unknown')}"

    elif action == "execute_js":
        output = result.get("result", "")
        return f"JavaScript result:\n{output}"

    else:
        return str(result)
