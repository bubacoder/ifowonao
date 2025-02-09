from typing import Dict, Any, Optional
from tools_base import ToolsBase, tool
from bs4 import BeautifulSoup
from markdownify import markdownify as md
import aiohttp
import tempfile
import asyncio
import os
import re


class AgentTools(ToolsBase):
    def __init__(self, settings: Optional[dict] = None):
        if settings is None: settings = {}
        super().__init__(settings)

    @tool(name="read_file")
    async def read_file(self, filename: str) -> str:
        """
        Purpose: Read file contents
        Parameters:
          filename: "full path to file"
        Example:
          {"name": "read_file", "parameters": {"filename": "/var/log/syslog"}}
        """
        if not filename:
            raise Exception("Missing filename parameter for read_file")

        try:
            with open(filename, "r") as f:
                content = f.read()
            return f"Successfully read {filename}:\n{content}"
        except Exception as ex:
            raise Exception(f"Read error: {str(ex)}") from ex

    @tool(name="write_file")
    async def write_file(self, filename: str, content: str = "") -> str:
        """
        Purpose: Create/modify files
        Parameters:
          filename: "full path",
          content: "text content"
        Example:
          {"name": "write_file", "parameters": {"filename": "script.sh", "content": "#!/bin/bash\\necho 'Hello'"}}
        """
        if not filename:
            raise Exception("Missing filename parameter for write_file")

        try:
            directory = os.path.dirname(filename)
            if directory:
                os.makedirs(directory, exist_ok=True)

            with open(filename, "w") as f:
                f.write(content)
            return f"Successfully wrote to {filename}"
        except Exception as ex:
            raise Exception(f"Write error: {str(ex)}") from ex

    @tool(name="execute_shell_command", formatter_function="format_shell_command_result")
    async def execute_shell_command(self, command: str) -> Dict[str, Any]:
        """
        Purpose: Run bash commands
        Parameters:
          command: "exact bash command to execute"
        Example:
          {"name": "execute_shell_command", "parameters": {"command": "ls -l /etc"}}
        """
        if not command:
            raise Exception("Missing command parameter for execute_shell_command")

        try:
            additional_error = None
            process_timeout = self.settings.get("shell_timeout_seconds", 2 * 60)

            with tempfile.NamedTemporaryFile(suffix=".sh", delete=False) as temp_file:
                script_filename = temp_file.name
                temp_file.write(b"# Note: this file contains the command to be executed by the LLM.\n")
                temp_file.write(command.encode())

            # Asynchronously create subprocess
            process = await asyncio.create_subprocess_exec(
                "bash", script_filename,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                # Wait for the process to complete with a timeout
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=process_timeout
                )

                # Collect output and error
                output = stdout.decode().strip()
                error = stderr.decode().strip()
            except asyncio.TimeoutError:
                process.kill()  # Kill the process if it exceeds the timeout
                await process.wait()  # Wait for the process to clean up after being killed
                additional_error = f"Error: The command execution exceeded the timeout of {process_timeout} seconds and was killed."
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

    def format_shell_command_result(self, command_result: Dict[str, Any]) -> str:
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

    @tool(name="fetch_webpage")
    async def fetch_webpage(self, url: str) -> str:
        """
        Fetches the content of a webpage and converts it to Markdown format.

        Args:
            url (str): The URL of the webpage.

        Returns:
            str: The content of the webpage formatted in Markdown, or an error message if the request fails.

        Example:
            {"name": "fetch_webpage", "parameters": {"url": "https://aider.chat/docs/install.html"}}
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()  # Raise an exception for HTTP errors
                    html_content = await response.text()

            # Parse the HTML content using BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # Convert the content to Markdown
            markdown_content = md(str(soup))

            return markdown_content.strip()

        except (aiohttp.ClientError, aiohttp.ClientResponseError) as ex:
            return f"Error: Unable to fetch the content due to: {ex}"

    @tool(name="develop_code", formatter_function="format_shell_command_result")
    async def develop_code(self, development_task: str, filename: str) -> Dict[str, Any]:
        """
        Purpose: Develop new or change existing program code (python, golang or anything else)
        Parameters:
          development_task: "a few sentence long description of the programming task to perform"
          filename: "name the new or existing file. multiple filenames and wildcards (e.g. *.py) can be also used is the application spans multiple files"
        Example:
          {"name": "develop_code", "parameters": {"development_task": "Add docstrings to all functions and create unit tests. Use a well-established unit-testing framework.", "filename": "myapp.py"}}
        """
        coder_model = self.settings.get("coder_model")
        openai_api_base = self.settings.get("openai_base_url")
        openai_api_key = self.settings.get("openai_api_key")

        command = "aider --no-auto-commits --no-git --no-check-update --no-pretty --no-analytics --yes-always"

        if coder_model:
            command += f" --model {coder_model}"
        if openai_api_base:
            command += f" --openai-api-base {openai_api_base}"
        if openai_api_key:
            command += f" --openai-api-key {openai_api_key}"

        command += f" --message \"{development_task}\" {filename}"

        return await self.execute_shell_command(command)
