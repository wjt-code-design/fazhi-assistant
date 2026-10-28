"""Explicit contracts for the bounded legal-research agent."""

from .schemas import AgentBudgets, AgentStatus, LegalAgentState, ToolCallDecision
from .state_machine import BudgetExceeded, DuplicateAction, InvalidTransition, register_action, transition

__all__ = [
    "AgentBudgets",
    "AgentStatus",
    "BudgetExceeded",
    "DuplicateAction",
    "InvalidTransition",
    "LegalAgentState",
    "ToolCallDecision",
    "register_action",
    "transition",
]
