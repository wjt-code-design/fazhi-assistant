"""票 J 变异执行器（R2 编排：唯一 basetemp，逐变异一次调用）。

编排逻辑**一个字都不另写**：直接复用 `run_mutations_ticket_h2`（它内部又复用
`run_mutations_full` 的 `run_suite` / `suite_stats` / `failed_set` / 分母比对），
只换变异表与 `PYTEST_EXTRA`。

变异表对准票 J 新加的**每个语义点**（不是对准某一行）：

  J-M1  写闸少 `not multi_bad`        —— 多选漏答会进缓存
  J-M2  写闸少 `_cache_write_ok`      —— study_aid 的库外引用会进缓存
  J-M3  写闸少 `not res.degraded`     —— **预期是 SURVIVED**：该条件与 `verdict == "pass"` 冗余
                                         （`degraded` 只在 verdict != "pass" 的那一支点亮）。
                                         它的价值是**归因**而非拦截 ⇒ 由 J-M4/J-M5 负责杀。
  J-M4  account 日志少 `degraded=`    —— 独立信号落不了盘
  J-M5  降级点少 `degraded=True`      —— 信号永不点亮

用法：backend/venv/Scripts/python.exe dispatch-output/hij-j-20260920/run_mutations_ticket_j.py <副本树> <R2 根目录> <变异名|baseline> [基线 xml 出处]
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
# ⚠️ 编排器在**票 H 的证据目录**里（跨目录复用判据实现，而不是抄第二份）⇒ 两个目录都要进 path。
# 第一版只加了 HERE，结果 `ModuleNotFoundError` 让 baseline 与 5 个变异**瞬间全灭**
# （每组 stdout 只有 traceback、没有 verdict.json）—— 「跑完了」不等于「跑出了读数」，
# 所以每个跑次必须回读 verdict.json，而不是看进程退出。
sys.path.insert(0, str(HERE.parent / "hij-h-20260920"))

import run_mutations_ticket_h2 as base

base.MUTANTS = {
    "J-M1_multibad_cond_removed": (
        "                    and not multi_bad\n                    and not res.law_version_hit\n                ):",
        "                    and not res.law_version_hit\n                ):",
    ),
    "J-M2_cache_write_ok_removed": (
        "                    and not res.degraded\n                    and _cache_write_ok(pre, answer)\n",
        "                    and not res.degraded\n",
    ),
    "J-M3_degraded_cond_removed": (
        "                    and not res.degraded\n                    and _cache_write_ok(pre, answer)\n",
        "                    and _cache_write_ok(pre, answer)\n",
    ),
    "J-M4_log_degraded_removed": (
        "                    degraded=res.degraded,\n",
        "",
    ),
    "J-M5_signal_never_set": (
        "                degraded=True,\n",
        "",
    ),
}

if __name__ == "__main__":
    sys.exit(base.main())
