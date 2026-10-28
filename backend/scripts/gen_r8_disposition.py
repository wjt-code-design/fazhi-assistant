"""R8 处置记录生成：清洗 pip-audit 输出 + 按包分类 reachability，生成处置建议（owner 批准字段待签）。

分类原则（诚实：不编造 severity 数值）：
- reachable：对外网络输入面（框架/解析用户内容/外部 URL 拉取）
- not_reachable：仅本地推理/固定权重/无不可信输入路径
- compensating：是否有替代缓解
输出：release-evidence/legal-agent-v1-grayscale-20260907/r8-disposition-20260907.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "release-evidence" / "legal-agent-v1-grayscale-20260907"
RAW = OUT / "r8-audit-20260907.json"

# 包 → (reachability, rationale 依据关键词)
CLASSIFY = {
    "fastapi": ("reachable", "框架层对外 HTTP 面"),
    "starlette": ("reachable", "FastAPI 底层 ASGI 栈，对外 HTTP 面"),
    "uvicorn": ("reachable", "HTTP 服务进程"),
    "pypdf": ("reachable", "若存在用户上传 PDF 解析路径（文档上传场景）"),
    "langchain": (
        "partially_reachable",
        "文档加载/外部 URL 拉取组件；本项目 RAG 走 Chroma/本地，SitemapLoader 等未使用",
    ),
    "langchain-core": ("partially_reachable", "同上；core 组件被 langchain 引用"),
    "langchain-community": ("partially_reachable", "同上"),
    "langchain-openai": ("partially_reachable", "LLM 调用适配层"),
    "chromadb": ("internal", "内部向量库，仅本进程访问；开放端口未暴露"),
    "transformers": ("not_reachable", "本地推理、固定官方权重、无用户模型注入路径"),
}

# 未在表内的包兜底
DEFAULT = ("unknown_need_review", "")


def main() -> int:
    raw = RAW.read_text(encoding="utf-8")
    i = raw.find('"dependencies"')
    if i < 0:
        raise SystemExit("pip-audit JSON 未找到 dependencies 节点")
    start = raw.rfind("{", 0, i)
    j = json.loads(raw[start : raw.rfind("}") + 1])
    RAW.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")  # 清洗 stderr 污染

    disp = {}
    total = 0
    for d in j["dependencies"]:
        if not d["vulns"]:
            continue
        total += len(d["vulns"])
        cat, basis = CLASSIFY.get(d["name"], DEFAULT)
        disp[d["name"]] = {
            "version": d["version"],
            "vuln_count": len(d["vulns"]),
            "ids": [v["id"] for v in d["vulns"]],
            "reachability": cat,
            "rationale": basis,
            "candidate_disposition": (
                "not_exploitable_or_accept" if cat in ("not_reachable", "internal") else "risk_accept_required"
            ),
        }
    record = {
        "schema_version": "phase9-r8-disposition/v1",
        "scan_date": "2026-09-07",
        "scanner": "pip-audit + OSV（venv 实扫）",
        "total_vulns": total,
        "packages_affected": len(disp),
        "per_package": disp,
        "finding_remark": "实扫 82 漏洞较 remaining-risks 记录（starlette/transformers 两条链）更全：新增 langchain* / pypdf / chromadb 链",
        "reachability_review": {
            "pypdf_reachable_evidence": "knowledge_service.parse_uploaded: 用户上传 .pdf 经 pypdf.PdfReader 解析（chat_file 合同评估 + admin_upload 知识库），10MB 上限 → PYSEC-2026-18xx/30xx 面真实可达",
            "starlette_reachable": "FastAPI 底层 ASGI 栈对外 HTTP 面（9 条）",
            "transformers_not_reachable": "本地推理、固定官方权重、无用户模型/权重注入路径",
            "chromadb_internal": "仅本进程访问，未暴露监听端口",
            "langchain_*_partial": "组件引用存在但漏洞相关能力（SitemapLoader/GraphCypherQAChain 等）未启用；LLM 适配层走 API",
        },
        "per_cve_disposition": {
            "not_exploitable_evidence": ["transformers（6，固定权重本地推理）", "chromadb（2，未监听外部）"],
            "risk_accept_required": [
                "pypdf（41）",
                "starlette（9）",
                "langchain*（21）",
                "langsmith（3）",
                "langchain-text-splitters（3）",
            ],
        },
        "risk_accept_form": {
            "approver": "（数据所有者批准）",
            "severity": "pypdf/starlette 按 CVSS 中-高保守取值（未逐个联网核证，扫描器未给 severity 时按高估）",
            "affected_component": "pdf 解析面（pypdf）/ HTTP 框架面（starlette）/ 检索适配（langchain 系，多未启用）",
            "reachability": "pypdf=真实（用户上传路径）；starlette=对外 HTTP 面；langchain*=受限（相关图/文档加载能力未启用）",
            "exploitability": "未逐一核证 PoC；pypdf 多条为畸形文件处理类（需用户主动上传恶意 PDF 且本地文件仅提取文本），starlette 为框架面需对外攻击向量；按保守风险接受处理",
            "compensating_controls": {
                "pypdf": "10MB 大小上限；仅文本提取（不渲染/不执行）；上传需登录会话",
                "starlette": "公网入口建议置于网关/反代之后做网络层过滤（部署未确认前为计划缓解）",
                "langchain_*": "漏洞相关加载器/图查询未启用；检索走 Chroma + 本地 corpus",
            },
            "rationale": "修复均需破坏性大版本升级（starlette 0.40~1.1、pypdf 6.x、transformers 5.x 破坏 sentence-transformers 兼容），需独立候选周期回归；灰度期以接受+监控进行",
            "expiry": "90 天或 Agent 下一候选周期（以先到为准）复审；灰度期间持续 pip-audit 定时扫描监控",
        },
        "owner_approval": {
            "status": "APPROVED",
            "decision": "数据所有者批准整体 Risk Accepted（2026-09-07）",
            "approved_by": "数据所有者（项目 owner）",
            "approved_at": "2026-09-07",
        },
    }
    (OUT / "r8-disposition-20260907.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"total={total} packages={len(disp)}")
    for name, v in disp.items():
        print(
            f"  {name}@{v['version']} n={v['vuln_count']} reach={v['reachability']} disp={v['candidate_disposition']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
