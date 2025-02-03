#!/usr/bin/env python3
# Note: can be used as a terminal application and also imported as a Python module

from typing import Union, Dict, Any, Optional
from openai import OpenAI
from enum import Enum
from rich import print as rprint
from rich.pretty import pprint
from traceback import format_exc
from datetime import datetime
import pathlib
import asyncio
import tempfile
import json
import sys
import os
import re


# Global Constants
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL')
DEBUG = os.getenv('DEBUG', '0').lower() in ('true', '1')

# Cost/million tokens in USD
INPUT_COST_PER_MILLION = 0.4
OUTPUT_COST_PER_MILLION = 0.4
NATIVE_CURRENCY = "HUF"
NATIVE_CURRENCY_PER_USD = 404

# Default log directory (can be overridden)
DEFAULT_LOG_DIR = "logs"

# Limits
ABORT_ON_TOTAL_COST = 0.5
COMMAND_TIMEOUT_SECONDS = 2 * 60


class Event(Enum):
    AI_RESPONSE = 1
    TOOL_SUCCESS = 2
    TOOL_ERROR = 3
    INFO = 10
    WARN = 11
    ABORT = 12
    COMPLETED = 20


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

    def save_messages(self, log_dir: str = DEFAULT_LOG_DIR, conclusion: str = None, user_prompt: str = None) -> str:
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


class ShellAgent:
    def __init__(self):
        self.client: LLMClient = None

    def event(self, event_type: Event, payload: Any) -> dict:
        return {"type": event_type, "payload": payload}

    async def run_shell_command_async(self, command: Union[str, dict]) -> dict:
        try:
            additional_error = None

            with tempfile.NamedTemporaryFile(suffix=".sh", delete=False) as temp_file:
                script_filename = temp_file.name
                temp_file.write(b"# Note: this file contains the command to be executed by the LLM.\n")
                if isinstance(command, dict):
                    command = command.get("parameters", {}).get("command", "")
                temp_file.write(command.encode())

            # Asynchronously create subprocess
            process = await asyncio.create_subprocess_exec(
                "bash", script_filename,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                # Wait for the process to complete with a timeout
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=COMMAND_TIMEOUT_SECONDS)
                # Collect output and error
                output = stdout.decode().strip()
                error = stderr.decode().strip()
            except asyncio.TimeoutError:
                process.kill()  # Kill the process if it exceeds the timeout
                await process.wait()  # Wait for the process to clean up after being killed
                additional_error = f"Error: The command execution exceeded the timeout of {COMMAND_TIMEOUT_SECONDS} seconds and was killed."
                stdout, stderr = "", ""  # Handle case where output is absent due to timeout
            finally:
                # Delete the temporary script file
                if os.path.exists(script_filename):
                    os.remove(script_filename)

            # Clean up error message by removing temporary file reference
            if error:
                error = re.sub(r'^/tmp/[^:]+\.sh: line \d+: ', 'bash: ', error)

            return {
                "output": output,
                "error": error,
                "additional_error": additional_error,
                "returncode": process.returncode
            }

        except Exception as ex:
            return {
                "output": "",
                "error": "",
                "additional_error": f"Unexpected error: {str(ex)}",
                "returncode": -1
            }

    def format_command_result(self, command_result: dict) -> str:
        output = command_result.get("output", "")
        error = command_result.get("error", "")
        additional_error = command_result.get("additional_error", "")
        returncode = command_result.get("returncode", 0)

        # Describe output and error
        output_described = output if output else "(The command produced no output)"
        error_described = error if error else "(The command produced no error output)"

        # If there's an additional error due to timeout or other issues, append it
        if additional_error:
            error_described = "\n".join([error_described, additional_error])

        # Construct formatted message
        output_section = f"Output of the command:\n```\n{output_described}\n```\n"
        error_section = "" if returncode == 0 else f"Errors:\n```\n{error_described}\n```\n"
        exit_section = f"Exit status: {returncode}"

        return output_section + error_section + exit_section

    def parse_response(self, response: Union[str, Dict]) -> Optional[Dict]:
        try:
            if isinstance(response, str):
                return json.loads(response)
        except json.JSONDecodeError:
            pass
        return None

    def get_tool_call(self, response_object: Optional[Dict]) -> dict:
        return response_object.get("tool_to_use") if response_object else {}

    def get_usage_summary(self) -> str:
        return self.client.get_usage_summary()

    async def process_user_request(self, user_prompt: str):
        """
        Main entry point for processing a user's prompt. Outputs results as events for streaming.
        """
        try:
            self.client = LLMClient(
                base_url=OPENAI_BASE_URL,
                api_key=OPENAI_API_KEY,
                model=OPENAI_MODEL,
                prompt_filename='agent-system-prompt.md')
            
            self.client.append_user_message(user_prompt)

            while True:
                response_text = self.client.query()

                response_object = self.parse_response(response_text)
                if response_object:
                    yield self.event(Event.AI_RESPONSE, response_object)
                else:
                    yield self.event(Event.AI_RESPONSE, response_text)
                    yield self.event(Event.WARN, "Invalid JSON data provided. Trying again.")
                    continue

                tool_call = self.get_tool_call(response_object)
                if not tool_call:
                    yield self.event(Event.ABORT, "No tool selection provided. Exiting.")
                    break

                # Log the assistant's response first - common for all tools
                self.client.append_assistant_message(response_text)

                # Dispatch to specific handler
                tool_name = tool_call.get("name")
                parameters = tool_call.get("parameters", {})
                
                match tool_name:
                    case "execute_shell_command":
                        tool_event = await self.handle_execute_shell_command(parameters)
                        match tool_event["type"]:
                            case Event.TOOL_SUCCESS:
                                command_result_formatted = self.format_command_result(tool_event["payload"])
                                self.client.append_user_message(command_result_formatted)
                                yield tool_event
                            case Event.TOOL_ERROR:
                                self.client.append_user_message(tool_event["payload"])
                                yield tool_event

                    case "read_file":
                        tool_event = self.handle_read_file(parameters)
                        self.client.append_user_message(tool_event["payload"])
                        yield tool_event

                    case "write_file":
                        tool_event = self.handle_write_file(parameters)
                        self.client.append_user_message(tool_event["payload"])
                        yield tool_event

                    case "task_complete":
                        summary = parameters.get("summary", "")
                        log_file = self.client.save_messages(conclusion="completed", user_prompt=user_prompt)
                        yield self.event(Event.INFO, f"Conversation saved to: {log_file}")
                        yield self.event(Event.COMPLETED, summary)
                        break

                    case _:
                        log_file = self.client.save_messages(conclusion="failed", user_prompt=user_prompt)
                        yield self.event(Event.INFO, f"Conversation saved to: {log_file}")
                        yield self.event(Event.ABORT, f"Unknown tool selected: {tool_name}. Exiting.")
                        break

                # Cost check after handling each tool
                if ABORT_ON_TOTAL_COST > 0 and self.client.get_total_cost() > ABORT_ON_TOTAL_COST:
                    log_file = self.client.save_messages(conclusion="aborted_due_cost", user_prompt=user_prompt)
                    yield self.event(Event.INFO, f"Conversation saved to: {log_file}")
                    yield self.event(Event.ABORT, f"Total cost is exceeding the limit (${ABORT_ON_TOTAL_COST}). Exiting.")
                    break

        except Exception as ex:
            exception_text = format_exc() if DEBUG else str(ex)
            yield self.event(Event.ABORT, exception_text)

    async def handle_execute_shell_command(self, parameters: dict):
        command = parameters.get("command")
        if not command:
            return self.event(Event.TOOL_ERROR, "Missing command parameter for execute_shell_command")

        command_result = await self.run_shell_command_async(command)
        return self.event(Event.TOOL_SUCCESS, command_result)

    def handle_read_file(self, parameters: dict):
        filename = parameters.get("filename")
        if not filename:
            return self.event(Event.TOOL_ERROR, "Missing filename parameter for read_file")

        try:
            with open(filename, "r") as f:
                content = f.read()
            return self.event(Event.TOOL_SUCCESS, f"Successfully read {filename}:\n{content}")
        except Exception as e:
            return self.event(Event.TOOL_ERROR, f"Read error: {str(e)}")

    def handle_write_file(self, parameters: dict):
        filename = parameters.get("filename")
        content = parameters.get("content", "")
        if not filename:
            return self.event(Event.TOOL_ERROR, "Missing filename parameter for write_file")

        try:
            # Ensure directory exists
            directory = os.path.dirname(filename)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(filename, "w") as f:
                f.write(content)
            return self.event(Event.TOOL_SUCCESS, f"Successfully wrote to {filename}")
        except Exception as e:
            return self.event(Event.TOOL_ERROR, f"Write error: {str(e)}")


async def cli_main(user_prompt: str) -> None:
    agent = ShellAgent()
    try:
        rprint(f"Welcome to Linux shell agent powered by \"{OPENAI_MODEL}\"!")
        rprint(f"Request from the user: [bold]\"{user_prompt}\"[/bold]")
        rprint("[bold red]Press Ctrl+C to stop iteration at any step.[/bold red]")

        async for event in agent.process_user_request(user_prompt):
            if event["type"]:
                match event["type"]:
                    case Event.AI_RESPONSE:
                        rprint("\n[bold]=== AI Response ===[/bold]")
                        pprint(event["payload"], expand_all=True)
                    case Event.TOOL_SUCCESS:
                        rprint("\n[bold]=== Tool Output ===[/bold]")
                        if event["payload"]["returncode"] != None:
                            print(agent.format_command_result(event["payload"]))
                        else:
                            print(event["payload"])
                    case Event.TOOL_ERROR:
                        rprint("\n[bold]=== Tool Output - ERROR ===[/bold]")
                        print(event["payload"])
                    case Event.INFO:
                        rprint(f"\n[bold]==> {event['payload']}")
                    case Event.WARN:
                        rprint(f"\n[bold]==> WARNING: {event['payload']}")
                    case Event.ABORT:
                        rprint(f"\n[bold]==> ERROR: {event['payload']}")
                    case Event.COMPLETED:
                        rprint("\n[bold]==> The AI has completed the task. Exiting.")
                    case _:
                        rprint(f"\n[bold]==> WARNING: Unhandled event: {event}")
            else:
                rprint(f"\n[bold]==> UNABLE TO PARSE EVENT: {event}")

            sys.stdout.flush()

    except KeyboardInterrupt:
        rprint("\n[bold red]User interrupted the program. Exiting...[/bold red]")

    except Exception as e:
        rprint(f"\n[bold red]Exception: {str(e)}[/bold red]")

    # Display usage summary after processing
    rprint("\n[bold]=== Usage Summary ===[/bold]")
    rprint(agent.get_usage_summary())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        rprint("Error: Please provide a prompt as a startup argument.")
        rprint("Usage: python shellcontrol.py '<your_prompt>'")
        sys.exit(1)

    user_prompt = sys.argv[1]
    asyncio.run(cli_main(user_prompt))
