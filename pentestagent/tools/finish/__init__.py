"""Task completion tool for PentestAgent agent loop control."""

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..registry import Tool as Tool
from ..registry import ToolSchema, register_tool

if TYPE_CHECKING:
    from ...runtime import Runtime
    from ..planning import TaskPlan

# Sentinel value to signal task completion
TASK_COMPLETE_SIGNAL = "__TASK_COMPLETE__"


class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    SKIP = "skip"
    FAIL = "fail"


@dataclass
class PlanStep:
    id: int
    description: str
    status: StepStatus = StepStatus.PENDING
    result: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.value,
            "result": self.result,
        }


@dataclass
class TaskPlan:
    steps: list[PlanStep] = field(default_factory=list)
    original_request: str = ""

    def is_complete(self) -> bool:
        return all(
            s.status in (StepStatus.COMPLETE, StepStatus.SKIP) for s in self.steps
        )

    def has_failure(self) -> bool:
        return any(s.status == StepStatus.FAIL for s in self.steps)

    def clear(self) -> None:
        self.steps.clear()
        self.original_request = ""

    def get_current_step(self) -> Optional[PlanStep]:
        for s in self.steps:
            if s.status == StepStatus.PENDING:
                return s
        return None

    def get_pending_steps(self) -> list[PlanStep]:
        return [s for s in self.steps if s.status == StepStatus.PENDING]


@register_tool(
    name="finish",
    description="Mark plan steps as complete, skipped, or failed. Actions: 'complete' (mark step done), 'skip' (step not applicable), 'fail' (step failed, invalidating plan). Once all steps are complete/skipped, task automatically finishes.",
    schema=ToolSchema(
        properties={
            "action": {
                "type": "string",
                "enum": ["complete", "skip", "fail"],
                "description": "Action: 'complete', 'skip', or 'fail'",
            },
            "step_id": {
                "type": "integer",
                "description": "Step number (1-indexed)",
            },
            "result": {
                "type": "string",
                "description": "[complete only] What was accomplished",
            },
            "reason": {
                "type": "string",
                "description": "[skip/fail only] Why step is being skipped or failed",
            },
        },
        required=["action", "step_id"],
    ),
    category="workflow",
)
async def finish(arguments: dict, runtime: "Runtime") -> str:
    """Mark plan steps as complete or skipped. Accesses plan via runtime.plan."""
    action = arguments.get("action", "")
    step_id = arguments.get("step_id")

    # Access plan from runtime (set by agent)
    plan = getattr(runtime, "plan", None)
    if plan is None or len(plan.steps) == 0:
        return "No active plan."

    # Find the step
    step = next((s for s in plan.steps if s.id == step_id), None)
    if not step:
        valid_ids = [s.id for s in plan.steps]
        return f"Error: Step {step_id} not found. Valid IDs: {valid_ids}"

    if action == "complete":
        result = arguments.get("result", "")
        step.status = StepStatus.COMPLETE
        step.result = result

        # Build response
        lines = [f"Step {step_id} complete"]
        if result:
            lines.append(f"Result: {result}")

        # Check if all done
        if plan.is_complete():
            lines.append("All steps complete")
        else:
            next_step = plan.get_current_step()
            if next_step:
                lines.append(f"Next: Step {next_step.id}")

        return "\n".join(lines)

    elif action == "skip":
        reason = arguments.get("reason", "")
        if not reason:
            return "Error: 'reason' required for skip action."

        step.status = StepStatus.SKIP
        step.result = f"Skipped: {reason}"
        return f"Step {step_id} skipped: {reason}"

    elif action == "fail":
        reason = arguments.get("reason", "")
        if not reason:
            return "Error: 'reason' required for fail action."

        step.status = StepStatus.FAIL
        step.result = f"Failed: {reason}"
        return f"Step {step_id} marked as FAILED: {reason}. Initiating replanning..."

    else:
        return f"Error: Unknown action '{action}'. Use 'complete', 'skip', or 'fail'."


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
        data = result[len(TASK_COMPLETE_SIGNAL) + 1 :]  # +1 for the colon
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
        data = result[len(TASK_COMPLETE_SIGNAL) + 1 :]
        try:
            return CompletionReport.from_json(data)
        except (json.JSONDecodeError, TypeError):
            # Legacy format - wrap in report
            return CompletionReport(status="success", summary=data)
    return None
