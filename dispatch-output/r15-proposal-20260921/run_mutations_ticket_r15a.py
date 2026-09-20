"""票 R15-A 变异执行器：复用 R2 编排（唯一 basetemp + 分母比对 + junit 差分）。

编排逻辑不重写：复用 `run_mutations_ticket_h2`（内含 run_mutations_full 的 run_suite/判定），
它已支持**每个变异体各自指定目标文件**（三元组首元素是相对路径）——R15-A 的变异全在
`backend/agent/limitation_calc.py`（票 H/J 那批在 main.py，靠这个扩展兼容）。

变异表对准 R15-A 的两个语义点各两条：
  R15A-M1 日期识别退回"只认年月日"（ISO/斜杠失效）      ⇒ 应被 R15-5 用例杀
  R15A-M2 去掉数字边界（(?<!\d)/(?!\d)）                ⇒ 应被"编号串不得误读"契约杀
  R15A-M3 恢复"整段劳动关键词即放过"（退回 R15-4 缺陷） ⇒ 应被混合句段用例杀
  R15A-M4 分水岭比较取反                                ⇒ 应被多腿杀（含控制腿）
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "hij-h-20260920"))

import run_mutations_ticket_h2 as base  # noqa: E402

TARGET = "backend/agent/limitation_calc.py"

base.MUTANTS = {
    "R15A-M1_date_iso_removed": (
        TARGET,
        '_DATE_RE = re.compile(r"(?:(\\d{4})年(\\d{1,2})月(\\d{1,2})日|(?<!\\d)(\\d{4})[-/](\\d{1,2})[-/](\\d{1,2})(?!\\d))")',
        '_DATE_RE = re.compile(r"(\\d{4})年(\\d{1,2})月(\\d{1,2})日")',
    ),
    "R15A-M2_boundary_removed": (
        TARGET,
        "(?<!\\d)(\\d{4})[-/](\\d{1,2})[-/](\\d{1,2})(?!\\d)",
        "(\\d{4})[-/](\\d{1,2})[-/](\\d{1,2})",
    ),
    "R15A-M3_whole_text_labor_restored": (
        TARGET,
        '    for segment in re.split(r"[。！？；\\n]", text):',
        '    if any(keyword in text for keyword in _LABOR_KEYWORDS):\n'
        "        return False\n"
        '    for segment in re.split(r"[。！？；\\n]", text):',
    ),
    "R15A-M4_watershed_inverted": (
        TARGET,
        "if (dates[0] < CIVIL_CODE_EFFECTIVE) != (law_as_of < CIVIL_CODE_EFFECTIVE):",
        "if (dates[0] < CIVIL_CODE_EFFECTIVE) == (law_as_of < CIVIL_CODE_EFFECTIVE):",
    ),
}

if __name__ == "__main__":
    sys.exit(base.main())
