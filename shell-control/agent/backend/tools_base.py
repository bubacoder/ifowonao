from typing import Optional, Callable, Tuple, List
import inspect

# A decorator for marking methods as tools
def tool(name: str, formatter_function: Optional[str] = None) -> Callable:
    def decorator(func: Callable) -> Callable:
        func._is_tool = True  # Mark the function as a tool
        func._tool_name = name  # Set the name of the tool
        func._formatter_function = formatter_function  # Optional formatter function
        return func
    return decorator


class ToolsBase:
    def __init__(self, settings: Optional[dict] = None):
        self.settings = settings if settings is not None else {}
        self.toolset = {}
        self.fill_toolset()

    def fill_toolset(self):
        # Dynamically populate the toolset by inspecting annotated methods
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

                docstring = inspect.getdoc(method)
                if not docstring:
                    raise ValueError(f"No docstring found for tool '{method._tool_name}'")

                # Use the `name` as the key and store its metadata
                self.toolset[method._tool_name] = {
                    "function": method,
                    "formatter_function": formatter_callable,
                    "docstring": docstring
                }

    def get_tool(self, name: str) -> Tuple[Optional[Callable], Optional[Callable]]:
        tool = self.toolset.get(name)
        if not tool: 
            return None, None

        function = tool.get("function")
        formatter_function = tool.get("formatter_function", None)
        return function, formatter_function

    def get_tool_names(self) -> List[str]:
        return self.toolset.keys()

    def get_tool_definitions(self) -> str:
        definitions: str = ""
        for tool_name in self.toolset:
            tool = self.toolset[tool_name]
            definitions += f"   - Name: \"{tool_name}\"\n"
            docstring = tool["docstring"]
            lines = docstring.split("\n")
            for line in lines:
                definitions += f"     {line}\n"
            definitions += "\n"
        return definitions.rstrip()
