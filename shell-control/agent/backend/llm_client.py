from typing import Union, Dict, Any, Optional
from openai import OpenAI
from datetime import datetime
import pathlib
import json

# Cost/million tokens in USD
INPUT_COST_PER_MILLION = 0.4
OUTPUT_COST_PER_MILLION = 0.4
NATIVE_CURRENCY = "HUF"
NATIVE_CURRENCY_PER_USD = 404

DEFAULT_LOG_DIR = "logs"


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str, prompt_filename: str = 'system-prompt.md'):
        self.model = model
        self.usage = {}
        self.reset_usage()

        with open(prompt_filename, 'r') as file:
            system_prompt = file.read()

        self.messages: list[Dict[str, Union[str, Any]]] = []
        self.append_message('system', system_prompt)

        self.client = OpenAI(base_url=base_url, api_key=api_key)

    def query(self) -> str:
        response = self.client.chat.completions.create(model=self.model, messages=self.messages)
        self.update_usage_stats(response.usage.prompt_tokens, response.usage.completion_tokens)
        return response.choices[0].message.content.strip()

    def append_message(self, role: str, message: str) -> None:
        self.messages.append({'role': role, 'content': message})

    def append_user_message(self, message: str) -> None:
        self.append_message('user', message)

    def append_assistant_message(self, message: str) -> None:
        self.append_message('assistant', message)

    def update_usage_stats(self, add_prompt_tokens: int = 0, add_completion_tokens: int = 0) -> None:
        # Add tokens to total
        self.usage["prompt_tokens"] += add_prompt_tokens
        self.usage["completion_tokens"] += add_completion_tokens
        # Calculate cost
        self.usage["prompt_cost"] = self.usage["prompt_tokens"] / 1_000_000 * INPUT_COST_PER_MILLION
        self.usage["completion_cost"] = self.usage["completion_tokens"] / 1_000_000 * OUTPUT_COST_PER_MILLION
        self.usage["total_cost"] = self.usage["prompt_cost"] + self.usage["completion_cost"]
        self.usage["total_cost_native"] = self.usage["total_cost"] * NATIVE_CURRENCY_PER_USD

    def reset_usage(self):
        self.usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "prompt_cost": 0.0,
            "completion_cost": 0.0,
            "total_cost": 0.0,
            "total_cost_native": 0.0
        }

    def get_usage_summary(self) -> str:
        return (
            f"Tokens: {self.usage['prompt_tokens']} sent + {self.usage['completion_tokens']} received = "
            f"{self.usage['prompt_tokens'] + self.usage['completion_tokens']} total\n"
            f"Total cost: USD {self.usage['total_cost']:.4f} / {NATIVE_CURRENCY} {self.usage['total_cost_native']:.4f}"
        )

    def get_total_cost(self) -> float:
        return self.usage["total_cost"]

    def save_messages(self, log_dir: str = DEFAULT_LOG_DIR, conclusion: Optional[str] = None, user_prompt: Optional[str] = None) -> str:
        """
        Save conversation messages to a JSON file in the specified directory.
        Args:
            log_dir: Directory to save the log file
            conclusion: How the conversation ended (e.g. "completed", "failed", "aborted_due_cost")
            user_prompt: The original user prompt that started the conversation
        Returns the path to the saved file.
        """
        # Ensure log directory exists
        log_path = pathlib.Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        
        # Create filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = log_path / f"conversation_{timestamp}.json"
        
        # Prepare log data
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "user_prompt": user_prompt,
            "conclusion": conclusion,
            "model": self.model,
            "messages": self.messages,
            "usage": self.usage,
        }
        
        # Write to file with nice formatting
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        
        return str(filename)
