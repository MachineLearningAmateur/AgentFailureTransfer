# Phase 2 ODC external-taxonomy control — taxonomy comparison

The paired comparison of the Phase 1 AIDev-derived taxonomy and the ODC Defect Type taxonomy on the same frozen SWE-smith cases. Sections follow the pre-registered report outline; sections owned by the companion report link to it.

No Phase 1 reviewer classification was modified during Phase 2.

No timestamp appears in this report. Identity is the hashes in section 16.

## 1. Motivation

Phase 1 measured these same 100 frozen SWE-smith cases with
the frozen AIDev-derived agent-failure taxonomy and found much lower
inter-reviewer
reproducibility than the same instrument achieved on AIDev. That result is
consistent with two explanations it cannot separate: a construct mismatch
between an agent-process taxonomy and static synthetic bugs, or a difficulty
intrinsic to the synthetic bugs themselves. Phase 2 re-measures the identical
cases with an independent, mechanism-neutral defect taxonomy to distinguish
them. Full statement:
[`../protocol/phase2_protocol.md`](../protocol/phase2_protocol.md) section 1.

The Phase 1 figures this report compares against are **recomputed here from
the sealed per-case Phase 1 labels**, never copied from a previous artifact.

## 2. Why ODC was selected

The Defect Type dimension of IBM's Orthogonal Defect Classification, which
predates LLMs, coding agents, SWE-smith and AIDev, was not derived from this
study, and classifies the semantics of the defect and its correction rather
than an agent's reasoning process. Only the Defect Type dimension is used; no
trigger, activity, impact, source or age attribute is collected. Rationale and
citation:
[`../protocol/external_taxonomy_selection.md`](../protocol/external_taxonomy_selection.md)
and [`../taxonomy/SOURCE_PROVENANCE.md`](../taxonomy/SOURCE_PROVENANCE.md).

## 3. Exact frozen ODC operationalisation

Reported in full in [`odc_agreement.md`](./odc_agreement.md); see also the frozen protocol in [`../protocol/phase2_protocol.md`](../protocol/phase2_protocol.md).

## 4. Packet and evidence equivalence

Reported in full in [`odc_agreement.md`](./odc_agreement.md); see also the frozen protocol in [`../protocol/phase2_protocol.md`](../protocol/phase2_protocol.md).

## 5. Reviewer blinding

Reported in full in [`odc_agreement.md`](./odc_agreement.md); see also the frozen protocol in [`../protocol/phase2_protocol.md`](../protocol/phase2_protocol.md).

## 6. ODC agreement

Reported in full in [`odc_agreement.md`](./odc_agreement.md); see also the frozen protocol in [`../protocol/phase2_protocol.md`](../protocol/phase2_protocol.md).

## 7. Phase 1 vs ODC paired comparison

Both taxonomies were applied to the same cases by the same two reviewer
families, so the comparison is paired and is analysed as such. The Phase 1
values below are recomputed from the sealed Phase 1 per-case labels through the
frozen family mapping.

| taxonomy / level | n | agreements | rate | Cohen's kappa |
| --- | --- | --- | --- | --- |
| Phase 1 AIDev-derived, broad family (primary comparator) | 100 | 41 | 41.0% | 0.2420 |
| Phase 1 AIDev-derived, fine label (secondary) | 100 | 41 | 41.0% | 0.2535 |
| Phase 2 ODC Defect Type | 100 | 60 | 60.0% | 0.5131 |

Phase 1 recomputation cross-check: the recomputed counts and kappas reproduce the frozen Phase 1 aggregate at both levels within a tolerance of 0.0005.
The frozen aggregate file is a validation checkpoint only; none of its
recorded numbers is reproduced in this report.

No Phase 1 reviewer classification was modified during Phase 2.

## 8. McNemar result

**Primary: Phase 1 broad family vs ODC.**

|  | ODC agree | ODC disagree |
| --- | --- | --- |
| Phase 1 agree | 21 | 20 |
| Phase 1 disagree | 39 | 20 |

- Phase 1 agreement rate: 41.0%
- ODC agreement rate: 60.0%
- paired absolute difference: +0.1900
- discordant pairs: b = 20 (Phase 1 only), c = 39 (ODC only), total 59
- **exact two-sided McNemar p-value: 0.0183** (binomial test on the discordant pairs; this is the pre-registered result)
- continuity-corrected chi-square, REFERENCE ONLY: chi2 = 5.4915, df = 1, p = 0.0191

**Secondary: Phase 1 fine label vs ODC.**

|  | ODC agree | ODC disagree |
| --- | --- | --- |
| Phase 1 agree | 21 | 20 |
| Phase 1 disagree | 39 | 20 |

- Phase 1 agreement rate: 41.0%
- ODC agreement rate: 60.0%
- paired absolute difference: +0.1900
- discordant pairs: b = 20 (Phase 1 only), c = 39 (ODC only), total 59
- **exact two-sided McNemar p-value: 0.0183** (binomial test on the discordant pairs; this is the pre-registered result)
- continuity-corrected chi-square, REFERENCE ONLY: chi2 = 5.4915, df = 1, p = 0.0191

An unpaired test is not used for the taxonomy comparison. Both tests are
exploratory comparisons of two measuring instruments on the same cases; neither
is confirmatory and neither is causal evidence.

## 9. Paired bootstrap intervals

Seed 20260906, 10000 replicates, percentile bootstrap (95%), 2.5th and 97.5th.
Case ids are resampled with replacement and all four labels of a case (Phase 1
claude, Phase 1 codex, ODC claude, ODC codex) travel together, so the two
taxonomies are never treated as independent samples.

| statistic | point estimate | 95% percentile interval | replicates used |
| --- | --- | --- | --- |
| ODC agreement - Phase 1 family agreement | +0.1900 | [0.0400, 0.3300] | 10000 |
| ODC kappa - Phase 1 family kappa | +0.2711 | [0.1118, 0.4255] | 10000 |

Undefined kappa replicates: 0 (Phase 1 side 0, ODC side 0). They are counted and excluded from the interval, never replaced by zero.

Change in the procedural agreement gap between taxonomies (seed [20260906, 2], 10000 replicates): -0.6034, 95% interval [-0.8762, -0.3125], 0 undefined replicate(s) excluded.
Descriptive only; no causal claim follows.

## 10. ODC confusion matrix

Reported in full in [`odc_agreement.md`](./odc_agreement.md); see also the frozen protocol in [`../protocol/phase2_protocol.md`](../protocol/phase2_protocol.md).

## 11. Generation-family analysis

The hidden SWE-smith generation crosswalk is joined to the ODC labels **only**
after both reviews are sealed; the join function refuses below `BOTH_COMPLETE`.
The machine-readable copy is
[`generation_method_analysis.csv`](./generation_method_analysis.csv).

| generation family | n | agreements | rate | 95% CI | kappa | note |
| --- | --- | --- | --- | --- | --- | --- |
| `llm` | 36 | 23 | 63.9% | [0.4758, 0.7752] | 0.5320 |  |
| `mirror` | 28 | 11 | 39.3% | [0.2357, 0.5759] | 0.2145 |  |
| `procedural` | 34 | 26 | 76.5% | [0.6000, 0.8756] | 0.6304 |  |
| `combine` | 2 | 0 | 0.0% | [0.0000, 0.6576] | 0.0000 | no substantive claim: n = 2 carries no informative agreement estimate |

kappa is reported under the bootstrap degenerate rule: a subgroup whose kappa
is undefined shows `n/a` rather than a manufactured 0.

Taxonomy-fit distribution and sentinel counts per family and reviewer:

| generation family | reviewer | fit DIRECT | fit AMBIGUOUS | fit OUT_OF_SCOPE | UNCLASSIFIABLE |
| --- | --- | --- | --- | --- | --- |
| `llm` | claude | 15 | 21 | 0 | 0 |
| `llm` | codex | 28 | 8 | 0 | 0 |
| `mirror` | claude | 8 | 20 | 0 | 0 |
| `mirror` | codex | 21 | 7 | 0 | 0 |
| `procedural` | claude | 20 | 14 | 0 | 0 |
| `procedural` | codex | 30 | 4 | 0 | 0 |
| `combine` | claude | 0 | 2 | 0 | 0 |
| `combine` | codex | 0 | 2 | 0 | 0 |

## 12. Procedural vs nonprocedural analysis

The frozen Phase 1B grouping is reused unchanged: `procedural` against
`nonprocedural = llm + mirror + combine`, with `procedural` against
`llm + mirror` as the pre-registered sensitivity. Both taxonomies are put
through the same code path and the same estimators, so the cross-taxonomy
comparison is descriptive rather than a comparison of two methods.

| taxonomy | contrast | procedural | procedural 95% CI | comparator | comparator 95% CI | gap | Fisher p |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Phase 1 AIDev-derived family | procedural vs nonprocedural | 6/34 (17.6%) | [0.0835, 0.3351] | 35/66 (53.0%) | [0.4116, 0.6457] | +0.3538 | 0.0006 |
| Phase 1 AIDev-derived family | procedural vs llm+mirror (sensitivity) | 6/34 (17.6%) | [0.0835, 0.3351] | 35/64 (54.7%) | [0.4257, 0.6627] | +0.3704 | 0.0005 |
| Phase 2 ODC Defect Type | procedural vs nonprocedural | 26/34 (76.5%) | [0.6000, 0.8756] | 34/66 (51.5%) | [0.3971, 0.6315] | -0.2496 | 0.0185 |
| Phase 2 ODC Defect Type | procedural vs llm+mirror (sensitivity) | 26/34 (76.5%) | [0.6000, 0.8756] | 34/64 (53.1%) | [0.4107, 0.6482] | -0.2335 | 0.0299 |

Effect sizes with intervals (Newcombe risk difference, Katz risk ratio, Woolf
odds ratio) are in [`taxonomy_comparison.json`](./taxonomy_comparison.json).
The Fisher exact tests are two-sided exploratory association tests on a single
pre-registered contrast, with no multiplicity correction and no causal reading.

Procedural gap under each taxonomy (nonprocedural rate minus procedural rate):

| taxonomy | procedural | nonprocedural | gap |
| --- | --- | --- | --- |
| Phase 1 AIDev-derived family | 17.6% | 53.0% | +0.3538 |
| Phase 2 ODC Defect Type | 76.5% | 51.5% | -0.2496 |

Paired bootstrap of the change in the gap: -0.6034, 95% interval [-0.8762, -0.3125].

## 13. UNCLASSIFIABLE and AMBIGUOUS analysis

Reported in full in [`odc_agreement.md`](./odc_agreement.md); see also the frozen protocol in [`../protocol/phase2_protocol.md`](../protocol/phase2_protocol.md).

## 14. Limitations

Agreement measures reproducibility between two reviewers applying one scheme.
It does not measure correctness, and no ground truth exists for these cases.
Phase 2 is a measurement control experiment. Regardless of outcome, none of the
following is established:

- that ODC is ground truth
- that higher inter-reviewer agreement means greater real-world realism
- that SWE-smith is good or bad overall
- that procedural mutations cause poor downstream model performance
- that ODC categories are the correct training-data distribution
- that SWE-smith lacks a particular real-agent failure family
- that training utility equals failure realism
- that the AIDev taxonomy is invalid for its original purpose

Two reviewer families are not a population of reviewers; one external taxonomy
is not a survey of taxonomies; the exploratory tests here carry no multiplicity
correction; and the `combine` subgroup is too small to interpret. Further
caveats:
[`../../../docs/threats_to_validity.md`](../../../docs/threats_to_validity.md)
and [`../protocol/phase2_protocol.md`](../protocol/phase2_protocol.md) section 14.

## 15. Interpretation using the decision matrix

The four outcomes were pre-registered before any Phase 2 case was reviewed, so
that whichever was observed, the reading of it was fixed beforehand. The
thresholds below were stated in advance and are reported here as the rule that
was applied; a reader may disagree with the reading without disagreeing with
any number in this report.

**Rule applied.**

- Let d = ODC exact agreement rate - Phase 1 family exact agreement rate, and let each taxonomy's procedural gap be its nonprocedural agreement rate minus its procedural agreement rate.
- 'Much higher' requires ALL THREE of: d >= 0.15; the paired bootstrap 95% interval for d excluding 0; and the exact two-sided McNemar p-value below 0.05. Any one of them failing is not 'much higher'.
- 'Worse' requires ALL THREE of: d <= -0.10; the paired bootstrap 95% interval for d excluding 0; and the exact two-sided McNemar p-value below 0.05.
- Anything else is read as 'near Phase 1 levels' (Outcome C). C is the default: an inconclusive result is never promoted to A, B or D.
- Within 'much higher', the procedural gap decides A from B. The gap counts as substantially narrowed when the ODC gap is below 0.10 AND is at most half the Phase 1 gap; when the Phase 1 gap was already below 0.10 there is no substantial gap to narrow, and an ODC gap below 0.10 counts as narrowed. Otherwise the reading is B.
- The same 'substantially narrowed' test selects which of the two permitted procedural phrasings is used, so the phrasing and the outcome letter can never disagree with each other.
- These thresholds were stated before the data were seen. They encode no preferred outcome: they are symmetric in form, and the inconclusive reading is the default in both directions.
- the ODC gap (-0.2496) counts as substantially narrowed when it is at or below 0.1 and at or below 0.5 x the Phase 1 gap (0.3538)

**Observed inputs to the rule.**

| quantity | value |
| --- | --- |
| Phase 1 family agreement rate | 41.0% |
| ODC agreement rate | 60.0% |
| difference d | +0.1900 |
| bootstrap 95% interval for d | [0.0400, 0.3300] |
| interval excludes 0 | yes |
| exact McNemar p | 0.0183 |
| Phase 1 procedural gap | +0.3538 |
| ODC procedural gap | -0.2496 |

**Outcome A** — ODC agreement much higher; procedural gap narrows substantially.

Read through the pre-registered interpretation matrix and the thresholds stated below, the observed pattern corresponds to Outcome A. The reading is conditional on those thresholds; the numbers are reported in full regardless of it.

The pre-registered reading of this outcome is:

> Phase 1's poor transfer was substantially attributable to a construct mismatch between an agent-process taxonomy and static synthetic bugs.

On the procedural contrast, the permitted phrasing that applies is:

> the procedural agreement gap substantially narrowed under ODC.

The ODC procedural gap is not positive: the procedural subset did not show lower agreement than the nonprocedural subset under ODC. Of the two phrasings the protocol permits, only the one above is defensible here; it should be read as 'no procedural deficit remained', not as a claim that a deficit shrank by a measured amount.

No other phrasing of the procedural contrast is permitted by the protocol, and
no causal claim is made.

## 16. Provenance and hashes

PROVENANCE. Every value below is read from a file at run time; none is hard-coded. No timestamp is recorded anywhere in these artifacts: identity is the hashes below, never a clock.

| artifact | value |
| --- | --- |
| repository commit | `f2fa59187571350d93ea5d82e6a5bef80bc82ccf` |
| freeze manifest sha256 | `03e588aea367e8590410ec033dc88ade1dced9e1a087f1c7f4d1e049b8498c41` |
| taxonomy fingerprint | `4fb66187d3aa949e70d65251404b00373cbe3529a14e901086026d7e998b2e96` |
| fingerprint algorithm | sha256(utf8( sha256(taxonomy/odc_defect_type_v1.yaml) + ':' + sha256(schemas/odc_review_result.schema.json) )) |
| snapshot manifest sha256 | `981694c07ffcc9ee9bcf00527d71a0c94b15884ebfc7d8aa537363b3f646a6de` |
| review-result schema sha256 | `6f8bfef620a91d9f024703c7197a4d4288e74302f775f40193c25cc38528cb8e` |
| claude COMPLETE marker sha256 | `3ce97eb477e1669180d85a45768d4a708e70e9c3f160c1a894cc0bcb4528113e` |
| claude review_results.jsonl sha256 | `e727179f3fd444994a6726c5d7c098a9b13d27baa3589ffc08fceeb67803de6f` |
| codex COMPLETE marker sha256 | `98c93c4a85f97c44a60f7ec451795d680da51029913049d4c4f5b46c7bd2383f` |
| codex review_results.jsonl sha256 | `7281fab5a2c44e0c79cc625372817db70bbd6d87849ccbed696fa2318d23fd4a` |
| phase1_claude_review_results sha256 | `433638b95abcc5d1ef31575a62171081bf3468191a6427015ffb66c8b8e1441b` |
| phase1_codex_review_results sha256 | `2a42458ad4bc3b727ca9c373c6e917ae12dc35a155088ad0d51619724e8912c2` |
| phase1_family_mapping sha256 | `1ce7232047437f87e7116d84b369e4f820e854481cbc744faf3b1d4c1af60985` |
| phase1_generation_crosswalk sha256 | `0ef1a5720f9f2a24caefb5abf7076fbf636d027a1dfe54d90f3307180fde84a1` |
| phase1_headline_results sha256 | `11f0bc45cd954a5f92e5cecd2b9298d8796ed7527022424e7232b831b6983f5b` |
| phase1_source_manifest sha256 | `b31cb41ef584568dcd1527228cea315aedeb6023c063d455b44498b4eb5b4632` |
| Phase 1 source commit | `0345139bf449f1fe9401f2a708d0d3b5961d14b2` |

Software: Python 3.11.16, numpy 2.4.6, scipy 1.17.1.

The two source repositories are read-only scientific provenance and were not modified by this analysis. No Phase 1 reviewer classification was modified during Phase 2.

