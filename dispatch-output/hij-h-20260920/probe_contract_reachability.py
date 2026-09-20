"""票 H 可达性读数：**真实配置**下合同分支入口到底可不可达（§0 判据第 2 条）。

为什么需要它：登记表 E5 的 `traffic` 一直写着「静态可达（执行未证）」，而票 H 的两道闸都长在
那一段上 ⇒ 如果那一段今天根本进不去，「已受保护」这句话就只能打折。本脚本不桩任何判定函数，
只用**真实**的 `domain_rules.is_contract_review` / `build_contract_data` / `main._cacheable` /
`main._cache_key` 读一遍，并顺手读**真实**的 `registry.is_unavailable(default_key())`
（它就是 `degraded` 的取值来源 ⇒ 决定 E15 那一帧今天会不会真的被走到）。

只读：不写库、不调模型、不动 .env。BGE 走本地缓存（先置两个 offline 开关，避免联网）。

用法：backend/venv/Scripts/python.exe dispatch-output/hij-h-20260920/probe_contract_reachability.py
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

REPO = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "backend"))

from dotenv import load_dotenv

load_dotenv(REPO / "backend" / ".env")

import domain_rules as D
import main

CONTRACT = (
    "租赁合同\n"
    "第一条 甲方将位于市中心的房屋出租给乙方，租赁期限为三年，租金每月八千元。\n"
    "第二条 乙方应于每月五日前支付租金，逾期未付的，甲方有权解除合同并没收押金。\n"
    "第三条 任何情况下甲方概不负责房屋质量问题，本合同最终解释权归甲方所有。\n"
    "第四条 本合同一式两份，双方各执一份，自签字之日起生效。"
)


def main_probe() -> int:
    out: dict = {}
    out["is_contract_review_real"] = bool(D.is_contract_review(CONTRACT))
    cd = D.build_contract_data(CONTRACT)
    out["need_clarify"] = cd["need_clarify"]
    out["n_blocks"] = len(cd["blocks"])
    out["n_docs"] = len(cd["docs"])
    out["level"] = cd["level"]
    pre = {
        "intent": "legal_query",
        "image": None,
        "recent": [],
        "rewritten": CONTRACT,
        "user_text": CONTRACT,
        "sources": [
            {
                "source": d.metadata.get("source", ""),
                "article": d.metadata.get("article", ""),
            }
            for d in cd["docs"]
        ],
    }
    out["cacheable_real"] = bool(main._cacheable(pre))
    out["cache_key_not_none"] = (
        main._cache_key(pre) if main._cacheable(pre) else None
    ) is not None
    out["settings_feature_router"] = main.settings.feature_router
    out["settings_feature_multi_analyze"] = main.settings.feature_multi_analyze
    dk = main.registry.default_key()
    out["registry_default_key"] = dk
    out["registry_is_unavailable_default_key"] = bool(main.registry.is_unavailable(dk))
    out["degraded_would_be_true_today"] = out["registry_is_unavailable_default_key"]
    out["verdict_contract_branch_entered_in_real_config"] = (
        out["settings_feature_router"]
        and out["settings_feature_multi_analyze"]
        and out["is_contract_review_real"]
        and not out["need_clarify"]
        and out["cache_key_not_none"]
    )
    (OUT / "17-reachability-realconfig.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main_probe())
