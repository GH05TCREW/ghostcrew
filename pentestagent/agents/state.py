"""Agent state management for PentestAgent."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentState(Enum):
    """Possible states for an agent."""

    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    WAITING_INPUT = "waiting_input"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class StateTransition:
    """Represents a state transition."""

    from_state: AgentState
    to_state: AgentState
    timestamp: datetime = field(default_factory=datetime.now)
    reason: Optional[str] = None


@dataclass
class AgentStateManager:
    """Manages agent state and transitions."""

    current_state: AgentState = AgentState.IDLE
    history: List[StateTransition] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Valid state transitions
    VALID_TRANSITIONS = {
        AgentState.IDLE: [AgentState.THINKING, AgentState.ERROR],
        AgentState.THINKING: [
            AgentState.EXECUTING,
            AgentState.WAITING_INPUT,
            AgentState.COMPLETE,
            AgentState.ERROR,
        ],
        AgentState.EXECUTING: [AgentState.THINKING, AgentState.ERROR],
        AgentState.WAITING_INPUT: [
            AgentState.THINKING,
            AgentState.COMPLETE,
            AgentState.ERROR,
        ],
        AgentState.COMPLETE: [AgentState.IDLE],
        AgentState.ERROR: [AgentState.IDLE],
    }

    def can_transition_to(self, new_state: AgentState) -> bool:
        """Check if a transition to the new state is valid."""
        valid_next_states = self.VALID_TRANSITIONS.get(self.current_state, [])
        return new_state in valid_next_states

    def transition_to(
        self, new_state: AgentState, reason: Optional[str] = None
    ) -> bool:
        """
        Transition to a new state.

        Args:
            new_state: The state to transition to
            reason: Optional reason for the transition

        Returns:
            True if transition was successful, False otherwise
        """
        if not self.can_transition_to(new_state):
            return False

        transition = StateTransition(
            from_state=self.current_state, to_state=new_state, reason=reason
        )
        self.history.append(transition)
        self.current_state = new_state
        return True

    def force_transition(self, new_state: AgentState, reason: Optional[str] = None):
        """Force a transition regardless of validity (use with caution)."""
        transition = StateTransition(
            from_state=self.current_state,
            to_state=new_state,
            reason=f"FORCED: {reason}" if reason else "FORCED",
        )
        self.history.append(transition)
        self.current_state = new_state

    def reset(self):
        """Reset state to IDLE."""
        self.current_state = AgentState.IDLE
        self.history.clear()
        self.metadata.clear()

    def is_terminal(self) -> bool:
        """Check if current state is a terminal state."""
        return self.current_state in [AgentState.COMPLETE, AgentState.ERROR]

    def is_active(self) -> bool:
        """Check if agent is actively processing."""
        return self.current_state in [AgentState.THINKING, AgentState.EXECUTING]

    def get_state_duration(self) -> float:
        """Get duration in current state (seconds)."""
        if not self.history:
            return 0.0

        last_transition = self.history[-1]
        return (datetime.now() - last_transition.timestamp).total_seconds()
