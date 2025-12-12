"""Task completion tool for GhostCrew agent loop control."""

import json
from typing import Any, Dict, List, Optional

from ..registry import ToolSchema, register_tool

# Sentinel value to signal task completion
TASK_COMPLETE_SIGNAL = "__TASK_COMPLETE__"


@register_tool(
    name="finish",
    description="Signal that the current task is finished. Call this when you have completed ALL steps of the user's request. Provide a structured report of what was accomplished.",
    schema=ToolSchema(
        properties={
            "status": {
                "type": "string",
                "enum": ["success", "partial", "failed"],
                "description": "Overall task status: 'success' (all objectives met), 'partial' (some objectives met), 'failed' (unable to complete)",
            },
            "summary": {
                "type": "string",
                "description": "Brief summary of what was accomplished and any key findings",
            },
            "findings": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of key findings, vulnerabilities discovered, or important observations",
            },
            "artifacts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of files created (PoCs, scripts, screenshots, reports)",
            },
            "recommendations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Suggested next steps or follow-up actions",
            },
        },
        required=["status", "summary"],
    ),
    category="control",
)
async def finish(arguments: dict, runtime) -> str:
    """
    Signal task completion to the agent framework with structured output.

    This tool is called by the agent when it has finished all steps
    of the user's task. The framework uses this as an explicit
    termination signal rather than relying on LLM text output.

    Args:
        arguments: Dictionary with structured completion data
        runtime: The runtime environment (unused)

    Returns:
        The completion signal with structured JSON data
    """
    # Build structured completion report
    report = CompletionReport(
        status=arguments.get("status", "success"),
        summary=arguments.get("summary", "Task completed."),
        findings=arguments.get("findings", []),
        artifacts=arguments.get("artifacts", []),
        recommendations=arguments.get("recommendations", []),
    )
    
    # Return special signal with JSON-encoded report
    return f"{TASK_COMPLETE_SIGNAL}:{report.to_json()}"


class CompletionReport:
    """Structured completion report for task results."""
    
    def __init__(
        self,
        status: str = "success",
        summary: str = "",
        findings: Optional[List[str]] = None,
        artifacts: Optional[List[str]] = None,
        recommendations: Optional[List[str]] = None,
    ):
        self.status = status
        self.summary = summary
        self.findings = findings or []
        self.artifacts = artifacts or []
        self.recommendations = recommendations or []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status,
            "summary": self.summary,
            "findings": self.findings,
            "artifacts": self.artifacts,
            "recommendations": self.recommendations,
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> "CompletionReport":
        """Create from JSON string."""
        data = json.loads(json_str)
        return cls(**data)
    
    def format_display(self) -> str:
        """Format for human-readable display."""
        lines = []
        
        # Status indicator
        status_icons = {"success": "✓", "partial": "◐", "failed": "✗"}
        icon = status_icons.get(self.status, "•")
        lines.append(f"{icon} Status: {self.status.upper()}")
        lines.append("")
        
        # Summary
        lines.append(f"Summary: {self.summary}")
        
        # Findings
        if self.findings:
            lines.append("")
            lines.append("Findings:")
            for finding in self.findings:
                lines.append(f"  • {finding}")
        
        # Artifacts
        if self.artifacts:
            lines.append("")
            lines.append("Artifacts:")
            for artifact in self.artifacts:
                lines.append(f"  📄 {artifact}")
        
        # Recommendations
        if self.recommendations:
            lines.append("")
            lines.append("Recommendations:")
            for rec in self.recommendations:
                lines.append(f"  → {rec}")
        
        return "\n".join(lines)


def is_task_complete(result: str) -> bool:
    """Check if a tool result signals task completion."""
    return result.startswith(TASK_COMPLETE_SIGNAL)


def extract_completion_summary(result: str) -> str:
    """Extract the summary from a task_complete result (legacy support)."""
    if is_task_complete(result):
        data = result[len(TASK_COMPLETE_SIGNAL) + 1:]  # +1 for the colon
        # Try to parse as JSON for new format
        try:
            report = CompletionReport.from_json(data)
            return report.summary
        except (json.JSONDecodeError, TypeError):
            # Fall back to raw string for legacy format
            return data
    return result


def extract_completion_report(result: str) -> Optional[CompletionReport]:
    """Extract the full structured report from a task_complete result."""
    if is_task_complete(result):
        data = result[len(TASK_COMPLETE_SIGNAL) + 1:]
        try:
            return CompletionReport.from_json(data)
        except (json.JSONDecodeError, TypeError):
            # Legacy format - wrap in report
            return CompletionReport(status="success", summary=data)
    return None
