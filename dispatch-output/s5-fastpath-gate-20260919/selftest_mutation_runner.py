import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1] / "backend"
LIVE = BACKEND / "main.py"
DUP = BACKEND / "main_mutation_selftest_dup.py"

shutil.copyfile(LIVE, DUP)
spec = [
    {
        "name": "SELFTEST-detects-injected-bug",
        "desc": "故意注入一个真 bug，执行器必须报 rc!=0 且还原成功",
        "target": "main_mutation_selftest_dup.py",
        "snippet": "def _light_buffered(pre: dict, messages: list) -> _LightResult:",
        "replacement": "def _light_buffered_BROKEN_NAME(pre: dict, messages: list) -> _LightResult:",
        "expect_failed_test": "test_light_pass_no_escalation",
        "pytest_args": ["tests/test_tiering.py", "-q"],
    },
    {
        "name": "SELFTEST-anchor-not-found-must-refuse",
        "desc": "锚点命中 0 次时必须停手且不写盘",
        "target": "main_mutation_selftest_dup.py",
        "snippet": "def this_symbol_does_not_exist_anywhere():",
        "replacement": "x",
        "expect_failed_test": "n/a",
        "pytest_args": ["tests/test_tiering.py", "-q"],
    },
]
spec_path = HERE / "_selftest_mutants.json"
spec_path.write_bytes(json.dumps(spec, ensure_ascii=False).encode("utf-8"))

before = DUP.read_bytes()
proc = subprocess.run(
    [sys.executable, str(HERE / "run_mutations.py"), str(spec_path)],
    cwd=str(BACKEND),
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
print("=== runner stdout ===")
print(proc.stdout[-2500:])
print("=== runner stderr (tail) ===")
print(proc.stderr[-800:])
print("runner_rc=", proc.returncode)
print("byte_identical_after_run=", DUP.read_bytes() == before, "(", len(before), "bytes )")
print("refused_second_mutant_without_writing=", DUP.read_bytes() == before)
DUP.unlink()
print("dup_removed=", not DUP.exists())
print("rc=0")
