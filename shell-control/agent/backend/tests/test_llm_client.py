from llm_client import LLMClient
import json
import tempfile
import pathlib


@pytest.fixture
def llm_client():
    return LLMClient(
        base_url="http://test",
        api_key="test-key",
        model="test-model",
        system_prompt="test prompt"
    )


def test_append_message(llm_client):
    llm_client.append_message('user', 'test message')
    assert len(llm_client.messages) == 2  # Including system prompt
    assert llm_client.messages[-1]['role'] == 'user'
    assert llm_client.messages[-1]['content'] == 'test message'


def test_update_usage_stats(llm_client):
    llm_client.update_usage_stats(100, 50)
    assert llm_client.usage["prompt_tokens"] == 100
    assert llm_client.usage["completion_tokens"] == 50
    assert llm_client.usage["total_cost"] > 0


def test_reset_usage(llm_client):
    llm_client.update_usage_stats(100, 50)
    llm_client.reset_usage()
    assert llm_client.usage["prompt_tokens"] == 0
    assert llm_client.usage["completion_tokens"] == 0
    assert llm_client.usage["total_cost"] == 0


def test_get_usage_summary(llm_client):
    llm_client.update_usage_stats(100, 50)
    summary = llm_client.get_usage_summary()
    assert "Tokens: 100 sent + 50 received = 150 total" in summary
    assert "Total cost: USD" in summary


@pytest.mark.asyncio
async def test_save_messages(llm_client):
    with tempfile.TemporaryDirectory() as tmpdir:
        llm_client.append_message('user', 'test message')
        saved_file = llm_client.save_messages(
            log_dir=tmpdir,
            conclusion="completed",
            user_prompt="test prompt"
        )

        # Verify file exists and contains expected data
        assert pathlib.Path(saved_file).exists()
        with open(saved_file, 'r') as f:
            data = json.load(f)
            assert data["conclusion"] == "completed"
            assert data["user_prompt"] == "test prompt"
            assert len(data["messages"]) == 2
