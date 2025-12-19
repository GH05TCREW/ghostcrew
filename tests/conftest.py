"""Test fixtures for PentestAgent tests."""

import pytest
import asyncio
from pathlib import Path
from typing import Generator, AsyncGenerator
from unittest.mock import MagicMock, AsyncMock

from pentestagent.config import Settings
from pentestagent.agents.state import AgentState, AgentStateManager
from pentestagent.tools import get_all_tools, Tool, ToolSchema


@pytest.fixture
def settings() -> Settings:
    """Create test settings."""
    return Settings(
        debug=True,
    )


@pytest.fixture
def agent_state() -> AgentStateManager:
    """Create a test agent state manager."""
    return AgentStateManager()


@pytest.fixture
def mock_llm() -> MagicMock:
    """Create a mock LLM."""
    mock = AsyncMock()
    mock.generate.return_value = MagicMock(
        content="Test response",
        tool_calls=None,
        usage={"prompt_tokens": 100, "completion_tokens": 50},
        model="gpt-5",
        finish_reason="stop"
    )
    return mock


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for tests."""
    return tmp_path


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_finding() -> dict:
    """Create a sample security finding."""
    return {
        "title": "SQL Injection in Login Form",
        "severity": "high",
        "target": "http://example.com/login",
        "description": "The login form is vulnerable to SQL injection attacks.",
        "evidence": "Parameter 'username' with payload: ' OR '1'='1",
        "remediation": "Use parameterized queries or prepared statements."
    }


@pytest.fixture
def sample_tool_result() -> dict:
    """Create a sample tool execution result."""
    return {
        "tool": "terminal",
        "success": True,
        "output": "nmap scan results...",
        "duration_ms": 1500.0
    }


@pytest.fixture
def sample_tool() -> Tool:
    """Create a sample tool for testing."""
    async def dummy_execute(arguments: dict, runtime) -> str:
        return f"Executed with: {arguments}"
    
    return Tool(
        name="test_tool",
        description="A test tool",
        schema=ToolSchema(
            properties={"param": {"type": "string", "description": "A parameter"}},
            required=["param"]
        ),
        execute_fn=dummy_execute,
        category="test"
    )
