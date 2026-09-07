# Research questions

RQ1 and RQ2 are answered by Phase 1. RQ3 and RQ4 are the two questions of the Phase 2
external-taxonomy control; both ODC reviews are sealed, the pre-registered analysis has been run,
and both questions are **answered with caveats**.

Phase status: **Phase 1A (reproduction) — COMPLETE**, **Phase 1B (robustness) — COMPLETE**,
**Phase 2 (ODC external-taxonomy control) — COMPLETE (workflow state `ANALYZED`)**.

Current stage: **MANUSCRIPT SYNTHESIS / OPTIONAL HUMAN VALIDATION**. The current scientific
state, with interpretations and the claims that must not be made, is in
[`current_research_findings.md`](current_research_findings.md).

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

## RQ3 — External-taxonomy control

> Does an independent mechanism-neutral software-defect taxonomy yield higher inter-reviewer
> reproducibility on the same SWE-smith cases than the AIDev-derived agent-failure taxonomy?

Operationalised as: apply the **Defect Type** dimension of IBM's Orthogonal Defect Classification
(ODC, 1992) to the same 100 frozen SWE-smith cases, with the same evidence, the same two reviewer
families and the same blind independence, so that the taxonomy is the only thing that changes;
then compare per-case agreement indicators between the two taxonomies with a two-sided McNemar
test and a paired case-level bootstrap. The Phase 1 values enter that comparison by being loaded
from the frozen Phase 1 artifacts, not by being quoted.

The question exists because Phase 1 cannot distinguish two explanations of its own result:
that the AIDev-derived taxonomy is the wrong instrument for static synthetic bugs
(a measurement mismatch), or that SWE-smith bugs are hard to classify reproducibly under any
defect taxonomy.

**Status: answered with caveats (Phase 2 — COMPLETE, workflow state `ANALYZED`).** On the same
100 frozen cases, ODC agreement is 60/100 (60.0%, κ 0.5131) against the Phase 1 broad-family
41/100 (41.0%, κ 0.2420): a paired difference of +19 percentage points, exact two-sided McNemar
p = 0.0183, paired bootstrap agreement difference +0.190 (95% CI [0.040, 0.330]) and κ difference
+0.2711 (95% CI [0.1118, 0.4255]). Read against the pre-registered interpretation matrix and its
pre-stated thresholds, this is Outcome A. The full reports are
[`../experiments/phase2_odc_control/analysis/odc_agreement.md`](../experiments/phase2_odc_control/analysis/odc_agreement.md)
and
[`../experiments/phase2_odc_control/analysis/taxonomy_comparison.md`](../experiments/phase2_odc_control/analysis/taxonomy_comparison.md);
the pre-registered protocol and the frozen ODC rubric remain in
[`../experiments/phase2_odc_control/`](../experiments/phase2_odc_control/README.md).

The caveats are not softened by the result: higher agreement under ODC does not mean ODC is
correct, and does not mean SWE-smith is realistic. ODC agreement of 60% is also far from
perfect, and the `taxonomy_fit` endpoint agrees on only 56 of 100 cases (κ 0.1861). See
[`threats_to_validity.md`](threats_to_validity.md) and
[`current_research_findings.md`](current_research_findings.md).

## RQ4 — Generation mechanism under the external taxonomy

> Under the external taxonomy, does reviewer agreement still vary by SWE-smith generation
> mechanism, particularly procedural versus nonprocedural generation?

Operationalised as: after both ODC reviews are sealed — and only then — join the same hidden
generation-method crosswalk used for RQ2, and recompute agreement by generation family and for
the frozen `procedural` vs `nonprocedural` (`llm + mirror + combine`) contrast, with the
`llm + mirror` sensitivity contrast beside it. RQ2's finding was an association, and so is
anything RQ4 produces.

**Status: answered with caveats (Phase 2 — COMPLETE, workflow state `ANALYZED`).** Under ODC,
agreement still varies by generation family — llm 23/36 (63.9%, κ 0.5320), mirror 11/28 (39.3%,
κ 0.2145), procedural 26/34 (76.5%, κ 0.6304), `combine` 0/2 and not interpretable — but the
direction of the procedural contrast is not the Phase 1 direction: 26/34 (76.5%) procedural
against 34/66 (51.5%) nonprocedural, against Phase 1's 6/34 (17.6%) against 35/66 (53.0%). The
Phase 1 procedural deficit disappeared and reversed direction under ODC; the pre-registered
decision rule words the same observation as the procedural agreement gap having substantially
narrowed, and that frozen wording is unchanged. The paired bootstrap of the change in the gap is
−0.6034 (95% interval [−0.8762, −0.3125]). It remains an association, not a causal claim about
the generation mechanism. Report:
[`../experiments/phase2_odc_control/analysis/taxonomy_comparison.md`](../experiments/phase2_odc_control/analysis/taxonomy_comparison.md)
§11–§12.

RQ3 and RQ4 are the only new scientific questions in Phase 2. It is not a coverage study, not a
taxonomy v2, and not an adjudication.

## Out of scope for the current phase

No taxonomy v2, no adjudication of the Claude/Codex disagreements, no relabelling of any Phase 1
case, no confirmatory significance testing beyond Phase 1B's exploratory association tests, no
new synthetic bugs, no model training, no causal claims, and no comparison of family-frequency
distributions as though the current taxonomy were mechanism-neutral.

The Phase 2 ODC control is the one external taxonomy in scope, it is an explicitly versioned
experiment with its own directory and its own write-up, and it is COMPLETE (workflow state
`ANALYZED`): its labels and its analysis outputs are now frozen research artifacts and must not
be edited. No BugPilot taxonomy classification is planned. The optional human-validation study
described in [`current_research_findings.md`](current_research_findings.md) has not been started
and is not numbered as a phase.
