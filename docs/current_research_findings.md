# Current research findings

What this project currently believes it has found, stated separately from what it merely
observed, from what was already known, and from what it must not claim.

This document is a **summary**, not a source of numbers. Every figure quoted here is copied
from a machine-generated artifact and is traceable to it; where the two ever disagree, the
generated artifact wins. The three canonical artifacts are listed under
[Provenance](#provenance) and linked at each finding.

Scope note: this file records interpretation. It changes no label, no taxonomy, no protocol and
no analysis output. Phase 1 and Phase 2 labels are sealed; the analysis artifacts under
`analysis/` and `experiments/phase2_odc_control/analysis/` are frozen research outputs.

## Current status

| Phase | State |
| --- | --- |
| Phase 1A — reproduction | **COMPLETE** |
| Phase 1B — robustness | **COMPLETE** |
| Phase 2 — ODC external-taxonomy control | **COMPLETE** (workflow state `ANALYZED`) |

**Current stage: MANUSCRIPT SYNTHESIS / OPTIONAL HUMAN VALIDATION.** No further experiment is
running. The human-validation study sketched at the end of this document is optional and has
**not** been started.

## How to read each finding

Each finding below is set out under the same seven headings, and they are deliberately not
blurred together:

- **Observed result** — what the generated artifacts actually contain.
- **Interpretation** — the reading we are prepared to defend, in the wording we prefer.
- **Potential contribution** — what, if anything, is publishable in it.
- **Known prior work** — what part of it is already established elsewhere.
- **Limitations** — what bounds the observation.
- **Claims we should NOT make** — the specific overreaches this finding invites.
- **Possible next validation** — what would strengthen it. Recorded, not scheduled.

---

## Finding 1 — the AIDev-derived taxonomy transfers poorly to SWE-smith

### Observed result

Source: [`../analysis/taxonomy_transfer/headline_results.md`](../analysis/taxonomy_transfer/headline_results.md).

On AIDev, the corpus the taxonomy was derived from:

| Level | n | agreement | rate | Cohen's κ |
| --- | ---: | ---: | ---: | ---: |
| fine label | 49 | 31 | 63.3% | 0.5827814570 |
| broad family | 49 | 36 | 73.5% | 0.6575268817 |

On 100 SWE-smith cases, with the same frozen taxonomy and the same frozen fine → family
mapping:

| Level | n | agreement | rate | Cohen's κ |
| --- | ---: | ---: | ---: | ---: |
| fine label | 100 | 41 | 41.0% | 0.2535425101 |
| broad family | 100 | 41 | 41.0% | 0.2420349435 |

The two populations are not structurally comparable: the AIDev figures cover the 49 of 100
reviewed cases where *both* reviewers assigned a technical pattern, the SWE-smith figures cover
all 100 frozen cases, because the SWE-smith review schema has no `UNASSIGNED` value. Both
definitions must always be stated together.

Phase 1B confirmed that the gap is not an artefact of that denominator choice and is not
dissolved by sampling uncertainty. Recomputing AIDev over all 100 reviewed PRs with the source
study's own all-100 rule gives 65/100 (65.0%, κ 0.5531154239), still far above SWE-smith's
41/100. The bootstrap κ intervals of the two corpora do not overlap under either AIDev
denominator. Source:
[`../analysis/taxonomy_transfer/phase1b_robustness/robustness_report.md`](../analysis/taxonomy_transfer/phase1b_robustness/robustness_report.md).

### Interpretation

> An agent-failure taxonomy derived from real coding-agent repair attempts transfers
> substantially less reproducibly to static SWE-smith bugs than it performs on the source
> domain from which it was developed.

That is a statement about the instrument's behaviour across two domains. It is not a statement
about the SWE-smith bugs themselves.

### Potential contribution

On its own, very little. It is the setup for Findings 3 and 4, and its value is that it is a
clean, hash-verified, independently recomputed measurement rather than a reported one.

### Known prior work

That taxonomies may fail to generalise across domains, and that defect classifications require
reliability validation before use, are established concerns in software-engineering measurement
research. Nothing in this finding is new as a *concept*. (Related-work traditions to cite are
listed under [Related-work positioning](#related-work-positioning); citations for them are not
yet verified in this repository.)

### Limitations

- Two reviewers only, both LLMs; agreement is reproducibility, not correctness.
- The broad-family mapping was developed from AIDev disagreement data, so the AIDev
  family-level number is partly in-sample while the SWE-smith one is out-of-sample.
- Language and corpus type are fully confounded: every SWE-smith task is Python, AIDev is
  multilingual.
- The bootstrap intervals of the two corpora do not overlap, but a non-overlap of two separate
  intervals is a weaker statement than a test of the difference, and no cross-corpus test of
  that difference was run — the two populations are not comparable enough to support one.

See [`threats_to_validity.md`](threats_to_validity.md) for the full list.

### Claims we should NOT make

- That this shows SWE-smith is unrealistic. It does not, and a low agreement figure under one
  instrument is not evidence about the bugs.
- That the AIDev-derived taxonomy is a bad taxonomy. Nothing here bears on its validity for its
  original purpose.

### Possible next validation

Human annotators applying the same frozen taxonomy to a stratified subset, to see whether the
transfer drop is a property of the instrument or of LLM reviewers. See
[Optional validation](#optional-validation--not-started).

---

## Finding 2 — procedural SWE-smith bugs looked especially incompatible under the agent-failure taxonomy

### Observed result

Source: [`../analysis/generation_method/agreement_by_generation.md`](../analysis/generation_method/agreement_by_generation.md)
and the Phase 1B report.

Under the AIDev-derived broad-family taxonomy:

| Group | n | agreement | rate |
| --- | ---: | ---: | ---: |
| procedural | 34 | 6 | 17.6% |
| nonprocedural (`llm + mirror + combine`) | 66 | 35 | 53.0% |

The difference is 35.4 percentage points (signed, procedural minus nonprocedural: −35.4),
Newcombe 95% CI [15.6, 50.2] on the absolute difference. Phase 1B reports a two-sided Fisher's
exact test p = 0.00063232, odds ratio 0.189796, risk ratio 0.3328. Dropping the two `combine`
cases leaves the gap at 37.0 points.

### Interpretation

> Reviewer agreement was lower among procedurally generated cases under the AIDev-derived
> taxonomy.

That is an association between a generation family and a reviewer-agreement indicator, measured
under one instrument.

### Potential contribution

It identifies the subgroup that Finding 4 later inverts. Its interest is almost entirely in
being the thing that does not survive a change of instrument.

### Known prior work

Synthetic and mutation-derived faults are known to differ from organic faults in ways that
affect downstream analysis. That procedural mutants are the most mechanical and the least
narrative of the SWE-smith families is unsurprising in itself.

### Limitations

- The Fisher and permutation tests are **exploratory association tests** on one contrast that
  was written down after the Phase 1A subgroup results were known. No multiplicity correction,
  no confirmatory status.
- Generation family may correlate with other uncontrolled task properties (repository, diff
  size, test structure).
- `combine` has n = 2 and supports no conclusion.

### Claims we should NOT make

- **Not:** procedural generation causes poor agreement.
- **Not:** procedural SWE-smith bugs are inherently unrealistic.

### Possible next validation

The same subgroup contrast under a second instrument — which is exactly what Phase 2 did, and
what Finding 4 reports.

---

## Finding 3 — ODC substantially improves reproducibility on the same SWE-smith bugs

### Observed result

Sources: [`../experiments/phase2_odc_control/analysis/odc_agreement.md`](../experiments/phase2_odc_control/analysis/odc_agreement.md)
and [`../experiments/phase2_odc_control/analysis/taxonomy_comparison.md`](../experiments/phase2_odc_control/analysis/taxonomy_comparison.md).

Phase 2 held fixed: the same 100 SWE-smith cases, the same evidence packets (verified byte for
byte against the frozen snapshot manifest), the same two reviewer families, and the same
independent blind review design. The variable that changed was the measurement taxonomy — from
the AIDev-derived agent-failure taxonomy to the Defect Type dimension of IBM's Orthogonal Defect
Classification.

| Taxonomy | n | agreement | rate | Cohen's κ |
| --- | ---: | ---: | ---: | ---: |
| Phase 1 AIDev-derived, broad family (primary comparator) | 100 | 41 | 41.0% | 0.2420 |
| Phase 2 ODC Defect Type | 100 | 60 | 60.0% | 0.5131 |

Paired difference: **+19 percentage points**. Exact two-sided McNemar on the discordant pairs
(b = 20, c = 39): **p = 0.0183**. Paired case-level bootstrap, 10,000 replicates, seed 20260906:

| Statistic | point estimate | 95% percentile interval |
| --- | --- | --- |
| ODC agreement − Phase 1 agreement | +0.190 | [0.040, 0.330] |
| ODC κ − Phase 1 κ | +0.2711 | [0.1118, 0.4255] |

Read against the pre-registered interpretation matrix and its pre-stated thresholds, this is
Outcome A.

### Interpretation

> A substantial portion of the poor Phase 1 transfer appears attributable to a construct
> mismatch between an agent-process-oriented taxonomy and static synthetic software defects.

The pre-registered reading of Outcome A is phrased the same way in the frozen protocol, which
is where it was fixed before any Phase 2 case was seen.

### Potential contribution

This is the controlled half of the project's strongest result: a same-cases, same-evidence,
same-reviewers instrument swap, with a paired analysis, pre-registered thresholds and a frozen
protocol. The design — not the direction of the difference — is what makes it worth reporting.

### Known prior work

That measurement instruments differ in reliability, and that a classification scheme must be
validated on the units it will be applied to, is established. ODC itself is a 1992 scheme with
a long reliability literature behind it (cited in
[`../experiments/phase2_odc_control/taxonomy/SOURCE_PROVENANCE.md`](../experiments/phase2_odc_control/taxonomy/SOURCE_PROVENANCE.md);
the wider reliability literature is a **TODO: verify citation**).

### Limitations

- Only the Defect Type dimension of ODC is used. This is not a test of ODC as a measurement
  programme.
- `UNCLASSIFIABLE` is a study-level sentinel, not an ODC type; κ over nine values is not κ over
  eight.
- The nine tie-break rules are this study's operationalisation, frozen in advance but still a
  choice; a different ordering could produce different agreement.
- Still two reviewers, both LLMs, and the same two families in both taxonomies — which is what
  makes the comparison paired, and also means any shared disposition of these two reviewers is
  common to both arms rather than controlled.

### Claims we should NOT make

- That ODC is "correct", "ground truth", or an answer key. It is an independent, pre-existing,
  mechanism-neutral scheme; that is the whole of the claim made for it.
- That the higher ODC agreement makes SWE-smith realistic.

### Possible next validation

A second independent external taxonomy, or human annotators under both instruments. Neither is
scheduled.

---

## Finding 4 — the procedural pattern reverses under ODC

This is currently the most interesting empirical result in the project.

### Observed result

Source: [`../experiments/phase2_odc_control/analysis/taxonomy_comparison.md`](../experiments/phase2_odc_control/analysis/taxonomy_comparison.md)
§11–§12 and
[`../experiments/phase2_odc_control/analysis/generation_method_analysis.csv`](../experiments/phase2_odc_control/analysis/generation_method_analysis.csv).

| Group | AIDev-derived taxonomy | ODC Defect Type |
| --- | ---: | ---: |
| procedural | 6/34 = 17.6% | 26/34 = 76.5% |
| nonprocedural | 35/66 = 53.0% | 34/66 = 51.5% |

Per generation family, under ODC:

| Generation family | n | agreement | rate | Cohen's κ |
| --- | ---: | ---: | ---: | ---: |
| llm | 36 | 23 | 63.9% | 0.5320 |
| mirror | 28 | 11 | 39.3% | 0.2145 |
| procedural | 34 | 26 | 76.5% | 0.6304 |
| combine | 2 | 0 | 0.0% | 0.0000 |

`combine` has n = 2 and is not interpreted.

The procedural gap (nonprocedural rate minus procedural rate) is **+0.3538** under the Phase 1
taxonomy and **−0.2496** under ODC. The paired bootstrap of the change in that gap (seed
[20260906, 2], 10,000 replicates) is **−0.6034, 95% interval [−0.8762, −0.3125]**.

So the subgroup that looked dramatically hardest to classify under the agent-derived taxonomy
became the highest-agreement meaningful generation family under ODC.

### Interpretation

In explanatory prose we describe this transparently:

> The Phase 1 procedural deficit disappeared and reversed direction under ODC.

The pre-registered Phase 2 decision rule words the same observation as

> the procedural agreement gap substantially narrowed under ODC

and that frozen wording is not altered. The two are not in conflict: the protocol permits only
two phrasings, and the report itself records that the applicable one "should be read as 'no
procedural deficit remained', not as a claim that a deficit shrank by a measured amount". The
explanatory sentence above is the descriptively accurate one and is the one to use outside a
direct quotation of the pre-registered rule.

No causal reading is implied in either direction.

### Potential contribution

This is the sharpest available demonstration that the *apparent scientific conclusion* about a
bug-generation mechanism — not merely the labels assigned — depends on which measurement
instrument is used. A subgroup ranking does not merely shift; it inverts.

### Known prior work

That different schemes yield different labels is known and is not the point. Whether an
instrument swap has been shown to invert a subgroup conclusion on the same synthetic
coding-agent cases is the part we believe is not established — flagged as a working novelty
claim below, requiring literature verification.

### Limitations

- One synthetic dataset, one external taxonomy, two LLM reviewer families.
- Subgroup sizes are modest (procedural 34, llm 36, mirror 28); the intervals are wide.
- The generation-family contrast is the same pre-registered exploratory contrast in both arms;
  it carries no multiplicity correction and no confirmatory status.
- The reversal is a change in reproducibility, not a change in anything about the bugs.

### Claims we should NOT make

- That ODC proves procedural bugs resemble real bugs.
- That procedural mutations cause reviewer disagreement, or that they stopped causing it.
- That procedural mutations are good, or bad.

### Possible next validation

Human annotators on a stratified subset under both taxonomies, asking only whether the same
qualitative taxonomy-dependent procedural pattern appears. See
[Optional validation](#optional-validation--not-started).

---

## Finding 5 — ODC did not eliminate annotation ambiguity

Recorded because it is what prevents Finding 3 from being overclaimed.

### Observed result

Source: [`../experiments/phase2_odc_control/analysis/odc_agreement.md`](../experiments/phase2_odc_control/analysis/odc_agreement.md).

| Endpoint | n | agreement | rate | Cohen's κ |
| --- | ---: | ---: | ---: | ---: |
| ODC defect type | 100 | 60 | 60.0% | 0.5131 |
| `taxonomy_fit` | 100 | 56 | 56.0% | 0.1861 |

Reviewer ambiguity and sentinel rates:

| Reviewer | AMBIGUOUS | UNCLASSIFIABLE |
| --- | ---: | ---: |
| claude | 57/100 | 0 |
| codex | 21/100 | 0 |

Label usage differs markedly between the two reviewers:

| ODC defect type | claude | codex |
| --- | ---: | ---: |
| `FUNCTION` | 8 | 0 |
| `BUILD_PACKAGE_MERGE` | 1 | 13 |
| `INTERFACE` | 16 | 30 |
| `ASSIGNMENT` | 28 | 18 |
| `ALGORITHM` | 28 | 21 |

### Interpretation

> ODC provided broader and more reproducible structural coverage of the SWE-smith bugs, but its
> category boundaries remained subjective for many cases.

Neither reviewer ever reached for the `UNCLASSIFIABLE` sentinel, so every case was describable
by some ODC type; the disagreement is about *which* type, not about whether the scheme applies.
The `taxonomy_fit` κ of 0.1861 says the two reviewers largely did not agree about *when* a case
was ambiguous, which is itself part of the finding.

### Potential contribution

It bounds the result honestly and supplies the "and yet" the manuscript needs: 60% agreement is
a large improvement and still a long way from a settled instrument.

### Known prior work

That defect classification schemes leave substantial residual subjectivity, and that ODC in
particular requires training and calibration to apply consistently, is established in the ODC
reliability literature (**TODO: verify citation**).

### Limitations

- One reviewer flagged ambiguity nearly three times as often as the other; the two ambiguity
  rates are not interchangeable measures of case difficulty.
- `pattern_confidence` is descriptive only and was used for nothing.
- Neither the tie-break rules nor the sentinel are part of published ODC.

### Claims we should NOT make

- That ODC solved the classification problem.
- That the remaining 40% disagreement measures how ambiguous the bugs "really" are.

### Possible next validation

Whether human annotators show the same asymmetry in ambiguity flagging, and whether a
calibration round closes it.

---

## Distinguishing the known lesson from the promising result

The following are **already known** in software-engineering research and must not be presented
as this project's contribution:

- taxonomy choice matters;
- defect classifications require reliability validation;
- taxonomies may fail to generalise across domains;
- synthetic bugs can differ from organic bugs;
- agent process information differs from final code outcomes.

Therefore we do not claim:

> We discovered that different taxonomies can produce different conclusions.

That is too broad and is not novel. Nor:

> We are the first to show that failure process and software defect are different concepts.

Also too broad.

## What appears promising

The potentially publishable contribution is the **controlled empirical result**:

> We hold the synthetic cases, evidence, reviewer families, and blind-review protocol fixed and
> change the measurement taxonomy from an AIDev-derived coding-agent failure taxonomy to an
> independent software-defect taxonomy. This increases inter-reviewer agreement from 41% to 60%
> and κ from 0.242 to 0.513. More strikingly, the procedural SWE-smith subset changes from the
> lowest-agreement subgroup under the agent-derived taxonomy (17.6%) to the highest-agreement
> meaningful subgroup under ODC (76.5%).

The distinction that carries the paper is:

- **not** "different taxonomies give different labels";
- **but** "changing the taxonomy changes the apparent scientific conclusion about a
  bug-generation mechanism".

## Candidate contribution statement

**Conservative version.**

> Prior software-engineering work has established that defect taxonomies require reliability and
> applicability validation. We show that this concern has concrete consequences in modern
> coding-agent training-data analysis: on identical SWE-smith cases, an agent-derived failure
> taxonomy and an independent software-defect taxonomy produce substantially different
> inter-reviewer reproducibility and opposite procedural-generation patterns.

**Compact version.**

> We provide evidence that conclusions about synthetic coding-bug generation can depend strongly
> on whether the measurement instrument targets agent failure processes or resulting software
> defects.

No "first" language is used. The preferred novelty wording is:

> To our knowledge, prior work has not tested this specific controlled taxonomy swap on the same
> synthetic coding-agent training cases while holding reviewers and evidence fixed.

**That sentence is a working novelty claim and requires final literature verification before
publication.** It must not appear in a submitted manuscript until the related-work traditions
below have actually been searched.

## Why this could matter: a methodological implication

A common analysis structure in this area is:

```text
choose taxonomy
        ↓
classify real dataset
classify synthetic dataset
        ↓
compare category distributions
        ↓
make claims about realism / coverage
```

Our results suggest an additional check may be necessary:

```text
choose taxonomy
        ↓
test whether the taxonomy behaves reproducibly
on each unit of analysis
        ↓
only then compare distributions
```

The concern is that apparent differences between datasets may partially reflect **measurement /
construct mismatch** rather than only **underlying bug-distribution differences**.

This does **not** mean that prior synthetic-bug comparisons are invalid, and we do not claim it.
The implication is phrased as:

> Our results motivate taxonomy-transfer validation as a methodological check when comparing
> agent-process failures with static software defects.

## Failure process vs code-state consequence

A framing worth preserving, though **the distinction itself is not novel**:

```text
FAILURE PROCESS
Why/how did the coding agent fail?

Examples:
- false premise
- bad diagnosis
- incomplete propagation
- failed verification
- unverified trial-and-error


CODE-STATE CONSEQUENCE
What is wrong with the resulting software?

Examples:
- assignment defect
- checking defect
- interface defect
- algorithm defect
```

Real coding-agent trajectory data can potentially support **failure process + code-state
consequence**. Static synthetic bug datasets generally support primarily **code-state
consequence**.

The framing is useful for exposition. The empirical evidence for what happens when the two are
conflated is the more interesting contribution, and it is the part that should carry weight.

## Known limitations

Recorded as a list, deliberately blunt:

```text
1 synthetic dataset: SWE-smith
1 independent external defect taxonomy: ODC
2 reviewer families: Claude and Codex
100 SWE-smith cases
AIDev primary technical-pattern denominator = 49
no human validation yet
no ground-truth taxonomy labels
agreement measures reproducibility, not correctness
ODC is old/general and not specifically designed for modern coding-agent data
```

Also:

```text
higher agreement != greater realism
higher agreement != better training data
higher agreement != greater downstream utility
```

The project does **not** establish whether SWE-smith improves agents more or less than other
data. Further caveats: [`threats_to_validity.md`](threats_to_validity.md).

## Publication-strength assessment

Stated candidly:

> The project appears sufficient for a focused empirical/workshop paper.

The reasons are:

- a coherent multi-stage experimental arc;
- frozen provenance;
- independent dual reviews;
- robustness analysis;
- an external taxonomy control;
- a paired comparison;
- a strong procedural reversal.

However:

> The generality of the finding remains limited by the use of one synthetic dataset, one
> external taxonomy, and two LLM reviewers.

The current result is not a universal law and must not be written up as one.

## OPTIONAL VALIDATION — NOT STARTED

The highest-value optional next step, recorded here so that it is not reinvented. **It has not
been launched, nothing has been prepared for it, and it is deliberately not numbered as a
phase.**

### Human validation

Potential design:

```text
24–30 SWE-smith cases
stratified across:

LLM
PR mirror
procedural
```

Two human annotators would independently apply both instruments:

```text
AIDev-derived taxonomy
ODC
```

Primary question:

> Does the same qualitative taxonomy-dependent procedural pattern appear with human annotators?

This is likely more valuable than adding many more taxonomies, adding random additional
SWE-smith cases, inventing a taxonomy v2, or starting a training experiment.

```text
OPTIONAL VALIDATION — NOT STARTED
```

Running it would be a new, explicitly versioned experiment with its own directory under
`experiments/`, its own inputs and its own write-up, and it would require explicit authorization
from the study owner. It would modify no Phase 1 or Phase 2 label.

## Current manuscript narrative

The intended flow of the write-up.

### Study 1

Derive and freeze a coding-agent failure taxonomy from AIDev.

### Study 2

Apply it unchanged to SWE-smith. Observation:

```text
agreement drops substantially
procedural cases appear especially problematic
```

### Robustness

Show that this is not explained by the denominator choice or by simple sampling uncertainty.

### External control

Apply ODC to the exact same SWE-smith cases. Observation:

```text
overall reproducibility increases
procedural deficit disappears and reverses
```

### Conclusion

The apparent relationship between synthetic bug-generation mechanism and classification
reliability is not stable across measurement instruments. Therefore:

> Researchers comparing coding-agent failures with static synthetic bugs should distinguish
> failure-process constructs from software-defect constructs and validate taxonomy transfer
> before interpreting cross-dataset differences.

## Claims and framing to avoid

The list below is binding for any write-up, abstract, slide or README paragraph produced from
this project.

### The explicit do-not-claim list

Do NOT claim:

```text
"SWE-smith is unrealistic"

"SWE-smith is realistic"

"ODC is the correct taxonomy"

"our taxonomy is bad"

"procedural mutations are good"

"procedural mutations are bad"

"procedural mutations cause reviewer disagreement"

"ODC proves procedural bugs resemble real bugs"

"taxonomy choice matters" as the novel contribution

"we are the first to distinguish agent failures from software defects"

"higher agreement means higher-quality training data"

"we proved prior synthetic-bug papers are wrong"
```

The Phase 2 protocol carries its own list of what the experiment does not establish
([`../experiments/phase2_odc_control/protocol/phase2_protocol.md`](../experiments/phase2_odc_control/protocol/phase2_protocol.md)
§14); both lists apply.

## Related-work positioning

The final manuscript's related-work section must acknowledge at least these research
traditions:

```text
ODC / defect classification reliability
cross-domain taxonomy validation
mutation testing / synthetic-vs-real fault representativeness
BugPilot
ScaleSWE
coding-agent failure-process / trajectory analysis
```

Citation status in this repository:

- **ODC** is cited with DOI in
  [`../experiments/phase2_odc_control/taxonomy/SOURCE_PROVENANCE.md`](../experiments/phase2_odc_control/taxonomy/SOURCE_PROVENANCE.md)
  (Chillarege et al., *IEEE TSE* 18(11):943–956, 1992, DOI `10.1109/32.177364`). Reference that
  file rather than retyping the citation.
- **The two source studies** are cited in the root [`../README.md`](../README.md) with their
  repository URLs and pinned commits.
- **ODC reliability / inter-rater studies** — TODO: verify citation.
- **Cross-domain taxonomy validation** — TODO: verify citation.
- **Mutation testing / synthetic-vs-real fault representativeness** — TODO: verify citation.
- **BugPilot** — TODO: verify citation.
- **ScaleSWE** — TODO: verify citation.
- **Coding-agent failure-process / trajectory analysis** — TODO: verify citation.

No citation may be invented to fill one of those TODOs.

The manuscript should position this work as

> an empirical extension of established measurement-validity concerns into coding-agent
> synthetic training-data analysis

rather than as

> invention of taxonomy reliability as a research concept.

## Provenance

The current Phase 2 result is frozen at repository commit
`f2fa59187571350d93ea5d82e6a5bef80bc82ccf`, which is the commit recorded in the provenance
block of both Phase 2 reports.

The Phase 1 source pins are unchanged:

| Study | Repository | Pinned commit |
| --- | --- | --- |
| AIBugAnalysis | <https://github.com/MachineLearningAmateur/AIBugAnalysis> | `85e4bf9caf0a63436a1a305592d82294536ccd8e` |
| SWE-Smith-Bug-Analysis | <https://github.com/MachineLearningAmateur/SWE-Smith-Bug-Analysis> | `0345139bf449f1fe9401f2a708d0d3b5961d14b2` |

Per-file hashes for every imported artifact are in [`provenance.md`](provenance.md).

### The canonical artifacts

These three generated files are the numerical source of truth. No number in this document may
be edited without re-reading them, and none of them may be edited by hand.

- [`../experiments/phase2_odc_control/analysis/odc_agreement.md`](../experiments/phase2_odc_control/analysis/odc_agreement.md)
- [`../experiments/phase2_odc_control/analysis/taxonomy_comparison.md`](../experiments/phase2_odc_control/analysis/taxonomy_comparison.md)
- [`../analysis/taxonomy_transfer/phase1b_robustness/robustness_report.md`](../analysis/taxonomy_transfer/phase1b_robustness/robustness_report.md)

The Phase 1A headline figures come from
[`../analysis/taxonomy_transfer/headline_results.md`](../analysis/taxonomy_transfer/headline_results.md)
and [`../analysis/generation_method/agreement_by_generation.md`](../analysis/generation_method/agreement_by_generation.md).
