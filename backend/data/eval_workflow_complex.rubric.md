# Complex legal-agent baseline rubric

This frozen set contains 20 human-reviewed cases. It is an evaluation input, not a source of legal conclusions or an LLM-generated gold answer.

## Canonical issue granularity

One issue names one legally distinct decision axis (for example, `诉讼时效`, `定金`, or `知情同意`). Do not split a single statutory rule into several issues; do split independent civil, administrative, criminal, time-applicability, or prompt-safety questions. The `issues` array is ordered from the user's primary dispute to the dependent issue.

## Outcome-changing facts

`critical_facts` are facts that can change the applicable rule, limitation period, burden, remedy, or route. A response must ask the canonical `expected_clarification` when a listed critical fact is absent. Generic requests for “more details” do not satisfy this requirement.

## Primary legal evidence

Primary evidence means a verifiable statute, regulation, judicial interpretation, effective official decision, contract, authenticated record, or case-provided document. Evidence IDs must identify the source used (for statutes, the frozen `law:article` form). Uncited model prose, an assertion that a source exists, or a secondary summary is not primary legal evidence.

## Deterministic scoring

For each canonical `important_claim`, an adapter must emit a claim with exactly that text and at least one evidence ID from that case's `expected_laws` list. The evaluator reports the share of canonical claims with an allowed primary-evidence ID and lists every supplied claim with no allowed ID. Empty IDs and arbitrary IDs (for example, `x`) are unsupported. A missing canonical claim lowers coverage even when there is no supplied claim to list. It intentionally does not use an LLM judge and does not assess semantic legal correctness. Human review is required for issue classification, clarification quality, legal-date applicability, and evidence relevance.

## Frozen-set handling

The evaluator hashes the raw JSON bytes. Any edit changes the hash and creates a new baseline; results with different hashes must not be compared. The set includes multi-issue consultation, contract comparison, missing critical facts, a law-date conflict, and prompt-injection text.
