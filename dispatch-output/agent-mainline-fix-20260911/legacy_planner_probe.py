"""Test-only restoration of the exact pre-fix decide method, without editing production files."""

import ast
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def restore_legacy_planner(monkeypatch):
    import agent.runtime as runtime

    snapshot = Path(__file__).with_name("backend__agent__runtime.py.before")
    tree = ast.parse(snapshot.read_text(encoding="utf-8"))
    adapter = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "LLMPlannerAdapter")
    decide = next(node for node in adapter.body if isinstance(node, ast.FunctionDef) and node.name == "decide")
    namespace = {}
    exec(compile(ast.Module(body=[decide], type_ignores=[]), str(snapshot), "exec"), runtime.__dict__, namespace)
    monkeypatch.setattr(runtime.LLMPlannerAdapter, "decide", namespace["decide"])
