"""Typed read-only clarification tool."""

from .contracts import AskUserInput, AskUserOutput, ToolContext


def ask_user(_context: ToolContext, tool_input: AskUserInput) -> AskUserOutput:
    return AskUserOutput(statement="需要用户补充信息。", question=tool_input.question)
