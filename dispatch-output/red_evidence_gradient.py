# P2-1 red→green 梯度复现脚本（task4 响应：red 证据补齐）
# 基线：worktree @ b7ab04f（6e43042 父代 = Gate-4 修复前）；tests 固定为 HEAD 版
# 沿提交链顺次 checkout backend 被测代码，记录每级 failed 数与失败用例 → 证明"先红后绿"
import subprocess
import sys
from pathlib import Path

VENV_PY = r"C:\Users\33393\Desktop\ai-legal-helper\backend\venv\Scripts\python.exe"
WT = Path(r"C:\Users\33393\AppData\Local\Temp\wt-red\6e43042")
OUT = Path(r"C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\red-evidence-runs")
OUT.mkdir(parents=True, exist_ok=True)

STEPS = [
    ("b7ab04f-baseline", "b7ab04f"),
    ("6e43042", "6e43042"),
    ("03a2f14", "03a2f14"),
    ("613ecb3", "613ecb3"),
    ("ee939bc", "ee939bc"),
    ("71e5f23", "71e5f23"),
    ("88b7937-head", "88b7937"),
]

TESTS = "tests/test_agent_resume.py tests/test_agent_controller.py tests/test_tool_gateway.py tests/test_agent_runtime.py tests/test_agent_verifier.py"

SRC_TESTS = Path(r"C:\Users\33393\Desktop\ai-legal-helper\backend\tests")
SRC_ENV = Path(r"C:\Users\33393\Desktop\ai-legal-helper\backend\.env")
TEST_FILES = ["test_agent_resume.py", "test_agent_controller.py", "test_tool_gateway.py", "test_agent_runtime.py", "test_agent_verifier.py", "conftest.py", "__init__.py", "_fake_embeddings.py"]

# 1) .env 复制进 worktree（gitignore 不随 checkout；仅本机临时，不提交）
import shutil
shutil.copy2(SRC_ENV, WT / "backend" / ".env")

def overlay_head_tests():
    for f in TEST_FILES:
        shutil.copy2(SRC_TESTS / f, WT / "backend" / "tests" / f)

for name, commit in STEPS:
    if commit:
        subprocess.run(
            ["git", "-C", str(WT), "checkout", "-q", commit, "--", "backend"],
            check=True,
        )
        overlay_head_tests()  # checkout backend 会覆盖 backend/tests，需重新覆盖回 HEAD 测试
    run = subprocess.run(
        [VENV_PY, "-m", "pytest", *TESTS.split(), "-q", "--tb=line"],
        cwd=str(WT / "backend"),
        capture_output=True,
        text=True,
        timeout=600,
    )
    log = run.stdout + run.stderr
    (OUT / f"{name}.log").write_text(log, encoding="utf-8")
    last = [l for l in log.splitlines() if l.strip()][-1] if log.splitlines() else "(no output)"
    print(f"{name}: exit={run.returncode} | {last}")
    print(f"  -> {OUT / name}.log")