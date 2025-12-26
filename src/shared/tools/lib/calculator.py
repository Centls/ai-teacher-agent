from ..registry import ToolRegistry

def calculator(expression: str) -> str:
    try:
        return str(eval(expression))
    except:
        return "Error"

ToolRegistry.register("calculator", calculator, allowed_roles=["*"])
