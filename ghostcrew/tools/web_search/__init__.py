"""Web search tool for GhostCrew."""

import os
from typing import TYPE_CHECKING

import httpx

from ..registry import ToolSchema, register_tool

if TYPE_CHECKING:
    from ...runtime import Runtime


@register_tool(
    name="web_search",
    description="Search the web for new security research, CVEs, exploits, bypass techniques, and documentation.",
    schema=ToolSchema(
        properties={
            "query": {
                "type": "string",
                "description": "Search query (be specific - include CVE numbers, tool names, versions)",
            }
        },
        required=["query"],
    ),
    category="research",
)
async def web_search(arguments: dict, runtime: "Runtime") -> str:
    """
    Search the web using Tavily API.

    Args:
        arguments: Dictionary with 'query'
        runtime: The runtime environment

    Returns:
        Search results formatted for the LLM
    """
    query = arguments.get("query", "").strip()
    if not query:
        return "Error: No search query provided"

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return (
            "Error: TAVILY_API_KEY environment variable not set.\n"
            "Get a free API key at https://tavily.com (1000 searches/month free)"
        )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "include_answer": True,
                    "include_raw_content": False,
                    "max_results": 5,
                },
            )
            response.raise_for_status()
            data = response.json()

        return _format_results(query, data)

    except httpx.TimeoutException:
        return "Error: Search request timed out"
    except httpx.HTTPStatusError as e:
        return f"Error: Search API returned {e.response.status_code}"
    except Exception as e:
        return f"Error: Search failed - {str(e)}"


def _format_results(query: str, data: dict) -> str:
    """
    Format Tavily results for LLM consumption.

    Returns a lean format with summary + titles + URLs only.
    Content snippets are excluded to prevent LLM from regurgitating
    noisy web scrapes in its response.
    """
    parts = [f"Search: {query}\n"]

    # Include synthesized answer if available (this is the valuable part)
    if answer := data.get("answer"):
        parts.append(f"Summary:\n{answer}\n")

    # Include sources as title + URL only (no content snippets)
    results = data.get("results", [])
    if results:
        parts.append("Sources:")
        for i, result in enumerate(results, 1):
            title = result.get("title", "Untitled")
            url = result.get("url", "")
            parts.append(f"  [{i}] {title}")
            parts.append(f"      {url}")
    else:
        parts.append("No results found")

    return "\n".join(parts)
