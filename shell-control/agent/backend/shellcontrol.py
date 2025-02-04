#!/usr/bin/env python3
# Note: can be used as a terminal application and also imported as a Python module

from typing import Dict, Any, Optional, AsyncGenerator, Callable
from llm_client import LLMClient
from agent_tools import AgentTools
from enum import Enum
from rich import print as rprint
from rich.pretty import pprint
from traceback import format_exc
import asyncio
import json
import sys
import os

# Global Constants
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL')
DEBUG = os.getenv('DEBUG', '0').lower() in ('true', '1')
ABORT_ON_TOTAL_COST = 0.5

class Event(Enum):
    AI_RESPONSE = 1
    TOOL_SUCCESS = 2
    TOOL_ERROR = 3
    INFO = 10
    WARN = 11
    ABORT = 12
    COMPLETED = 20


class ShellAgent:
    def __init__(self):
        self.client: LLMClient = None
        self.tools: AgentTools = AgentTools()

    def event(self, event_type: Event, payload: Any) -> Dict[str, Any]:
        return {"type": event_type, "payload": payload}

    def get_response(self, response: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        return None

    def get_tool_call(self, response_object: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return response_object.get("tool_to_use") if response_object else {}

    def get_usage_summary(self) -> str:
        return self.client.get_usage_summary()

    async def call_tool(self, parameters: Dict[str, Any], function: Callable, formatter_function: Optional[Callable]) -> Dict[str, Any]:
        try:
            tool_result = await function(**parameters)
            if formatter_function is None:
                self.client.append_user_message(tool_result)
            else:
                tool_result_formatted = formatter_function(tool_result)
                self.client.append_user_message(tool_result_formatted)
            return self.event(Event.TOOL_SUCCESS, tool_result)
        except Exception as ex:
            return self.event(Event.TOOL_ERROR, str(ex))

    async def process_user_request(self, user_prompt: str) -> AsyncGenerator[Dict[str, Any], None]:
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

                response_object = self.get_response(response_text)
                if response_object:
                    yield self.event(Event.AI_RESPONSE, response_object)
                else:
                    yield self.event(Event.AI_RESPONSE, response_text)
                    yield self.event(Event.WARN, "Invalid JSON data provided. Trying again.")
                    continue

                tool_call = self.get_tool_call(response_object)
                if not tool_call:
                    self.client.save_messages(conclusion="failed", user_prompt=user_prompt)
                    yield self.event(Event.ABORT, "No tool selection provided. Exiting.")
                    break

                self.client.append_assistant_message(response_text)

                tool_name = tool_call.get("name")
                parameters = tool_call.get("parameters", {})

                if tool_name == "task_complete":
                    summary = parameters.get("summary", "")
                    self.client.save_messages(conclusion="completed", user_prompt=user_prompt)
                    yield self.event(Event.COMPLETED, summary)
                    break
                else:
                    (function, formatter_function) = self.tools.get_by_name(tool_name)
                    if function:
                        yield await self.call_tool(parameters, function, formatter_function)
                    else:
                        self.client.save_messages(conclusion="failed", user_prompt=user_prompt)
                        yield self.event(Event.ABORT, f"Unsupported tool selected: {tool_name}. Exiting.")
                        break

                # Cost check after handling each tool
                if ABORT_ON_TOTAL_COST > 0 and self.client.get_total_cost() > ABORT_ON_TOTAL_COST:
                    self.client.save_messages(conclusion="aborted_due_cost", user_prompt=user_prompt)
                    yield self.event(Event.ABORT, f"Total cost is exceeding the limit (${ABORT_ON_TOTAL_COST}). Exiting.")
                    break

        except Exception as ex:
            exception_text = format_exc() if DEBUG else str(ex)
            yield self.event(Event.ABORT, exception_text)


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
                        if event["payload"]["returncode"] is not None:
                            print(agent.tools.format_shell_command_result(event["payload"]))
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
                rprint(f"\n[bold]==> Unable to parse event: {event}")

            sys.stdout.flush()

    except KeyboardInterrupt:
        rprint("\n[bold red]User interrupted the program. Exiting...[/bold red]")

    except Exception as ex:
        rprint(f"\n[bold red]Exception: {str(ex)}[/bold red]")

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
