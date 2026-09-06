# Threats to validity

What the reproduced numbers do not support. Read this before quoting any figure from
`analysis/`.

## Construct: the taxonomy and its mapping

**The taxonomy was derived from AIDev, using AIDev.** `aidev_failure_taxonomy_v1` was developed
by studying real coding-agent repair attempts in the AIBugAnalysis corpus. Its 11 fine-grained
labels name the things that go wrong when an agent tries to repair real code. Applying it to
SWE-smith is therefore an asymmetric test by construction: one corpus is the taxonomy's home
ground, the other is not. A lower agreement on SWE-smith is consistent with "the taxonomy does
not transfer", but it is also consistent with "the taxonomy was fitted to one corpus's
vocabulary" — the design cannot separate those.

**The broad-family mapping is partly in-sample for AIDev.** The frozen `fine → family` mapping
was built from the AIDev disagreement matrix — the source study's own
`family_mapping_analysis.md` records candidate mappings being compared on the *same* 49 cases
the family-level agreement is then reported on, and its calibration report states plainly that
the family-level number is an in-sample estimate needing validation on a new labelling
exercise. So AIDev's 36/49 (κ 0.6575) is not an out-of-sample estimate and should not be read
as one. The SWE-smith family number *is* the out-of-sample application of that same frozen
mapping — which makes the AIDev→SWE-smith family-level drop partly an in-sample vs
out-of-sample artefact rather than purely a corpus effect. Note also that the mapping's entire
effect is one three-way collapse inside `REPOSITORY_UNDERSTANDING`; the other eight families
are single-member identity renames.

**Process-oriented labels are not naturally observable from static synthetic bugs.** Several
fine labels describe the *repair process* — `unverified_trial_and_error`, `vacuous_verification`,
`misdiagnosed_root_cause`, `masked_symptom_instead_of_fixing`. These presuppose an agent that
attempted something and can be observed doing it. A SWE-smith case is a static injected bug
state with no repair trajectory attached, so a reviewer must infer a process that never
happened. Low agreement on SWE-smith may reflect that mismatch of observability rather than any
property of synthetic bugs as such.

## Measurement: what agreement is, and who the reviewers are

**There are only two reviewers, both LLMs.** Every number here is a two-rater statistic
produced by two blind LLM reviews. Two raters give no way to estimate rater variance, and both
raters being language models means correlated blind spots are not just possible but likely.
Nothing here generalises to human labellers, and nothing here estimates how a third reviewer
would have labelled.

**Agreement measures reproducibility, not truth.** Cohen's κ says how consistently two raters
applied the same scheme. It says nothing about whether either rater was right. High agreement
can mean a shared misunderstanding; low agreement can mean the cases are genuinely ambiguous
under the scheme. No ground truth exists in either corpus, no adjudication has been performed,
and none is planned in this phase. Every result should be read as "how reproducibly can this
taxonomy be applied", not "how accurate is this taxonomy".

**The reviewer identities are not symmetric across the two studies.** On the AIDev side,
`review_metadata.json` names each reviewer's model and provider. On the SWE-smith side it does
not: the SWE-smith reviewer metadata records completion time, result count and hashes, and
**no model or provider field at all**. "Codex" and "Claude" are directory names on the
SWE-smith side. No claim about which specific models produced the SWE-smith labels is backed by
any imported artifact, and none should be made.

## Population: the two corpora are not comparable

**The AIDev and SWE-smith headline numbers are computed on structurally different
populations.** The AIDev figures cover the 49 of 100 reviewed cases where *both* reviewers
assigned a technical pattern (`failure_pattern != "UNASSIGNED"` on both sides). The SWE-smith
figures cover all 100 frozen cases, because the SWE-smith review schema has no `UNASSIGNED`
value — every sampled case is an execution-validated bug state, so the non-technical escape
hatch does not exist there. This is not a choice made in this repository; it follows from the
two source schemas. "63.3% vs 41.0%" is therefore not a like-for-like contrast, and part of the
gap is a selection effect: the AIDev population is pre-filtered to cases where both reviewers
were confident enough to name a pattern at all, while SWE-smith is not filtered at all. Both
population definitions must be stated side by side wherever the numbers appear.

**Do not confuse the AIDev headline with the all-100 variant.** The AIDev source study also
contains an earlier, structurally different analysis at `analysis/cross_model/`: `failure_pattern`
agreement of **65/100, κ 0.5531**, computed over all 100 cases and counting
`UNASSIGNED`-vs-`UNASSIGNED` as agreement. That analysis was **not imported** here. It is the
statistic structurally analogous to SWE-smith's 41/100, and it is *not* the headline. If it is
ever cited, label it explicitly as the all-100 variant, alongside its inclusion rule; quoting
it as though it were the 49-case number, or the 49-case number as though it were the all-100
number, would misstate both.

**The SWE-smith sample represents 4,207 resolvable training-task instances, not all of
SWE-smith.** The frozen sample was drawn from a population of 4,207 unique resolvable
training-task instances (derived from the pinned upstream revisions: ~5,017 documented
trajectories, 5,016 rows in the pinned revision, 4,211 unique task instances, 4 unresolved).
Any inference generalises to that population and to nothing wider — not to SWE-smith as a whole,
not to other SWE-smith releases, and not to synthetic bug generation in general.

**`combine` has n = 2 and supports no substantive conclusion.** Two cases, drawn under a
proportional allocation from a population where `combine` is a small minority. Its κ of 0.0 is a
*genuine* value, not an undefined or degenerate one: the two reviewers' label sets on those two
cases are disjoint, so both observed and expected agreement are 0, giving κ = (0 − 0)/(1 − 0) = 0.
(This matters for reimplementation as well as for interpretation — an implementation that
returns `nan` or `None` for a two-case subgroup will not reproduce it.) But a genuine κ from
n = 2 is still a κ from n = 2. It is reported for completeness only, and no comparison between
`combine` and any other generation family is meaningful.

## Language and corpus type are confounded

**Every SWE-smith task is Python.** The sample is 100% Python by construction of the
population.

**AIDev is multilingual.** The AIDev corpus spans many languages. Across the 35-case strict
code-state corpus, the language distribution is typescript 12, go 5, python 4, unknown 4,
rust 3, csharp 2, java 2, cpp 1, php 1, c 1.

**Only 4 of those 35 strict AIDev cases are Python.** That is the entire overlap available for
a language-controlled comparison. Four cases cannot support a statistical claim of any kind.

**All 4 of those Python cases belong to `REPOSITORY_UNDERSTANDING`.** They carry no family
variation at all, so they cannot even indicate which families do or do not transfer. (Case 003
has a fine-label disagreement that the family mapping absorbs.)

**Consequently language and corpus type are fully confounded.** Real-agent failures come with a
multilingual corpus; synthetic training bugs come with a Python-only corpus. Any difference
between the two agreement figures could be a corpus-type effect, a language effect, or both,
and this design cannot separate them. Coverage of the strict corpus is deliberately not
analysed in this phase.

**The AIDev language attribution is itself a cross-repo artifact.** AIDev's own
`pr_manifest.csv` has no `language` column. The language of the 35 strict cases comes from
`data/swesmith/analysis/aidev_strict_language_profile.json`, imported from the *SWE-smith*
repository, where it was produced by that study's environment-mix profiling script. Note the
direction of that dependency: a statement about the AIDev corpus rests on a derived artifact
computed in the other source study.

## Reporting and reproduction

**The per-generation-family κ values published as the headline are family-level, not
fine-level.** They diverge — for `llm`, family κ 0.2976 vs fine κ 0.3364. Both levels are
emitted in `analysis/generation_method/agreement_by_generation.md`, each labelled with which
level it is. Quoting a per-family κ without saying which level it came from is ambiguous, and
for `llm` it is materially misleading.

**Rounding.** The SWE-smith fine-level κ is 0.2535425101. It rounds to the frequently stated
0.254 only at 3 decimal places; at 4 dp it is 0.2535. Both the full-precision and the 4 dp
values are emitted, and the reproduction checkpoint tolerance is `5e-4`, so a value differing in
the fourth decimal is a real disagreement, not rounding noise.

**There is no committed source-side artifact to diff the SWE-smith numbers against.** The
SWE-smith source study never committed its headline results: `analysis/frozen_families/` and
`analysis/cross_model/` do not exist there, and no file in that repository contains the pooled
or per-family figures — they existed only as script output. This repository's
`analysis/taxonomy_transfer/` and `analysis/generation_method/` are therefore the first
committed artifacts carrying them. The only committed cross-check available is on the AIDev
side, against the imported `agreement_metrics.json`, which `reproduce_headline_results.py
--check` uses. The SWE-smith side is verified against the expected checkpoint values and
against the sealed labels themselves, not against a source-study file.

**The κ implementation was unified, which the source studies' were not.** AIDev used
`sklearn.metrics.cohen_kappa_score` at full precision; SWE-smith used a hand-written κ rounded
to 4 dp with a degenerate guard. They are numerically equivalent for the unweighted case, but
this repository computes every κ with one hand-rolled implementation (see
[`study_design.md`](study_design.md)), cross-checked in the tests against scikit-learn. Small
differences from a number quoted in either source study's own prose can therefore originate in
that unification rather than in the data.

## The Phase 2 ODC control: what a second taxonomy can and cannot settle

Phase 2 is in SETUP — the protocol is drafted and no review has been run — so nothing below is a
caveat about a result. These are the limits the design carries in advance, recorded now so that
they cannot be softened once numbers exist.

**ODC is not ground truth.** Orthogonal Defect Classification is an independent, pre-existing,
mechanism-neutral scheme, which is what a control requires. It is not a correct answer key for
these cases. No case in either corpus has a ground-truth defect type, no adjudication is planned,
and the Phase 2 endpoints are agreement statistics: they measure how reproducibly two reviewers
apply one instrument, not whether either reviewer was right. A high ODC κ could equally be two
reviewers sharing a misreading of a category.

**Higher agreement would not mean greater realism.** Reproducibility of classification and
fidelity to real coding-agent failures are different properties. If ODC agreement comes out well
above the Phase 1 figure, that is evidence about the instruments, not evidence that SWE-smith
bugs resemble real agent failures — and if it comes out no better, that is not evidence that
SWE-smith is "bad". The pre-registered interpretation matrix in the Phase 2 protocol states each
reading conditionally and blocks both of those inferences explicitly.

**Only one ODC dimension is used.** Defect Type only. Defect trigger, development activity,
impact, source, age and the other ODC process attributes are excluded, deliberately, because they
would reintroduce the process information the control is meant to remove. Phase 2 is therefore
not a test of ODC as a measurement programme, and no result here supports a claim about ODC as a
whole.

**`UNCLASSIFIABLE` is a study-level sentinel, not an ODC type.** ODC defines eight defect types;
the ninth allowed value is ours. It exists so that a reviewer facing a case no ODC type describes
can say so instead of forcing a fit — which would inflate apparent coverage and quietly raise
agreement. That makes the sentinel rate part of the finding, but it also means the Phase 2 label
set is not the published ODC label set, and κ computed over nine values is not κ over eight.

**The tie-break guidance is ours, not ODC's.** The nine numbered rules that resolve two plausible
categories are this study's operationalisation of the published types. They were frozen before
any reviewer saw a Phase 2 packet, and written without inspecting any Phase 1 case-level label —
but they are still a choice we made, and a different ordering could produce different agreement.
They are documented as an operationalisation everywhere they appear, and they may not be amended
after review begins except as a formally recorded protocol amendment.

**The reviewer-family caveat carries over from Phase 1 unchanged.** There are still only two
reviewers and both are LLMs, so there is still no way to estimate rater variance and correlated
blind spots remain likely; nothing generalises to human labellers. The reviewers are the same two
families as Phase 1, which is what makes the comparison paired — and which also means any shared
disposition of these two reviewers is common to both taxonomies rather than controlled by the
design. And as in Phase 1, the SWE-smith reviewer metadata names no model or provider: "Claude"
and "Codex" are reviewer identities in this study's sense, not claims about specific models.

**Phase 2 modifies nothing from Phase 1.** The Phase 1 labels are sealed and are read-only
inputs to the paired comparison; the Phase 2 labels are new labels under a new taxonomy, held in
their own experiment directory.

## Scope

Nothing here has been adjudicated or re-labelled, and no Phase 1 number has been subjected to a
second taxonomy: the Phase 2 ODC control is drafted but unrun, so every figure in `analysis/`
still rests on the single AIDev-derived taxonomy. No causal claim is supported. In particular, family-frequency distributions
must not be compared across the two corpora as though the current taxonomy were
mechanism-neutral — it is not, and that comparison is explicitly out of scope for this phase.
