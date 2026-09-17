"""生成 run-13 预登记 manifest（T7）。

数据来源：candidate-manifest-20260910.json（重采的候选哈希）——不手打哈希。
用法：在仓库根运行。
    backend/venv/Scripts/python.exe dispatch-output/t2-persistence-20260910/gen_run13_preregistration.py
"""
from __future__ import annotations

import json
import pathlib
import subprocess
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).parent
PREV = pathlib.Path(r"C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t2-persistence-20260909\t7-run12-manifest.json")

RUN_NAME = "gate5-dev-run-13"
CASE_LIST = [f"C{i:02d}" for i in range(1, 11)]


def main() -> None:
    cand = json.loads((HERE / "candidate-manifest-20260910.json").read_text(encoding="utf-8"))
    prev = json.loads(PREV.read_text(encoding="utf-8"))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()

    manifest = {
        "run_id": RUN_NAME,
        "kind": "pre-registered paid run (T7) — 替代 run-12",
        "preregistered_at_utc": datetime.now(timezone.utc).isoformat(),
        "started_at_utc": None,
        "started_at_utc_note": "由 gate2_runner 在启动时写入 claim；本文件为预登记，启动前为 null",
        "git_head": head,
        "candidate_basis": "脏工作树 + 哈希锚定（T0 方法论：不 commit / 不 stash / 不 reset）",
        "candidate_files_sha256": cand["candidate_files_sha256"],
        "frozen_files_sha256": cand["frozen_files_sha256"],
        "supersedes": {
            "run": "gate2-run-12",
            "reason": "run-12 被中断，其 checkpoint 的 4 题（C01-C04）跑在 C01 修复之前的候选上；"
                      "混用会使该轮不可归因，故弃用其名、重开新 run。run-12 的 claim/checkpoint 原样保留留档。",
            "run12_recorded_cases": {"C01": "GENERATOR_FAILURE", "C02": "EVIDENCE_COVERAGE_DEFICIENT",
                                     "C03": "EVIDENCE_COVERAGE_DEFICIENT",
                                     "C04": "CLIENT_TIMEOUT(unknown_server_state)"},
        },
        "candidate_delta_vs_run12": {
            "backend/agent/controller.py": "新增改动（C01 修复：_every_issue_retrieval_attempted + 幂等转移短路）",
            "backend/tests/test_agent_chat_integration.py": "已漂移（新增 3 条 C01 回归测试）",
        },
        "model_identifiers_sanitized": {
            "source": "沿用 run-12 记录；启动前请以当前 .env / LLM_MODELS_JSON 复核",
            "from_env_LLM_MODELS_JSON": prev.get("model_identifiers_sanitized", {}).get("from_env_LLM_MODELS_JSON", []),
        },
        "service": {
            "host": prev["service"]["host"],
            "port": prev["service"]["port"],
            "agent_enabled": True,
            "agent_max_steps": prev["service"]["agent_max_steps"],
            "interpreter": prev["service"]["interpreter"],
            "workdir": prev["service"]["workdir"],
            "note": "服务当前不在运行（上一轮进程已被误杀）；启动前请按 handoff §6.3 起服务并确认 /healthz 就绪",
        },
        "runner_command": f"python scripts/gate2_runner.py --run {RUN_NAME} --all --base-url "
                          f"http://{prev['service']['host']}:{prev['service']['port']}",
        "expected_output": f"release-evidence/legal-agent-v1-complex-v1-20260907/gate2-run-{RUN_NAME}-sessions.json",
        "case_list": CASE_LIST,
        "pre_run_probe": {
            "command": f"python scripts/gate2_runner.py --run probe-c01-verify-20260910 --case C01 "
                       f"--base-url http://{prev['service']['host']}:{prev['service']['port']}",
            "pass_criteria": "errors 里不再出现 EVIDENCE_COVERAGE_DEFICIENT，且 observations 覆盖全部 4 个 issue",
            "note": "只以 EVIDENCE_COVERAGE_DEFICIENT 是否消失为准；若报 GENERATOR_FAILURE 不判定修复失败（C01 失败面非确定）",
        },
        "verification_status": {
            "offline_tests": "903 passed / 0 failed（tests/ 全树）；362 passed（agent 17 模块子集）",
            "frozen_artifacts": "16 项一致 / 4 项知情变化（见 candidate-manifest-20260910.md）",
            "paid_verification": "尚未进行（预登记前的离线验证已完成）",
        },
        "red_lines": [
            "不 commit / 不 stash / 不 reset（候选 = 脏工作树）",
            "不修改冻结物（verifier/chat_integration/state_machine/repository/prompts/gate5_judge/frozen-*/hidden-*/历史 sessions）",
            "不跑 gate2-run-12（其名已占用，且记录属旧候选）",
            "共享数据库 / 服务端口 / 付费账户禁止并发",
            "unknown_server_state 的题未经人工确认不得重跑",
            "一次开发轮只算候选证据，不得宣称生产级质量或统计显著提升",
        ],
        "notes": "预登记由本会话生成；run 实际启动时以 gate2_runner 的 claim 为准。无 hidden-case 内容进入仓库。",
    }

    out = HERE / "t7-run13-manifest.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print("written:", out.relative_to(ROOT))
    print("run_id:", manifest["run_id"])
    print("candidate files:", len(manifest["candidate_files_sha256"]),
          " frozen files:", len(manifest["frozen_files_sha256"]))
    print("expected output:", manifest["expected_output"])


if __name__ == "__main__":
    main()
