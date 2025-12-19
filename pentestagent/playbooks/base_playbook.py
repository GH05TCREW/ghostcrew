from dataclasses import dataclass, field
from typing import List


@dataclass
class Phase:
    name: str
    objective: str
    techniques: List[str]


class BasePlaybook:
    """Base class for all playbooks."""

    name: str = "base_playbook"
    description: str = "Base playbook description"
    mode: str = "agent"  # "agent" or "crew"
    max_loops: int = 50
    phases: List[Phase] = field(default_factory=list)

    def get_task(self) -> str:
        """Convert playbook into a structured task description."""
        task = f"{self.description}\n\n"

        for phase in self.phases:
            task += f"Phase: {phase.name}\n"
            task += f"Objective: {phase.objective}\n"
            task += "Techniques:\n"
            for i, technique in enumerate(phase.techniques, 1):
                task += f"  {i}. {technique}\n"
            task += "\n"

        return task
