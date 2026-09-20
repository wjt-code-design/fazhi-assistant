"""票 C 前置取证 P1–P9 的读数落盘（不 import .env 内容，只读已加载的 settings 生效值）。

为什么要这个脚本：Owner 纪律「不碰 .env」，但 §6-⑦ 要求"真实配置下"的读数 ⇒
用 `settings` 的**已加载生效值**回答，而不是 grep .env 的原文。
"""

import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
BACKEND = HERE.parents[1] / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from dotenv import load_dotenv

load_dotenv(BACKEND / ".env")

from llm_registry import registry
from settings import settings

readings = {
    "roles_configured": sorted(
        {(e.modality, e.tier) for e in registry._entries.values()}
    ),
    "has_role_text_light": registry.has_role("text", "light"),
    "has_role_text_flag": registry.has_role("text", "flag"),
    "feature_router_effective": settings.feature_router,
    "agent_enabled_effective": settings.agent_enabled,
    "fast_path_law_version_check_effective": settings.fast_path_law_version_check,
    "law_version_tripwire_check_effective": settings.law_version_tripwire_check,
}

p = subprocess.run(
    [sys.executable, "-c", "import main; print(main.__file__)"],
    cwd=BACKEND,
    capture_output=True,
    text=True,
    check=False,
)
readings["import_main_rc"] = p.returncode
print(json.dumps(readings, ensure_ascii=False, indent=1))
(HERE / "00-pre-flight-readings.json").write_text(
    json.dumps(readings, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
)
