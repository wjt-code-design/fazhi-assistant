"""T-E2 守卫：环境变量与运维脚本的固定目标分歧时必须拒绝执行。

红绿性质（watch-it-fail）：
- 把 `assert_matches` 的 raise 删掉 ⇒ 第 3 条红；把里面的 `os.path.abspath` 去掉 ⇒ 第 2 条红
  （那条测的是"同一路径的不同写法不该被误判成分歧"，用的是真不同的字面量，不是自己造自己比）；
- 把某个脚本 `__main__` 前的 `_check_env_contract()` 调用删掉、或把它挪进 `main()` 里
  ⇒ 该脚本的接线断言红（接线用源码判定，不 import 脚本本体，见 WIRED 注释）；
- 把 `backup_data` 那句 `env_name="QUOTA_DB"` 删掉（退回默认 CHROMA_DIR）⇒ 末条 QUOTA_DB 接线断言红。
  那道门挡的是容器侧形状：compose 注入 `QUOTA_DB=/data/quota_used.sqlite`，而脚本按 `backend/data/`
  固定取源 ⇒ 只判 CHROMA_DIR 时三件附属全部"源不存在⇒跳过"，却照样打印"备份完成"。
"""

import os
import re
from pathlib import Path

import pytest

from scripts import chroma_dir_guard

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def test_guard_is_silent_when_env_unset(monkeypatch):
    monkeypatch.delenv("CHROMA_DIR", raising=False)
    chroma_dir_guard.assert_matches(str(Path("backend") / "chroma_db"), "t")  # 不抛即通过


def test_guard_accepts_equivalent_spellings(monkeypatch, tmp_path):
    """同一路径的不同写法（末尾分隔符 / 正斜杠混写）不算分歧。

    两侧字面量**必须真的不同**，否则这条就是在测我自己造的字符串。
    """
    real = tmp_path / "chroma_db"
    monkeypatch.setenv("CHROMA_DIR", str(real))  # 本机原生写法
    spelled = str(real).replace("\\", "/") + os.sep  # 换斜杠方向 + 末尾多一个分隔符
    assert spelled != str(real), "构造得不够不同，这条测不出归一化"
    chroma_dir_guard.assert_matches(spelled, "t")


def test_guard_refuses_divergent_env(monkeypatch, tmp_path):
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "test_lane_store"))
    with pytest.raises(SystemExit) as ei:
        chroma_dir_guard.assert_matches(str(tmp_path / "real_prod_store"), "backup_data")
    msg = str(ei.value)
    assert "拒绝执行" in msg and "backup_data" in msg, f"报错得说清是谁拒的、为什么：{msg}"


# 接线判据：三个脚本都必须在**自己**的模块里定义 _check_env_contract 并在 __main__ 路径上调它。
# 用源码判而不是 import 模块：这些脚本 import 期拉 chromadb/嵌入依赖（快测车道不该付这个钱）。
WIRED = ["backup_data.py", "rebuild_embeddings.py", "switch_embedding.py"]


@pytest.mark.parametrize("fname", WIRED)
def test_script_is_wired_to_the_guard(fname):
    src = (SCRIPTS / fname).read_text(encoding="utf-8")
    assert "_check_env_contract()" in src, f"{fname} 没接守卫：CHROMA_DIR 分歧时会静默作用在错库上"
    assert re.search(r"if __name__ == .__main__.:\s*\n\s*_check_env_contract\(\)", src), (
        f"{fname} 的守卫不在 __main__ 路径上（放进 main() 会让 test_backup_data 这类直调 main 的用例被拒）"
    )
    assert "assert_matches(" in src, f"{fname} 的 _check_env_contract 没真正调用守卫"


def test_backup_data_wires_the_guard_for_quota_db_too():
    """Q1 判据的接线面：`backup_data` 还必须拿 **QUOTA_DB** 比一遍，分歧即拒绝执行。

    期望值来自票面判据（"`QUOTA_DB` 分歧即拒绝"），不是从实现里抄的。
    `[^()]*` 是刻意的：它不允许跨过一次调用边界，于是"另一支 assert_matches 传了 env_name"
    冒充"QUOTA_DB 这一支传了"挡不住——正则必须能区分"传了"与"没传"。
    """
    src = (SCRIPTS / "backup_data.py").read_text(encoding="utf-8")
    assert re.search(r'assert_matches\([^()]*env_name="QUOTA_DB"[^()]*\)', src), (
        'backup_data 的守卫没带 env_name="QUOTA_DB" ⇒ 容器里 QUOTA_DB 指向卷内路径时，'
        '三件附属会全部按 backend/data/ 找不到源而跳过，脚本仍打印"备份完成"'
    )
