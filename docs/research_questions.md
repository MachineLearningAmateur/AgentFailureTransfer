# Research questions

The current scope of this study is RQ1 and RQ2. RQ3 is recorded here so that the boundary of
the current claim is explicit; it has **not** been tested.

Phase status: **Phase 1A (reproduction) — COMPLETE**, **Phase 1B (robustness) — COMPLETE**,
**Phase 2 (external-taxonomy control) — NOT STARTED**.

## RQ1 — Taxonomy transfer

> How reliably does a failure taxonomy derived from real coding-agent repair
> attempts transfer to synthetic SWE-smith training bugs?

Operationalised as: apply the frozen `aidev_failure_taxonomy_v1` labels, produced by two
independent blind LLM reviewers, to both corpora, and compare inter-reviewer agreement — at the
fine-grained level and under the frozen broad-family mapping — between the real-agent corpus
and the synthetic corpus.

**Status: reproduced (Phase 1A) and robustness-checked (Phase 1B).** See
[`../analysis/taxonomy_transfer/headline_results.md`](../analysis/taxonomy_transfer/headline_results.md).
Read those numbers alongside the population caveat: the AIDev figures cover the 49 cases where
both reviewers assigned a technical pattern, the SWE-smith figures cover all 100 frozen cases.

Phase 1B tests whether that answer depends on the denominator choice or on a single point
estimate: it recomputes AIDev over all 100 reviewed cases using the source study's own all-100
semantics, and attaches Wilson intervals to every agreement rate and bootstrap intervals to
every κ. The gap survives both. See
[`../analysis/taxonomy_transfer/phase1b_robustness/robustness_report.md`](../analysis/taxonomy_transfer/phase1b_robustness/robustness_report.md).

## RQ2 — Generation mechanism

> How does taxonomy transfer vary with synthetic bug-generation mechanism?

Operationalised as: after the sealed SWE-smith labels are loaded, join the generation-method
crosswalk that was withheld from both reviewers, group by the source study's authoritative
`method_family`, and compute agreement within each generation family.

**Status: reproduced (Phase 1A) and robustness-checked (Phase 1B).** See
[`../analysis/generation_method/agreement_by_generation.md`](../analysis/generation_method/agreement_by_generation.md).
The `combine` family has n = 2 and supports no substantive conclusion.

Phase 1B collapses the families into the binary contrast specified in its plan — procedural against
nonprocedural (`llm + mirror + combine`), plus a sensitivity contrast against `llm + mirror`
only — and quantifies the difference with a two-sided Fisher's exact test, a risk difference,
a risk ratio and an odds ratio with intervals, and an exploratory permutation check. Reviewer
agreement was lower among procedurally generated cases. That is an association, not a causal
claim about the generation mechanism.

## Potential future RQ3 — future work / not yet tested

> Is the transfer failure specific to an agent-process taxonomy, or does it
> persist under a mechanism-neutral bug taxonomy?

**This has not been tested.** Nothing in this repository bears on it. Answering it would
require running a second, mechanism-neutral taxonomy over the same frozen cases — a new,
explicitly versioned experiment with its own inputs and its own write-up, which would leave
the imported reviewer labels untouched. The placeholder directory
`experiments/external_taxonomy_control/` exists for that work; it is empty, and no external or
BugPilot taxonomy classification has been run.

## Out of scope for the current phase

No taxonomy v2, no adjudication of the Claude/Codex disagreements, no new labels, no external
taxonomy, no confirmatory significance testing beyond Phase 1B's exploratory association tests,
no new synthetic bugs, no model training, no causal claims, and no comparison of
family-frequency distributions as though the current taxonomy were mechanism-neutral.
