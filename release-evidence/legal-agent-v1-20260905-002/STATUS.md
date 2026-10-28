# BLOCKED — controlled captures and independent audit pending

This candidate boundary is validated, but it is not release approval.

## Frozen candidate boundary

- Release ID: `legal-agent-v1-20260905-002`
- Git revision: `7655265de1771263e708914c3869ec8873557d0c`
- Backend image: `sha256:c270b83507ffdaddb51e6d7d696cf4e00d58bc1eb91b33c67c9093e3cd6a319f`
- Runtime provider/model: `longcat-openai-compatible` / `LongCat-2.0`
- Frozen case-set SHA-256: `f8ca2f2e71250f18a3741132d1024e3865eb21c1fb997a4d4d26c12391f1588d`
- Jurisdiction: `CN`
- Authoritative corpus source confirmed by the data owner: 国家法律法规数据库 (`flk.npc.gov.cn`)
- Corpus ingestion / review boundary confirmed by the data owner: `2026-08-01`
- Validated release-manifest SHA-256: `d8997f3f5aef31cc17b8973e3bb65abc381bd64048758bd4f88f756442057707`
- Independent joint legal/security reviewer: `haimeng`

## Completed checks

- Candidate code, image, model, prompt, tool-policy, non-secret runtime configuration, corpus and index boundaries are recorded.
- Capture protocol fixes timeout, retry, concurrency, output and tool-call ceilings.
- Agent remains safe-off by default: `AGENT_ENABLED=false`, `AGENT_TRAFFIC_PERCENT=0`.

## Remaining blockers

- Controlled, de-identified Existing RAG capture for all 20 frozen cases.
- Controlled, de-identified Agent capture for the same 20 cases and boundary.
- The repository currently has no real capture adapter; no-adapter synthetic reports are plumbing-only and release-ineligible.
- Deterministic reports generated from the two frozen v2 capture artifacts.
- Independent joint legal/security audit by `haimeng` over every Agent trace.
- Deterministic release check with `allowed=true`.
- Only after that check: isolated backup/restore rehearsal, four candidate scenarios and operator approval.

Do not enable Agent traffic or claim release approval while any blocker remains.
