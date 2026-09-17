# V2-T8 候选锚定（分解契约加固后重采）— 2026-09-10

采集时间（UTC）：2026-09-11T07:08:47+00:00
HEAD：`ebe82e2bda26185236d50afd780cfb48c7c5e946`　分支：master
取代：`candidate-manifest-20260910.json`（T7 锚定，**保留留痕，未覆盖**）

## 与 T7 锚定的 delta（本次改动的候选文件）

- `backend/agent/controller.py` —— **已变化**
- `backend/agent/runtime.py` —— **已变化**
- `backend/agent/service.py` —— **已变化**
- `backend/agent/writer.py` —— **已变化**
- `backend/observability.py` —— **已变化**
- `backend/scripts/gate2_runner.py` —— **已变化**
- `backend/tests/test_agent_chat_integration.py` —— **已变化**
- `backend/tests/test_agent_controller.py` —— **已变化**
- `backend/tests/test_agent_gate.py` —— **已变化**
- `backend/tests/test_agent_resume.py` —— **已变化**
- `backend/tests/test_agent_runtime.py` —— **已变化**
- `backend/tests/test_agent_writer.py` —— **已变化**
- `backend/tests/test_agent_coverage_loop.py` —— **已变化**
- `backend/tests/test_gate2_runner.py` —— **已变化**
- `backend/tests/test_review_sidecar.py` —— **已变化**

## ⚠️ 新增候选文件（旧清单未覆盖 ⇒ 已纳入锚定）

- `backend/agent/gate.py`
- `backend/agent/planner.py`
- `backend/agent/schemas.py`
- `backend/answer_cache.py`
- `backend/auth.py`
- `backend/clarify.py`
- `backend/complexity.py`
- `backend/contract_verify.py`
- `backend/domain_rules.py`
- `backend/intent.py`
- `backend/knowledge_service.py`
- `backend/law_versions.py`
- `backend/llm_registry.py`
- `backend/main.py`
- `backend/mcp_server.py`
- `backend/multi_extract.py`
- `backend/output_normalize.py`
- `backend/pyproject.toml`
- `backend/qa_seeds.py`
- `backend/quality.py`
- `backend/query_understand.py`
- `backend/quota_store.py`
- `backend/rag_chain.py`
- `backend/request_bootstrap.py`
- `backend/retrieval.py`
- `backend/retrieval_core.py`
- `backend/schemas.py`
- `backend/scripts/_client.py`
- `backend/scripts/_judge.py`
- `backend/scripts/acceptance.py`
- `backend/scripts/benchmark_trend.py`
- `backend/scripts/capture_eval.py`
- `backend/scripts/check_agent_release.py`
- `backend/scripts/create_eval_artifact.py`
- `backend/scripts/eval_5law.py`
- `backend/scripts/eval_agent.py`
- `backend/scripts/eval_consistency.py`
- `backend/scripts/eval_exam.py`
- `backend/scripts/eval_exam_professional.py`
- `backend/scripts/eval_latency_log.py`
- `backend/scripts/eval_negative_run.py`
- `backend/scripts/eval_quality.py`
- `backend/scripts/eval_relevance.py`
- `backend/scripts/eval_retrieval.py`
- `backend/scripts/eval_robustness.py`
- `backend/scripts/gate2_probe.py`
- `backend/scripts/gen_freeze_manifest.py`
- `backend/scripts/gen_g1_audit.py`
- `backend/scripts/gen_g2_audit.py`
- `backend/scripts/gen_g3_audit.py`
- `backend/scripts/gen_g3_cases.py`
- `backend/scripts/gen_gate1_freeze.py`
- `backend/scripts/gen_gate1_law_check.py`
- `backend/scripts/gen_phase0_snapshot.py`
- `backend/scripts/gen_phase1_audit.py`
- `backend/scripts/gen_phase1_audit_source.py`
- `backend/scripts/gen_qa_corpus.py`
- `backend/scripts/gen_qwen_cases.py`
- `backend/scripts/gen_r8_disposition.py`
- `backend/scripts/gen_readiness_manifest.py`
- `backend/scripts/gen_route_mask_grayscale.py`
- `backend/scripts/gen_s5_reeval.py`
- `backend/scripts/harness_fact_reveal.py`
- `backend/scripts/mock_llm_500.py`
- `backend/scripts/rebuild_embeddings.py`
- `backend/scripts/recompute_boundary_manifests.py`
- `backend/scripts/release_manifest.py`
- `backend/scripts/restore_drill.py`
- `backend/scripts/safety_readiness_check.py`
- `backend/scripts/smoke_b1b5.py`
- `backend/scripts/smoke_citation_full.py`
- `backend/scripts/smoke_transcribe.py`
- `backend/scripts/switch_embedding.py`
- `backend/scripts/test_mcp_models.py`
- `backend/scripts/verify_new_law.py`
- `backend/seed_admin.py`
- `backend/settings.py`
- `backend/tests/test_agent_evaluator.py`
- `backend/tests/test_agent_prompt_contracts.py`
- `backend/tests/test_agent_release_check.py`
- `backend/tests/test_answer_cache.py`
- `backend/tests/test_cache_similar.py`
- `backend/tests/test_capture_eval.py`
- `backend/tests/test_capture_protocol.py`
- `backend/tests/test_chat_force_agent.py`
- `backend/tests/test_citation.py`
- `backend/tests/test_clarify.py`
- `backend/tests/test_complexity.py`
- `backend/tests/test_contract_file.py`
- `backend/tests/test_contract_review.py`
- `backend/tests/test_contract_verify.py`
- `backend/tests/test_create_eval_artifact.py`
- `backend/tests/test_eval_agent.py`
- `backend/tests/test_flagship_quality.py`
- `backend/tests/test_gate5_judge_layers.py`
- `backend/tests/test_harness_fact_reveal.py`
- `backend/tests/test_init_release_evidence.py`
- `backend/tests/test_knowledge_service.py`
- `backend/tests/test_law_versions.py`
- `backend/tests/test_llm_guard.py`
- `backend/tests/test_multi_extract.py`
- `backend/tests/test_output_normalize.py`
- `backend/tests/test_pre_rewrite_order.py`
- `backend/tests/test_qa_direct_return.py`
- `backend/tests/test_qa_invalidate.py`
- `backend/tests/test_quality.py`
- `backend/tests/test_query_understand.py`
- `backend/tests/test_quota_switch.py`
- `backend/tests/test_release_manifest.py`
- `backend/tests/test_request_bootstrap.py`
- `backend/tests/test_retrieval_rerank.py`
- `backend/tests/test_routing.py`
- `backend/tests/test_routing_metrics.py`
- `backend/tests/test_scenario_data.py`
- `backend/tests/test_scenario_supplement.py`
- `backend/tests/test_tiering.py`
- `backend/tests/test_tool_gateway.py`
- `backend/tools/contracts.py`
- `backend/tools/gateway.py`
- `backend/tools/legal_retrieval.py`
- `backend/scripts/run_evidence.py`
- `backend/tests/test_log_field_whitelist.py`
- `backend/tests/test_run_evidence.py`
- `backend/tests/test_statute_supplement.py`

候选文件总数：141；冻结文件总数：13
**冻结文件漂移：0** ✅（冻结物未被本次改动触碰）

## 本次改动说明

- `backend/agent/runtime.py`：分解契约加固（穷尽性提示词 + 事实分句覆盖度确定性检查 + 有界修复环）
- `backend/observability.py`：登记 `agent_coverage_*` 与 `agent_pre_run_*` 诊断字段（修 handoff §12.3 的静默丢弃缺陷）
- `backend/tests/test_agent_runtime.py`：新增 10 个用例（含终止性回归与白名单回归）

## 复算方式

```bash
python - <<'PY'
import json,hashlib,pathlib
m=json.load(open('dispatch-output/t2-persistence-20260910/candidate-manifest-t8-20260910.json',encoding='utf-8'))
for sec in ('candidate_files_sha256','frozen_files_sha256'):
    for rel,exp in m[sec].items():
        got=hashlib.sha256(pathlib.Path(rel).read_bytes()).hexdigest()
        assert got==exp, (sec, rel)
print('anchor OK')
PY
```

## 红线（沿用）

- 不 commit / 不 stash / 不 reset（候选 = 脏工作树 + 哈希锚定）
- 不修改冻结物；不并行跑共享数据库 / 端口 / 付费账户
- 反悔方式：`git apply --reverse candidate-post-t8.patch`（2650 行，已 `--reverse --check` 通过）
