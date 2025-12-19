"""Tests for the tool system."""

import pytest

from pentestagent.tools import (
    Tool, ToolSchema, register_tool, get_all_tools, get_tool,
    enable_tool, disable_tool, get_tool_names
)


class TestToolRegistry:
    """Tests for tool registry functions."""
    
    def test_tools_loaded(self):
        """Test that built-in tools are loaded."""
        tools = get_all_tools()
        assert len(tools) > 0
        
        tool_names = get_tool_names()
        assert "terminal" in tool_names
        assert "browser" in tool_names
    
    def test_get_tool(self):
        """Test getting a tool by name."""
        tool = get_tool("terminal")
        assert tool is not None
        assert tool.name == "terminal"
        assert tool.category == "execution"
    
    def test_get_nonexistent_tool(self):
        """Test getting a tool that doesn't exist."""
        tool = get_tool("nonexistent_tool_xyz")
        assert tool is None
    
    def test_disable_enable_tool(self):
        """Test disabling and enabling a tool."""
        result = disable_tool("terminal")
        assert result is True
        
        tool = get_tool("terminal")
        assert tool.enabled is False
        
        result = enable_tool("terminal")
        assert result is True
        
        tool = get_tool("terminal")
        assert tool.enabled is True
    
    def test_disable_nonexistent_tool(self):
        """Test disabling a tool that doesn't exist."""
        result = disable_tool("nonexistent_tool_xyz")
        assert result is False


class TestToolSchema:
    """Tests for ToolSchema class."""
    
    def test_create_schema(self):
        """Test creating a tool schema."""
        schema = ToolSchema(
            properties={
                "command": {"type": "string", "description": "Command to run"}
            },
            required=["command"]
        )
        
        assert schema.type == "object"
        assert "command" in schema.properties
        assert "command" in schema.required
    
    def test_schema_to_dict(self):
        """Test converting schema to dictionary."""
        schema = ToolSchema(
            properties={"input": {"type": "string"}},
            required=["input"]
        )
        
        d = schema.to_dict()
        assert d["type"] == "object"
        assert d["properties"]["input"]["type"] == "string"
        assert d["required"] == ["input"]


class TestTool:
    """Tests for Tool class."""
    
    def test_create_tool(self, sample_tool):
        """Test creating a tool."""
        assert sample_tool.name == "test_tool"
        assert sample_tool.description == "A test tool"
        assert sample_tool.category == "test"
        assert sample_tool.enabled is True
    
    def test_tool_to_llm_format(self, sample_tool):
        """Test converting tool to LLM format."""
        llm_format = sample_tool.to_llm_format()
        
        assert llm_format["type"] == "function"
        assert llm_format["function"]["name"] == "test_tool"
        assert llm_format["function"]["description"] == "A test tool"
        assert "parameters" in llm_format["function"]
    
    def test_tool_validate_arguments(self, sample_tool):
        """Test argument validation."""
        is_valid, error = sample_tool.validate_arguments({"param": "value"})
        assert is_valid is True
        assert error is None
        
        is_valid, error = sample_tool.validate_arguments({})
        assert is_valid is False
        assert "param" in error
    
    @pytest.mark.asyncio
    async def test_tool_execute(self, sample_tool):
        """Test tool execution."""
        result = await sample_tool.execute({"param": "test"}, runtime=None)
        assert "test" in result


class TestRegisterToolDecorator:
    """Tests for register_tool decorator."""
    
    def test_decorator_registers_tool(self):
        """Test that decorator registers a new tool."""
        initial_count = len(get_all_tools())
        
        @register_tool(
            name="pytest_test_tool_unique",
            description="A tool registered in tests",
            schema=ToolSchema(properties={}, required=[]),
            category="test"
        )
        async def pytest_test_tool_unique(arguments, runtime):
            return "test result"
        
        new_count = len(get_all_tools())
        assert new_count == initial_count + 1
        
        tool = get_tool("pytest_test_tool_unique")
        assert tool is not None
        assert tool.name == "pytest_test_tool_unique"
