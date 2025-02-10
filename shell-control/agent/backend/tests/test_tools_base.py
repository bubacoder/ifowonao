import pytest
from typing import Optional
from tools_base import ToolsBase, tool

# Test class that implements ToolsBase


class TestTools(ToolsBase):
    def __init__(self, settings: Optional[dict] = None):
        super().__init__(settings)

    @tool(name="test_tool")
    def test_tool(self, param1: str) -> str:
        """
        Purpose: Test tool
        Parameters:
          param1: "test parameter"
        """
        return f"Test output: {param1}"

    @tool(name="formatted_tool", formatter_function="format_test_output")
    def formatted_tool(self, param1: str) -> dict:
        """
        Purpose: Test formatted tool
        Parameters:
          param1: "test parameter"
        """
        return {"result": param1}

    def format_test_output(self, result: dict) -> str:
        return f"Formatted: {result['result']}"


def test_tool_decorator():
    # Test that tool decorator properly marks functions
    tools = TestTools()
    assert hasattr(tools.test_tool, '_is_tool')
    assert tools.test_tool._tool_name == "test_tool"


def test_fill_toolset():
    tools = TestTools()
    assert "test_tool" in tools.toolset
    assert "formatted_tool" in tools.toolset
    assert callable(tools.toolset["test_tool"]["function"])


def test_get_tool():
    tools = TestTools()
    func, formatter = tools.get_tool("test_tool")
    assert callable(func)
    assert formatter is None

    func, formatter = tools.get_tool("formatted_tool")
    assert callable(func)
    assert callable(formatter)


def test_get_tool_names():
    tools = TestTools()
    names = tools.get_tool_names()
    assert "test_tool" in names
    assert "formatted_tool" in names


def test_get_tool_definitions():
    tools = TestTools()
    definitions = tools.get_tool_definitions()
    assert "test_tool" in definitions
    assert "formatted_tool" in definitions
    assert "Purpose: Test tool" in definitions
