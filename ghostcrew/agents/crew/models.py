"""Data models for crew orchestration."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Literal, Optional


class CrewState(Enum):
    """State of the crew orchestrator."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"


class AgentStatus(Enum):
    """Status of a worker agent."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    WARNING = "warning"  # Completed but hit max iterations
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class AgentWorker:
    """A worker agent managed by the crew."""

    id: str
    task: str
    status: AgentStatus = AgentStatus.PENDING
    priority: int = 1
    depends_on: List[str] = field(default_factory=list)
    result: Optional[str] = None
    error: Optional[str] = None
    tools_used: List[str] = field(default_factory=list)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "task": self.task,
            "status": self.status.value,
            "priority": self.priority,
            "depends_on": self.depends_on,
            "result": self.result,
            "error": self.error,
            "tools_used": self.tools_used,
        }


@dataclass
class Finding:
    """A security finding from an agent."""

    severity: Literal["critical", "high", "medium", "low", "info"]
    title: str
    description: str
    agent_id: str
    evidence: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "agent_id": self.agent_id,
            "evidence": self.evidence,
        }


# Type alias for worker event callback
WorkerCallback = Callable[[str, str, Dict[str, Any]], None]
