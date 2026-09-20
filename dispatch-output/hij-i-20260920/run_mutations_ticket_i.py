"""票 I 变异执行器（复用 R2 编排：唯一 basetemp + 分母比对 + junit 差分）。

编排逻辑一个字不另写：直接复用 `run_mutations_ticket_h2`（它内部又复用
`run_mutations_full` 的 `run_suite` / `suite_stats` / `failed_set`）。

变异表对准票 I 的**每个语义点**（不是对准某一行）：

  I-M1  回退整体失效（`return _valid_docs(..., only=rows)` → `return []`）
  I-M2  源名过滤反了（`== sk` → `!= sk`）—— 同时验证"回退不是把同条号别的法条一起端出来"
  I-M3  版本护栏永不触发（判据行 → `if False:`）
  I-M4  分水岭比较取反（`!=` → `==`）—— 预期 2 条红（先红腿 + 同侧控制腿）
  I-M5  脏值当成已知基准日（`except ValueError: basis = None` → 一个真日期）

用法：backend/venv/Scripts/python.exe dispatch-output/hij-i-20260920/run_mutations_ticket_i.py <副本树> <R2 根目录> <变异名|baseline> [基线 xml 出处]
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
# ⚠️ 编排器在**票 H 的证据目录**里（跨目录复用判据实现，别抄第二份）⇒ 两个目录都要进 path。
sys.path.insert(0, str(HERE.parent / "hij-h-20260920"))

import run_mutations_ticket_h2 as base

base.MUTANTS = {
    # ⚠️ 这两个的锚点在 `backend/retrieval.py` ⇒ 必须用**三元组**形式（首个元素是目标文件）。
    # 第一版按二元组写，共用执行器只在 `main.py` 里找锚点 ⇒ 报 `ANCHOR-NOT-UNIQUE count=0`，
    # **看起来像 SURVIVED，其实是"根本没执行"**（判据要求"不是 KILLED 就是坏消息"）。
    "I-M1_fallback_returns_empty": (
        "backend/retrieval.py",
        "    return _valid_docs(data, cutoff, only=rows)\n",
        "    return []\n",
    ),
    "I-M2_source_filter_inverted": (
        "backend/retrieval.py",
        'if _source_key(str((m or {}).get("source", "") or "")) == sk',
        'if _source_key(str((m or {}).get("source", "") or "")) != sk',
    ),
    # 以下三个的锚点在 `backend/main.py`（二元组即可，兼容票 H/J 的写法）
    "I-M3_version_guard_disabled": (
        "        if basis is not None and (basis >= _CIVIL_WATERSHED) != (law_as_of >= _CIVIL_WATERSHED):",
        "        if False:",
    ),
    "I-M4_watershed_compare_inverted": (
        "        if basis is not None and (basis >= _CIVIL_WATERSHED) != (law_as_of >= _CIVIL_WATERSHED):",
        "        if basis is not None and (basis >= _CIVIL_WATERSHED) == (law_as_of >= _CIVIL_WATERSHED):",
    ),
    "I-M5_dirty_value_blocks": (
        "            basis = None  # 脏值 ⇒ 不拦（保持旧行为）",
        "            basis = _CIVIL_WATERSHED  # 变异：脏值当成已知基准日",
    ),
}

if __name__ == "__main__":
    sys.exit(base.main())
