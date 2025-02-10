import pytest
from agent_tools import AgentTools
import tempfile
import os


@pytest.fixture
def agent_tools():
    return AgentTools({"shell_timeout_seconds": 5})


@pytest.mark.asyncio
async def test_read_file():
    tools = AgentTools()
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as tf:
        tf.write("test content")
        tf.flush()
        result = await tools.read_file(tf.name)
        assert "test content" in result
        os.unlink(tf.name)


@pytest.mark.asyncio
async def test_write_file():
    tools = AgentTools()
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        result = await tools.write_file(tf.name, "test content")
        assert "Successfully wrote" in result
        with open(tf.name, 'r') as f:
            assert f.read() == "test content"
        os.unlink(tf.name)


@pytest.mark.asyncio
async def test_execute_shell_command():
    tools = AgentTools()
    result = await tools.execute_shell_command("echo 'test'")
    assert result["output"].strip() == "test"
    assert result["returncode"] == 0


def test_format_shell_command_result():
    tools = AgentTools()
    result = tools.format_shell_command_result({
        "output": "test output",
        "error": "",
        "returncode": 0
    })
    assert "test output" in result
    assert "Exit status: 0" in result
