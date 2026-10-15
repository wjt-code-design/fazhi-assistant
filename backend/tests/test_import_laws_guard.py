"""B-45：`import_laws` 的 CLI 前置守卫（三段闸的第一段）。

前三条腿跑**子进程**，因为守卫按在册判例只挂在 `if __name__ == "__main__"` 上
（判例见 `chroma_dir_guard` 模块 docstring；同族 `backup_data.py` 的 `_check_env_contract` 同位）。
`tests/conftest.py` 会把 `CHROMA_DIR` 无条件指向进程临时库 ⇒ 守卫一旦进 `main()` 或 import 期，
本仓直接调 `main()` 的用例（`test_import_laws_preflight.py`）会被它钉红。子进程因此是唯一真实测法。

除 validate-only 那条外，输入文件**故意不存在**：这样"守卫没拦"的读数只能是
`未找到导入文件`，绝不可能真去写任何库。判据按**消息**分，不按 rc —— 两条路径 rc 都可能是 1。
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
PROD = str(BACKEND / "chroma_db")

# 要跑的 argv 走环境变量传，不走 `-c` 的 argv：`python -c` 下 sys.argv[0] 的形状随版本变，
# 用下标取参数会造出「子进程读到一只不存在的路径」这种看着像红、其实是尺子坏的读数。
CHILD = """
import os, runpy, sys
sys.argv = ["import_laws", *os.environ["FZ_ARGV"].split("|")]
try:
    runpy.run_module("scripts.import_laws", run_name="__main__")
except SystemExit:
    # 必须 re-raise：SystemExit 的 message（那条"拒绝执行"）是解释器在退出时打到 stderr 的，
    # 自己吞掉就等于把判据要读的消息删了 —— 我第一版就在这儿拿到了假的"没拦"。
    print("RAG_CHAIN_IMPORTED" if "rag_chain" in sys.modules else "NO_RAG_CHAIN")
    raise
print("RAG_CHAIN_IMPORTED" if "rag_chain" in sys.modules else "NO_RAG_CHAIN")
"""


def run_cli(argv: list[str], chroma_dir: str | None) -> str:
    env = dict(os.environ)
    env.update(
        {
            "JWT_SECRET": "test-jwt-secret-for-ci-only",
            "LLM_API_KEY": "test-key-not-for-real-calls",
            "LLM_BASE_URL": "http://127.0.0.1:9/v1",
            "EMBEDDING_PROVIDER": "local",
            "RERANK_ENABLED": "false",
            "HF_HUB_OFFLINE": "1",
            "PYTEST_ADDOPTS": "",
            "PYTHONPATH": str(BACKEND),
            "PYTHONDONTWRITEBYTECODE": "1",
            "FZ_ARGV": "|".join(argv),
        }
    )
    env.pop("CHROMA_DIR", None)
    if chroma_dir is not None:
        env["CHROMA_DIR"] = chroma_dir
    proc = subprocess.run(
        [sys.executable, "-B", "-c", CHILD],
        cwd=str(BACKEND),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
    )
    return proc.stdout + proc.stderr


def good_file(tmp_path: Path) -> str:
    path = tmp_path / "laws.json"
    path.write_text(
        json.dumps(
            [
                {
                    "title": "合成测试法",
                    "article_number": "第一条",
                    "content": "这是一条合成演练条文，用于校验 CLI 闸的读取顺序。",
                    "status": "未验证",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return str(path)


def test_write_modes_refuse_divergent_chroma_dir_before_touching_the_input(tmp_path):
    """默认模式（实写）与 --dry-run（读库）都必须在**读输入之前**拒绝。"""
    elsewhere = tmp_path / "elsewhere-chroma"
    missing = str(tmp_path / "definitely-missing.json")
    for mode in ([], ["--dry-run"]):
        out = run_cli([*mode, "--input", missing], str(elsewhere))
        assert "拒绝执行" in out, f"模式 {mode or '默认(实写)'} 未拦下分歧的 CHROMA_DIR：{out}"
        assert "未找到导入文件" not in out, f"守卫没跑在读取之前（先碰了输入文件）：{out}"
    assert not elsewhere.exists(), "拒绝之前就已经建了库目录"


def test_validate_only_is_exempt_and_never_loads_the_embedding_model(tmp_path):
    """validate-only 结构上不写库 ⇒ 放行；同时钉住它不 import rag_chain。

    这条腿兼管一件事：`test_import_laws_validation.py` 用「把 CHROMA_DIR 指到不存在的目录」
    来证明 validate-only 不碰库。守卫若拦下那种形状，就是守卫自己把测试钉红，本条会先响。
    """
    elsewhere = tmp_path / "should-not-exist"
    out = run_cli(["--validate-only", "--input", good_file(tmp_path)], str(elsewhere))
    assert "拒绝执行" not in out, out
    assert "文件校验通过" in out, out
    assert "NO_RAG_CHAIN" in out, "validate-only 期加载了嵌入模型/连接了知识库：" + out
    assert not elsewhere.exists()


def test_convergent_env_and_unset_env_are_both_allowed(tmp_path):
    """一致与 unset 都放行 —— 缺这条的话守卫其实是「env 一旦存在就红」，会拦死正常用法。"""
    missing = str(tmp_path / "definitely-missing.json")
    for chroma_dir in (None, PROD):
        out = run_cli(["--input", missing], chroma_dir)
        assert "拒绝执行" not in out, f"CHROMA_DIR={chroma_dir} 本应放行：{out}"
        assert "未找到导入文件" in out, f"没走到本该的下一步（读输入）：{out}"


def test_guard_is_not_wired_into_main_so_direct_main_calls_still_work(monkeypatch, tmp_path):
    """判例的反面：`main()` 里不许有守卫。

    把 `CHROMA_DIR` 设成分歧值，再按 preflight 用例的做法 monkeypatch `sys.argv` 直接调 `main()`：
    它必须走到「读输入」那一步（rc=1 的原因是缺文件，不是缺授权）。
    """
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "elsewhere"))
    spec = importlib.util.spec_from_file_location("_il_guard_probe", BACKEND / "scripts" / "import_laws.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    cwd = os.getcwd()
    try:
        spec.loader.exec_module(mod)  # 模块期会 os.chdir(BACKEND) ⇒ 必须还原
        monkeypatch.setattr(sys, "argv", ["import_laws.py", "--input", str(tmp_path / "missing.json")])
        with pytest.raises(SystemExit) as exc:
            mod.main()
    finally:
        os.chdir(cwd)
    assert exc.value.code == 1, "main() 应只走到「未找到导入文件」那条 rc=1，不能被守卫拦成别的形状"
