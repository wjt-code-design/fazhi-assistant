"""Lazy exports for typed, read-only legal-agent tools.

Package initialization stays side-effect free so ``agent.schemas`` can import
the neutral output contracts without importing the Gateway back into itself.
"""

from __future__ import annotations

from typing import Any

_CONTRACT_EXPORTS = {
    "AskUserInput",
    "AskUserOutput",
    "ContractInput",
    "ContractOutput",
    "LookupArticleInput",
    "LookupArticleOutput",
    "RetrieveLawsInput",
    "RetrieveLawsOutput",
    "RetrieveMemoryInput",
    "RetrieveMemoryOutput",
    "ToolContext",
}
_GATEWAY_EXPORTS = {"ToolGateway", "shutdown_default_executor"}

__all__ = sorted(_CONTRACT_EXPORTS | _GATEWAY_EXPORTS | {"Observation"})


def __getattr__(name: str) -> Any:
    if name in _CONTRACT_EXPORTS:
        from . import contracts

        return getattr(contracts, name)
    if name == "Observation":
        from agent.schemas import Observation

        return Observation
    if name in _GATEWAY_EXPORTS:
        from . import gateway

        return getattr(gateway, name)
    raise AttributeError(name)
