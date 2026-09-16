# BLOCKED — controlled captures and independent audit pending

This candidate boundary is validated and the same-question Agent isolation
preflight now succeeds, but it is not release approval.

## Frozen candidate boundary

- Release ID: `legal-agent-v1-20260905-003`
- Git revision: `366c16f191e54264a01890da788b37bf2fea9f04`
  - `deb65fc` fix(agent): planner/writer 提示词补全严格校验所需的输出 JSON 契约
  - `366c16f` docs(backend): 修正公开注册开关注释为真实环境变量 FEATURE_SELF_REGISTER
- Backend image: `sha256:6ab091963f439827824d1ba62efd81b8b85cbf319a8128d80b695de08cc1ecc0`
  - previous candidate retained as `ai-legal-helper-backend:pre-deb65fc` (`sha256:c270b83507ff…`)
- Runtime provider/model: `longcat-openai-compatible` / `LongCat-2.0` (`model_snapshot: LongCat-2.0`)
- Frozen case-set SHA-256: `f8ca2f2e71250f18a3741132d1024e3865eb21c1fb997a4d4d26c12391f1588d`
- Jurisdiction: `CN`
- Authoritative corpus source confirmed by the data owner: 国家法律法规数据库 (`flk.npc.gov.cn`)
- Corpus ingestion / review boundary confirmed by the data owner: `2026-08-01`
- Validated release-manifest SHA-256: `d3edce07cfc0c2def2a95e9712e41636026863f61e3c11ffec3eb8e2ad6ceed7`
  (validated in-repo with `backend/scripts/release_manifest.py`, exit 0)
- Independent joint legal/security reviewer: `haimeng`

## Why a new candidate became necessary (root cause of the 002 Agent blocker)

The 002 same-question Agent preflight failed with `agent_status failed` +
`error` and zero `agent_runs` rows. Forensics on the isolated volume showed the
failure happened before run creation (independent `create_run` commit cannot be
rolled back), with a non-technical reason code. Instrumented full-path
reproductions against LongCat (2/2 runs) plus direct decomposer probes (3/3
clean) established the deterministic root cause:

- `parse_plan_decision` requires tool_call decisions to be exactly
  `{kind, issue_id, tool_name, args}`; `AGENT_WRITER_SYSTEM` likewise demands an
  exact claims schema — but **neither system prompt ever documented those
  schemas**. A live model must guess; LongCat-2.0 emitted
  `{"kind":"tool_call","name":"retrieve_laws","args":{…}}` (name ≠ tool_name,
  issue_id missing), the strict validators fail-closed by design, and every real
  Agent run ended in `PLANNER_PARSE_ERROR` fallback (or, once at 07:34
  2026-09-05, a decomposer-level hard failure pre-run).
- The validators are correct (fail-closed against untrusted output is tested
  policy); the prompts were the defect. Fix = complete the prompt contract only
  (`deb65fc`), verified red→green by `backend/tests/test_agent_prompt_contracts.py`.

## Completed checks

- Full backend suite after the fix: 769 passed (pytest, local venv, 2026-09-05).
- Candidate image rebuilt (full Dockerfile build; CPU-only torch asserted
  `2.6.0+cpu`, no `nvidia-*` packages, BGE baked via hf-mirror).
- In-image file hashes for `agent/runtime.py`, `prompts.py`, `settings.py`,
  `main.py` match the working tree exactly; `/app/.env` absent.
- Boundary manifests recomputed with an independently written, reproducible
  implementation (`diag/recompute_manifests.py`):
  - corpus logical hash `d76220e7…` — byte-exact reproduction of the recorded
    002 value (proves corpus records did not drift; anchors: record_count
    10545, canonical_bytes 8840943);
  - tool-policy aggregate `f4e3e932…` — byte-exact match to 002 (no tool files
    changed);
  - prompt-bundle, runtime-config, index aggregates differ from 002 for
    accounted reasons (prompt/config commits; see index note below);
  - frozen case set and rubric hash identical to 002.
- Same-question Agent isolation preflight on a fresh container/volumes
  (`legal-agent-preflight-003`, 127.0.0.1 only): HTTP 200, SSE
  `agent_status waiting_user` + structured `clarification`
  (issue `issue_29e49e8570c72c05a6633afb`, prompt "是否存在诉讼时效中断、中止的
  法定事由"), **no error events**; isolated DB shows one run
  `status=waiting_user`, steps bootstrap → tool_call retrieve_laws →
  TOOL_SUCCEEDED → clarification (`OUTCOME_CHANGING_FACT_UNKNOWN`), consistent
  with SSE. This is the first live end-to-end Agent lifecycle (planner tool
  call included) on LongCat-2.0.
- Agent remains safe-off by default in deployment config: `AGENT_ENABLED=false`,
  `AGENT_TRAFFIC_PERCENT=0`. The 100% values used above existed only inside the
  isolated preflight container.

## Known limitations / honest notes

1. **Index byte drift (physical only).** Running the backend pytest suite
   mutates `backend/chroma_db` (test_phase5 intentionally writes and cleans up
   a `test_phase5_tmp` doc against the real vectorstore; chroma rewrites the
   qa_pairs HNSW segment and sqlite page layout). Logical corpus hash is
   byte-identical to 002 (proven above); the file-boundary aggregate
   `f4f03d40…` honestly reflects post-suite bytes of the same records. The 003
   index boundary is therefore frozen at 2026-09-05 post-suite state. Future
   candidate freezes must run the backend suite BEFORE freezing index bytes,
   and Phase K/J should evaluate sandboxing test_phase5 to a temp collection.
2. **Decomposer residual risk.** The 002-era 07:34 hard failure occurred in the
   issue decomposer (pre-run, non-technical reason) with unrecoverable output
   shape (no trace kept; SSE error code was not recorded by the harness). 5/5
   direct decomposer probes plus the successful 003 preflight were clean.
   Root cause class: malformed model JSON under temperature 0.7 →
   `ISSUE_DECOMPOSITION_INVALID`/`PLANNER_POLICY_VIOLATION` fail-closed. Not
   "fixed" on speculation per handoff rules; the capture adapter must record
   the SSE `error.code` and sanitized raw shapes for any recurrence.
3. **LongCat `disable_thinking:false` / `temperature=0.7`.** Provider role
   config unchanged in this candidate (minimal-change rule); strict-JSON
   compliance variance is a Phase B capability-matrix item.
4. The 003 preflight created one synthetic user + one conversation inside the
   isolated `legal_agent_eval003_data` volume only.
5. **Writer live path not yet exercised.** The 003 preflight ended in a
   clarification (correct for the frozen question), so the writer prompt fix is
   verified by unit tests + the prompt-contract tripwire only, not yet by a live
   LongCat drafting round. Phase D captures must treat any
   `MALFORMED_GENERATOR_OUTPUT`/writer reason codes as first-class findings.
6. **Evidence hygiene gaps found by review (2026-09-05).** The "769 passed"
   full-suite run was not archived as a log file (one-time gap; re-running the
   suite now would re-mutate the frozen index bytes, so it was not repeated —
   future suite runs must tee logs). Remediated: red→green logs for the
   contract tests archived as `diag/red-green-evidence-red.txt` /
   `diag/red-green-evidence-green.txt` (byte-identical working copies of the run outputs;
   the original .log files stay untracked per the repo `*.log` convention) (red reproduced by checking out the
   pre-fix prompt files; chroma untouched); the LongCat malformed planner shape
   is archived as `diag/longcat-observed-shapes.json`; the boundary-recompute
   implementation lives in `diag/recompute_manifests.py` (untracked working
   material — canonicalization is fully documented inside each manifest JSON;
   productize the script in the Phase C commit).
7. The 003 `agent-audit.json` is still the init-script template (all nulls) —
   it becomes a real artifact only at Phase F after `haimeng` signs.

## Remaining blockers

- Phase B: LongCat full product-capability audit matrix (PASS/DISABLED/BLOCKED
  incl. vision/voice protocol reality check).
- Phase C: real-but-isolated capture adapter (none exists yet; no-adapter
  synthetic reports remain release-ineligible).
- Phase D/E: controlled 20×2 dual-path captures and deterministic reports.
- Phase F: independent joint legal/security audit by `haimeng` over every
  Agent trace.
- Phase G: `check_agent_release.py` must yield `allowed=true` before rollout
  planning.
