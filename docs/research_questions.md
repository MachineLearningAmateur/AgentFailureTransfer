# Research questions

The current scope of this study is RQ1 and RQ2. RQ3 is recorded here so that the boundary of
the current claim is explicit; it has **not** been tested.

## RQ1 — Taxonomy transfer

> How reliably does a failure taxonomy derived from real coding-agent repair
> attempts transfer to synthetic SWE-smith training bugs?

Operationalised as: apply the frozen `aidev_failure_taxonomy_v1` labels, produced by two
independent blind LLM reviewers, to both corpora, and compare inter-reviewer agreement — at the
fine-grained level and under the frozen broad-family mapping — between the real-agent corpus
and the synthetic corpus.

**Status: reproduced.** See [`../analysis/taxonomy_transfer/headline_results.md`](../analysis/taxonomy_transfer/headline_results.md).
Read those numbers alongside the population caveat: the AIDev figures cover the 49 cases where
both reviewers assigned a technical pattern, the SWE-smith figures cover all 100 frozen cases.

## RQ2 — Generation mechanism

> How does taxonomy transfer vary with synthetic bug-generation mechanism?

Operationalised as: after the sealed SWE-smith labels are loaded, join the generation-method
crosswalk that was withheld from both reviewers, group by the source study's authoritative
`method_family`, and compute agreement within each generation family.

**Status: reproduced.** See [`../analysis/generation_method/agreement_by_generation.md`](../analysis/generation_method/agreement_by_generation.md).
The `combine` family has n = 2 and supports no substantive conclusion.

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
taxonomy, no statistical significance tests, no new synthetic bugs, no model training, no
causal claims, and no comparison of family-frequency distributions as though the current
taxonomy were mechanism-neutral.
