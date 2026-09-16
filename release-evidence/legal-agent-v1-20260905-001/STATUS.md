# BLOCKED — controlled captures and independent audit pending

This candidate boundary is validated, but it is not release approval.

## Frozen candidate boundary

- Release ID: `legal-agent-v1-20260905-001`
- Git revision: `9fba8fb870bdfd8bf2c55bbebcb21ff5b626e27f`
- Backend image: `sha256:2c17161f9ca33ca3b77fbac7763d8b0c98fa7cb78da47d0c780dccf96125ac9f`
- Frozen case-set SHA-256: `f8ca2f2e71250f18a3741132d1024e3865eb21c1fb997a4d4d26c12391f1588d`
- Jurisdiction: `CN`
- Authoritative corpus source confirmed by the data owner: 国家法律法规数据库 (`flk.npc.gov.cn`)
- Corpus ingestion / review boundary confirmed by the data owner: `2026-08-01`
- Validated release-manifest SHA-256: `58ec58cc865a37a43dbd1084085a40a9f6554c5d183a21bc9b564391358c1606`
- Independent joint legal/security reviewer: `haimeng`

## Completed checks

- Release policy validated in the candidate image.
- Release manifest and its policy/protocol dependencies validated in the candidate image.
- Prompt, tool-policy, non-secret runtime-config, logical corpus and active index boundaries are recorded.
- Agent remains safe-off by default: `AGENT_ENABLED=false`, `AGENT_TRAFFIC_PERCENT=0`.

## Remaining blockers

- Controlled, de-identified Existing RAG capture for all 20 frozen cases.
- Controlled, de-identified Agent capture for the same 20 cases and boundary.
- The repository currently has no real capture adapter; no-adapter synthetic reports are plumbing-only and release-ineligible. The production `/api/chat` path writes business state and must not be used as a substitute.
- Deterministic reports generated from the two frozen v2 capture artifacts.
- Independent joint legal/security audit by `haimeng` over every Agent trace.
- Deterministic release check with `allowed=true`.
- Only after that check: isolated backup/restore rehearsal, four candidate scenarios and operator approval.

Do not enable Agent traffic, call this an online shadow run, or claim release approval while any blocker remains.
