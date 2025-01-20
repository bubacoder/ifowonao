#!/usr/bin/env python3
# Note: can be used as a terminal application and also imported as a Python module

from typing import Union, Dict, Any, Optional
from openai import OpenAI
from enum import Enum
from rich import print as rprint
from traceback import format_exc
import asyncio
import json
import sys
import os


# Global Constants
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL')
DEBUG = True

# Cost/million tokens in USD
INPUT_COST_PER_MILLION = 0.4
OUTPUT_COST_PER_MILLION = 0.4
NATIVE_CURRENCY = "HUF"
NATIVE_CURRENCY_PER_USD = 404

# Limits
ABORT_ON_TOTAL_COST = 0.5
COMMAND_TIMEOUT_SECONDS = 2 * 60


class Event(Enum):
    AI_RESPONSE = 1
    COMMAND_RESULT = 2
    INFO = 3
    WARN = 4
    ABORT = 5
    COMPLETED = 6


class ShellAgent:
    def __init__(self):
        self.usage = {}

    def emit(self, event_type: Event, payload: Any) -> dict:
        return {"type": event_type, "payload": payload}

    async def run_shell_command_async(self, command: str) -> dict:
        try:
            script_filename = "command.sh"
            with open(script_filename, "w") as script_file:
                script_file.write("# Note: this file contains the last command executed by the LLM.\n")
                script_file.write(command)

            # Asynchronously create subprocess
            process = await asyncio.create_subprocess_exec(
                "bash", script_filename,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            additional_error = None

            try:
                # Wait for the process to complete with a timeout
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=COMMAND_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                process.kill()  # Kill the process if it exceeds the timeout
                await process.wait()  # Wait for the process to clean up after being killed
                additional_error = f"Error: The command execution exceeded the timeout of {COMMAND_TIMEOUT_SECONDS} seconds and was killed."
                stdout, stderr = b"", b""  # Handle case where output is absent due to timeout

            # Collect output and error
            output = stdout.decode().strip()
            error = stderr.decode().strip()

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

    def query_llm(self, client: OpenAI, messages: list[Dict[str, Union[str, Any]]]) -> str:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
        )

        self.update_usage_stats(
            response.usage.prompt_tokens,
            response.usage.completion_tokens
        )

        return response.choices[0].message.content.strip()

    def parse_response(self, response: Union[str, Dict]) -> Optional[Dict]:
        try:
            if isinstance(response, str):
                return json.loads(response)
        except json.JSONDecodeError:
            pass
        return None

    def get_command(self, response_object: Optional[Dict]) -> Optional[str]:
        return response_object.get("command") if response_object else None

    async def process_user_request(self, user_prompt: str):
        """
        Main entry point for processing a user's prompt. Outputs results as events for streaming.
        """
        try:
            # Read the system prompt
            with open('system-prompt.md', 'r') as file:
                system_prompt = file.read()

            self.reset_usage()

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            # Initialize OpenAI client
            client = OpenAI(
                base_url=OPENAI_BASE_URL,
                api_key=OPENAI_API_KEY,
            )

            while True:
                # Query the model
                response_text = self.query_llm(client, messages)

                response_object = self.parse_response(response_text)
                if response_object:
                    yield self.emit(Event.AI_RESPONSE, response_object)
                else:
                    yield self.emit(Event.AI_RESPONSE, response_text)
                    yield self.emit(Event.WARN, "Invalid JSON data provided. Trying again.")
                    continue

                command = self.get_command(response_object)
                if command is None:
                    yield self.emit(Event.ABORT, "No command provided. Exiting.")
                    break
                if command == "COMPLETED":
                    yield self.emit(Event.COMPLETED, None)
                    break

                # Append assistant's response to the conversation
                messages.append({
                    "role": "assistant",
                    "content": response_text
                })

                # Run the shell command asynchronously
                command_result = await self.run_shell_command_async(command)
                yield self.emit(Event.COMMAND_RESULT, command_result)

                # Append output to conversation
                messages.append({
                    "role": "user",
                    "content": self.format_command_result(command_result)
                })

                if ABORT_ON_TOTAL_COST > 0 and self.usage["total_cost"] > ABORT_ON_TOTAL_COST:
                    yield self.emit(Event.ABORT, f"Total cost is exceeding the limit (USD ${ABORT_ON_TOTAL_COST}). Exiting.")
                    break

        except Exception as ex:
            exception_text = format_exc() if DEBUG else str(ex)
            yield self.emit(Event.ABORT, exception_text)

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
            f"Token usage: {self.usage['prompt_tokens']} input + {self.usage['completion_tokens']} output = "
            f"{self.usage['prompt_tokens'] + self.usage['completion_tokens']} total\n"
            f"Total cost: USD {self.usage['total_cost']:.4f} / {NATIVE_CURRENCY} {self.usage['total_cost_native']:.4f}"
        )


def main(user_prompt: str) -> None:
    agent = ShellAgent()
    try:
        rprint(f"Welcome to Linux shell agent powered by \"{OPENAI_MODEL}\"!")
        rprint(f"Request from the user: [bold]\"{user_prompt}\"[/bold]")
        rprint("[bold red]Press Ctrl+C to stop iteration at any step.[/bold red]")

        for event in agent.process_user_request(user_prompt):
            if event["type"]:
                match event["type"]:
                    case Event.AI_RESPONSE:
                        rprint("\n[bold]=== AI Response ===[/bold]")
                        rprint(event["payload"])
                    case Event.COMMAND_RESULT:
                        rprint("\n[bold]=== Shell Output ===[/bold]")
                        print(agent.format_command_result(event["payload"]))
                    case Event.INFO:
                        rprint(f"\n[bold]==> {event['payload']}")
                    case Event.WARN:
                        rprint(f"\n[bold]==> WARNING: {event['payload']}")
                    case Event.ABORT:
                        rprint(f"\n[bold]==> ERROR: {event['payload']}")
                    case Event.COMPLETED:
                        rprint("\n[bold]==> The AI has completed the task. Exiting.")
                    case _:
                        rprint(f"\n[bold]==> WARNING UNHANDLED EVENT: {event}")
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
    asyncio.run(main(user_prompt))
