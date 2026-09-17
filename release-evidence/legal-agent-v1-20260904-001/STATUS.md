# BLOCKED — release evidence incomplete

This directory is a partially populated candidate evidence package. Do not claim approval until every placeholder is replaced with traceable evidence and the independent audit is complete.

## Automated preflight progress

- Candidate source revision: `1a8331f5cd3372e50643ce78cb1dfcf47c786406`
- Candidate image digest: `sha256:8032564be82d1687f044c7760ca092f551aa827b801ae5432bc08be5f6e7fdcf`
- User-approved frozen case set: `frozen-eval-cases.json`
- Frozen case-set SHA-256: `f8ca2f2e71250f18a3741132d1024e3865eb21c1fb997a4d4d26c12391f1588d`
- Shape validation: 20 cases; 38 unique expected legal references.
- Local index metadata check: all 38 expected legal references were found.
- Runtime path check: `build_agent_runtime()` resolves `registry.get()`; the current default key is `vision_flag` with model `qwen3.5-omni-plus-2026-03-15`.
- Candidate image build verified externally: build completed, CPU-only torch and baked BGE load were checked, and the one-shot health check returned HTTP 200 before its validation container was removed.
- Prompt, tool-policy, non-secret runtime-config, logical corpus and active local index manifests were generated with reproducible canonicalization rules; all four file-boundary aggregates were independently recomputed successfully.

## Resolved build incidents

- The original multi-mirror Docker configuration returned invalid registry metadata. `registry-mirrors` is now empty; do not restore the seven-source backup for this candidate.
- The original CPU torch install path suffered SSL EOF on transitive dependencies. Commits `f26779e`, `6827444`, `a54b392`, and `1a8331f` produced the verified candidate image above.

These checks validate structure and local index coverage. User approval froze the case file, but this is not the independent joint legal/security audit required for release.

## Remaining blockers

- Independent reviewer designated: `haimeng`; review evidence is still pending.
- Controlled, de-identified Existing RAG and Agent answer captures.
- Independent joint legal/security audit.
- `law_as_of` confirmation from independent reviewer `haimeng`, followed by final release-manifest validation.
- Recovery drill and operator approval.
