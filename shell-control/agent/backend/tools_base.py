from typing import Optional, Callable, Tuple


# A decorator for marking methods as tools
def tool(name: str, formatter_function: Optional[str] = None) -> Callable:
    def decorator(func: Callable) -> Callable:
        func._is_tool = True  # Mark the function as a tool
        func._tool_name = name  # Set the name of the tool
        func._formatter_function = formatter_function  # Optional formatter function
        return func
    return decorator


class ToolsBase:
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
