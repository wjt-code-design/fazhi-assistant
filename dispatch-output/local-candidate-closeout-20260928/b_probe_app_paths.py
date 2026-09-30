"""B 档应用路径驱动：主动跑两条真实链路，把「静态 0 命中」换成「运行时调用次数」。

  qa     = rag_chain 装载（本地 BGE 加载）→ retrieval.retrieve_for_test（查询嵌入 + Chroma 检索）
  upload = knowledge_service 校验/解析上传 → add_text（切片 + 批量嵌入 + 写副本库）

两条路径都走应用自己的模块入口，不经 HTTP 鉴权面（上传/限流的 HTTP 面由测试场覆盖）。
所有可写对象先指向临时目录再 import 任何后端模块：数据库、配额库、Chroma 都是副本或空目录。
生成模型不调用；LLM 端点指向不可用地址；嵌入走本地 provider。
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

# B_PROBE_EVIDENCE_DIR 只搬读数落点（PROBE_OUT 由它派生）；默认仍写历史目录。
EVIDENCE = Path(
    os.environ.get("B_PROBE_EVIDENCE_DIR")
    or "C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/local-candidate-closeout-20260928"
)

which = (sys.argv[1] if len(sys.argv) > 1 else "both").lower()
tree = Path(
    sys.argv[2] if len(sys.argv) > 2 else r"C:/Users/33393/.codex/worktrees/local-candidate-closeout/ai-legal-helper"
)
backend = tree / "backend"
if not backend.is_dir():
    print(f"FATAL: 树里没有 backend/ -> {backend}")
    raise SystemExit(2)

stamp = time.strftime("%Y%m%d-%H%M%S")
work = Path(os.environ.get("TEMP", r"C:/Users/33393/AppData/Local/Temp")) / f"b-probe-app-{stamp}"
(work / "iso").mkdir(parents=True, exist_ok=True)

os.environ.update(
    {
        "JWT_SECRET": "test-jwt-secret-for-ci-only",
        "LLM_API_KEY": "test-key-not-for-real-calls",
        "LLM_BASE_URL": "https://test.invalid/v1",
        "EMBEDDING_PROVIDER": "local",
        "RERANK_ENABLED": "false",
        "EMBEDDING_QUOTA_TOTAL": "0",
        "RERANK_QUOTA_TOTAL": "0",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "LANGCHAIN_TRACING_V2": "false",
        "LANGSMITH_TRACING": "false",
        "DATABASE_URL": "sqlite:///" + str(work / "iso" / "app.db").replace("\\", "/"),
        "QUOTA_DB": str(work / "iso" / "quota.db"),
        "CHROMA_DIR": str(work / "iso" / "chroma"),
        "PROBE_OUT": str(EVIDENCE / f"b-probe-readings-app-{stamp}.json"),
        "PROBE_CAND": str(tree),
    }
)

import b_runtime_probe as P  # noqa: E402  （同目录，PYTHONPATH 指过来）

P.install()  # 关键顺序：先装仪器，再让应用自己 import —— 这样 NEVER-IMPORTED 才是应用的事实
sys.path.insert(0, str(backend))

results: dict[str, object] = {}


def _delta_marker() -> dict[str, int]:
    return {tid: rec["count"] for tid, rec in P.STATE["targets"].items()}


def run_qa() -> None:
    before = _delta_marker()
    import rag_chain  # noqa: F401  装载嵌入与向量库（本地 BGE 在此加载）
    import retrieval

    hits = retrieval.retrieve_for_test("劳动法第四十四条加班工资怎么算", k=3)
    results["qa"] = {
        "retrieved": len(hits),
        "top_source": (hits[0].get("source") if hits else None),
        "chroma_dir": rag_chain.CHROMA_DIR,
        "collection": rag_chain.COLLECTION_NAME,
        "embedding_class": type(rag_chain.embeddings._inner).__module__
        + "."
        + type(rag_chain.embeddings._inner).__name__,
    }
    results["qa_delta"] = {tid: _delta_marker()[tid] - before[tid] for tid in before}


def run_upload() -> None:
    before = _delta_marker()
    import knowledge_service as ks

    text = "第一条 为了保障劳动者合法权益，制定本法。\n\n第二条 在中华人民共和国境内的企业适用本法。"
    kind, parsed = ks.parse_upload_or_raise("probe-law.txt", text.encode("utf-8"))
    written = ks.add_text(
        parsed, source="探针法.txt", origin="upload", file_hash_value=ks.file_hash(text.encode("utf-8"))
    )
    results["upload"] = {
        "kind": kind,
        "parsed_chars": len(parsed),
        "chunks_written": written,
        "chroma_dir": ks.CHROMA_DIR,
    }
    results["upload_delta"] = {tid: _delta_marker()[tid] - before[tid] for tid in before}


def main() -> int:
    if not work.exists():
        (work / "iso").mkdir(parents=True, exist_ok=True)
    steps = ["qa", "upload"] if which == "both" else [which]
    failures: list[str] = []
    for step in steps:
        t0 = time.time()
        try:
            globals()[f"run_{step}"]()
        except BaseException as exc:
            failures.append(f"{step}: {type(exc).__name__}: {str(exc)[:200]}")
            (work / f"trace-{step}.txt").write_text(traceback.format_exc(), encoding="utf-8", newline="\n")
            print(f"[{step}] FAILED {type(exc).__name__}: {str(exc)[:200]}  (trace -> work/trace-{step}.txt)")
        print(f"[{step}] {round(time.time() - t0, 1)}s")

    P._apply_pending()
    P.sweep_aliases()
    payload = P.dump(
        "app-paths",
        extra={
            "which": which,
            "results": results,
            "failures": failures,
            "workdir": str(work),
            "env_isolation": {
                k: os.environ[k]
                for k in (
                    "DATABASE_URL",
                    "QUOTA_DB",
                    "CHROMA_DIR",
                    "LLM_BASE_URL",
                    "EMBEDDING_PROVIDER",
                    "RERANK_ENABLED",
                )
            },
        },
    )
    print("\n=== 逐目标运行时读数（应用路径） ===")
    for r in payload["targets"]:
        print(
            f"  {r['id']} {r['verdict']:16s} count={r['count']:4d} dry={r['dry_runs']:3d} "
            f"patched_at={r['patched_at'][:58]}"
        )
        for caller, cnt in sorted(r["callers"].items(), key=lambda kv: -kv[1])[:3]:
            print(f"        x{cnt:<4d} from {caller}")
        for sample in r["arg_samples"][:2]:
            print(f"        arg {sample[:110]}")
        if r["trust_remote_code_values"]:
            print(f"        trust_remote_code 取值 = {sorted(set(r['trust_remote_code_values']))}")
    print(f"\n=== 外联事件（{payload['net_event_kinds']} 类 / {payload['net_event_total']} 次） ===")
    for key, cnt in list(payload["net_events"].items())[:20]:
        print(f"  {cnt:5d}  {key[:150]}")
    print("\n=== 路径结果 ===")
    print(
        json.dumps(
            {k: results[k] for k in sorted(results) if k != "targets"}, ensure_ascii=False, indent=2, sort_keys=True
        )[:2500]
    )
    if failures:
        print("\nAPP-PATH FAIL:", *failures, sep="\n  - ")
        return 1
    print("\nAPP-PATH OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        shutil.rmtree(str(work), ignore_errors=True)
