"""Tests for the agent state management."""

import pytest
from datetime import datetime

from pentestagent.agents.state import AgentState, AgentStateManager, StateTransition


class TestAgentState:
    """Tests for AgentState enum."""
    
    def test_state_values(self):
        """Test state enum values."""
        assert AgentState.IDLE.value == "idle"
        assert AgentState.THINKING.value == "thinking"
        assert AgentState.EXECUTING.value == "executing"
        assert AgentState.WAITING_INPUT.value == "waiting_input"
        assert AgentState.COMPLETE.value == "complete"
        assert AgentState.ERROR.value == "error"
    
    def test_all_states_exist(self):
        """Test that all expected states exist."""
        states = list(AgentState)
        assert len(states) >= 6


class TestAgentStateManager:
    """Tests for AgentStateManager class."""
    
    @pytest.fixture
    def state_manager(self):
        """Create a fresh AgentStateManager for each test."""
        return AgentStateManager()
    
    def test_initial_state(self, state_manager):
        """Test initial state is IDLE."""
        assert state_manager.current_state == AgentState.IDLE
        assert len(state_manager.history) == 0
    
    def test_valid_transition(self, state_manager):
        """Test valid state transition."""
        result = state_manager.transition_to(AgentState.THINKING)
        assert result is True
        assert state_manager.current_state == AgentState.THINKING
        assert len(state_manager.history) == 1
    
    def test_invalid_transition(self, state_manager):
        """Test invalid state transition."""
        result = state_manager.transition_to(AgentState.COMPLETE)
        assert result is False
        assert state_manager.current_state == AgentState.IDLE
    
    def test_transition_chain(self, state_manager):
        """Test a chain of valid transitions."""
        assert state_manager.transition_to(AgentState.THINKING)
        assert state_manager.transition_to(AgentState.EXECUTING)
        assert state_manager.transition_to(AgentState.THINKING)
        assert state_manager.transition_to(AgentState.COMPLETE)
        
        assert state_manager.current_state == AgentState.COMPLETE
        assert len(state_manager.history) == 4
    
    def test_force_transition(self, state_manager):
        """Test forcing a transition."""
        state_manager.force_transition(AgentState.ERROR, reason="Test error")
        assert state_manager.current_state == AgentState.ERROR
        assert "FORCED" in state_manager.history[-1].reason
    
    def test_reset(self, state_manager):
        """Test resetting state."""
        state_manager.transition_to(AgentState.THINKING)
        state_manager.transition_to(AgentState.EXECUTING)
        
        state_manager.reset()
        
        assert state_manager.current_state == AgentState.IDLE
        assert len(state_manager.history) == 0
    
    def test_is_terminal(self, state_manager):
        """Test terminal state detection."""
        assert state_manager.is_terminal() is False
        
        state_manager.transition_to(AgentState.THINKING)
        state_manager.transition_to(AgentState.COMPLETE)
        
        assert state_manager.is_terminal() is True
    
    def test_is_active(self, state_manager):
        """Test active state detection."""
        assert state_manager.is_active() is False
        
        state_manager.transition_to(AgentState.THINKING)
        assert state_manager.is_active() is True


class TestStateTransition:
    """Tests for StateTransition dataclass."""
    
    def test_create_transition(self):
        """Test creating a state transition."""
        transition = StateTransition(
            from_state=AgentState.IDLE,
            to_state=AgentState.THINKING,
            reason="Starting work"
        )
        
        assert transition.from_state == AgentState.IDLE
        assert transition.to_state == AgentState.THINKING
        assert transition.reason == "Starting work"
        assert transition.timestamp is not None
