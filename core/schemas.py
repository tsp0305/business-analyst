from pydantic import BaseModel, Field
from typing import Optional, Any

class Action(BaseModel):
    pass

class ToolCall(Action):
    name: str
    args: dict
    thought: str

class AskUser(Action):
    question: str
    options: Optional[list[str]] = None

class FinalAnswer(Action):
    payload: Any
