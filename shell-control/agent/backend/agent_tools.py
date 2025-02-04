from typing import Optional, Callable, Dict, Any, Tuple
import tempfile
import asyncio
import os
import re


# A decorator for marking methods as tools
def tool(name: str, formatter_function: Optional[str] = None) -> Callable:
    def decorator(func: Callable) -> Callable:
        func._is_tool = True  # Mark the function as a tool
        func._tool_name = name  # Set the name of the tool
        func._formatter_function = formatter_function  # Optional formatter function
        return func
    return decorator


class AgentTools:
    def __init__(self, tool_timeout_seconds: int = 2 * 60):
        self.tool_timeout_seconds = tool_timeout_seconds
        
        # Dynamically populate the toolset by inspecting annotated methods
        self.toolset = {}

        for method_name in dir(self):  # Iterate over all attributes of the class
            method = getattr(self, method_name, None)

            # Filter methods that have the _is_tool attribute
            if callable(method) and getattr(method, "_is_tool", False):
                # Look up the formatter function if it's specified as a string
                if method._formatter_function:
                    formatter_callable = getattr(self, method._formatter_function, None)
                    if not callable(formatter_callable):
                        raise ValueError(
                            f"Formatter function '{method._formatter_function}' for tool '{method._tool_name}' is not callable or not defined"
                        )
                else:
                    formatter_callable = None

                # Use the `name` as the key and store its metadata
                self.toolset[method._tool_name] = {
                    "function": method,
                    "formatter_function": formatter_callable,
                }

    def get_by_name(self, name: str) -> Tuple[Optional[Callable], Optional[Callable]]:
        tool = self.toolset.get(name)
        if not tool: 
            return None, None

        function = tool.get("function")
        formatter_function = tool.get("formatter_function", None)
        return function, formatter_function

    @tool(name="read_file")
    async def read_file(self, filename: str) -> str:
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
        if not command:
            raise Exception("Missing command parameter for execute_shell_command")

        try:
            additional_error = None

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
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.tool_timeout_seconds)
                # Collect output and error
                output = stdout.decode().strip()
                error = stderr.decode().strip()
            except asyncio.TimeoutError:
                process.kill()  # Kill the process if it exceeds the timeout
                await process.wait()  # Wait for the process to clean up after being killed
                additional_error = f"Error: The command execution exceeded the timeout of {self.tool_timeout_seconds} seconds and was killed."
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
