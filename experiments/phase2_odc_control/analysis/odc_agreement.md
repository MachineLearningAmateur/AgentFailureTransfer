# Phase 2 ODC external-taxonomy control — ODC agreement

Inter-reviewer agreement on the same frozen SWE-smith cases under the ODC Defect Type dimension. Sections follow the pre-registered report outline; sections owned by the companion report link to it.

No Phase 1 reviewer classification was modified during Phase 2.

No timestamp appears in this report. Identity is the hashes in section 16.

## 1. Motivation

Reported in full in [`taxonomy_comparison.md`](./taxonomy_comparison.md); see also the frozen protocol in [`../protocol/phase2_protocol.md`](../protocol/phase2_protocol.md).

## 2. Why ODC was selected

Reported in full in [`taxonomy_comparison.md`](./taxonomy_comparison.md); see also the frozen protocol in [`../protocol/phase2_protocol.md`](../protocol/phase2_protocol.md).

## 3. Exact frozen ODC operationalisation

The frozen rubric is [`../taxonomy/odc_defect_type_v1.md`](../taxonomy/odc_defect_type_v1.md)
with the machine-readable form beside it. The eight canonical ODC defect types,
in the frozen order, are:

1. `FUNCTION`
2. `INTERFACE`
3. `CHECKING`
4. `ASSIGNMENT`
5. `TIMING_SERIALIZATION`
6. `BUILD_PACKAGE_MERGE`
7. `DOCUMENTATION`
8. `ALGORITHM`

`UNCLASSIFIABLE` is a **study-level sentinel and is not an ODC defect
type**. It records that none of the eight could be defensibly assigned from the
frozen evidence, and it is data about taxonomy applicability rather than a
reviewer failure. `taxonomy_fit` takes `DIRECT`, `AMBIGUOUS`, `OUT_OF_SCOPE`, with the two-way rule
`UNCLASSIFIABLE` if and only if `OUT_OF_SCOPE`. `pattern_confidence`
(`HIGH`, `MEDIUM`, `LOW`) is
descriptive only and was not used for inclusion, weighting or any estimate.

The operational tie-breaking guidance is this study's operationalisation of the
published ODC types, not a modification of ODC, and it was frozen before any
Phase 2 case was seen.

Taxonomy fingerprint: `4fb66187d3aa949e70d65251404b00373cbe3529a14e901086026d7e998b2e96`

## 4. Packet and evidence equivalence

Phase 2 showed the reviewers the same frozen evidence packets Phase 1 showed
them: the same bytes, verified file by file and digest by digest against the
same frozen snapshot manifest. No case was resampled, no bug was rebuilt and no
specification was regenerated.

- packets: 100 (`STUDY` corpus)
- snapshot manifest sha256: `981694c07ffcc9ee9bcf00527d71a0c94b15884ebfc7d8aa537363b3f646a6de`
- review manifest sha256: `64e607800de2a08e4321b371d616841bbd4fbe6deaddb1321dfd355333caebfa`

Import and verification: [`../data/IMPORT_PROVENANCE.json`](../data/IMPORT_PROVENANCE.json).

## 5. Reviewer blinding

Each reviewer worked in a physically isolated bundle generated outside this
repository from the frozen pre-review commit, containing only the ODC
instructions, the frozen rubric, the schema, the validator, the evidence
packets and its own empty output directory. Phase 1 labels, Phase 1 reports,
generation metadata, the hidden sample mapping, the other reviewer's output and
all AIDev data were physically excluded, and the exporter refuses to publish a
bundle that contains any of them. Reviewer write boundaries are enforced in
code: a reviewer can only write under its own `reviews/<reviewer>/`.

Details: [`../protocol/blinding_protocol.md`](../protocol/blinding_protocol.md).

## 6. ODC agreement

Across all 100 cases, under the ODC Defect Type taxonomy:

| endpoint | n | agreements | rate | 95% CI | Cohen's kappa |
| --- | --- | --- | --- | --- | --- |
| ODC defect type | 100 | 60 | 60.0% | [0.5020, 0.6906] | 0.5131 |
| taxonomy_fit | 100 | 56 | 56.0% | [0.4623, 0.6533] | 0.1861 |

Intervals are Wilson score intervals. Cohen's kappa is this repository's
single unweighted implementation, the same one Phase 1A and Phase 1B use.

Per-reviewer label distributions over the frozen order:

| ODC defect type | claude | codex |
| --- | --- | --- |
| `FUNCTION` | 8 | 0 |
| `INTERFACE` | 16 | 30 |
| `CHECKING` | 17 | 11 |
| `ASSIGNMENT` | 28 | 18 |
| `TIMING_SERIALIZATION` | 2 | 6 |
| `BUILD_PACKAGE_MERGE` | 1 | 13 |
| `DOCUMENTATION` | 0 | 1 |
| `ALGORITHM` | 28 | 21 |
| `UNCLASSIFIABLE` | 0 | 0 |

## 7. Phase 1 vs ODC paired comparison

Reported in full in [`taxonomy_comparison.md`](./taxonomy_comparison.md); see also the frozen protocol in [`../protocol/phase2_protocol.md`](../protocol/phase2_protocol.md).

## 8. McNemar result

Reported in full in [`taxonomy_comparison.md`](./taxonomy_comparison.md); see also the frozen protocol in [`../protocol/phase2_protocol.md`](../protocol/phase2_protocol.md).

## 9. Paired bootstrap intervals

Reported in full in [`taxonomy_comparison.md`](./taxonomy_comparison.md); see also the frozen protocol in [`../protocol/phase2_protocol.md`](../protocol/phase2_protocol.md).

## 10. ODC confusion matrix

Rows are **claude**, columns are **codex**, over the
full frozen label set in the frozen order. The machine-readable copy is
[`odc_confusion.csv`](./odc_confusion.csv).

| claude \ codex | `FUNCTION` | `INTERFACE` | `CHECKING` | `ASSIGNMENT` | `TIMING_SERIALIZATION` | `BUILD_PACKAGE_MERGE` | `DOCUMENTATION` | `ALGORITHM` | `UNCLASSIFIABLE` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `FUNCTION` | 0 | 4 | 0 | 1 | 0 | 2 | 0 | 1 | 0 |
| `INTERFACE` | 0 | 12 | 0 | 0 | 0 | 4 | 0 | 0 | 0 |
| `CHECKING` | 0 | 5 | 10 | 0 | 1 | 1 | 0 | 0 | 0 |
| `ASSIGNMENT` | 0 | 2 | 0 | 17 | 1 | 5 | 1 | 2 | 0 |
| `TIMING_SERIALIZATION` | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 |
| `BUILD_PACKAGE_MERGE` | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| `DOCUMENTATION` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `ALGORITHM` | 0 | 7 | 1 | 0 | 2 | 0 | 0 | 18 | 0 |
| `UNCLASSIFIABLE` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

The diagonal is the exact-agreement count reported in section 6.

## 11. Generation-family analysis

Reported in full in [`taxonomy_comparison.md`](./taxonomy_comparison.md); see also the frozen protocol in [`../protocol/phase2_protocol.md`](../protocol/phase2_protocol.md).

## 12. Procedural vs nonprocedural analysis

Reported in full in [`taxonomy_comparison.md`](./taxonomy_comparison.md); see also the frozen protocol in [`../protocol/phase2_protocol.md`](../protocol/phase2_protocol.md).

## 13. UNCLASSIFIABLE and AMBIGUOUS analysis

`UNCLASSIFIABLE` is a study-level sentinel, not an ODC defect type,
and is not a reviewer failure: it is the measurement of how often none of the
eight canonical types could be defensibly assigned from the frozen evidence.
`AMBIGUOUS` records that more than one type was plausible while a best primary
type was still selected.

| reviewer | n | UNCLASSIFIABLE | rate | 95% CI | AMBIGUOUS | rate | 95% CI |
| --- | --- | --- | --- | --- | --- | --- | --- |
| claude | 100 | 0 | 0.0% | [0.0000, 0.0370] | 57 | 57.0% | [0.4722, 0.6627] |
| codex | 100 | 0 | 0.0% | [0.0000, 0.0370] | 21 | 21.0% | [0.1417, 0.2998] |

`pattern_confidence` distribution, descriptive only and used for nothing:

| reviewer | HIGH | MEDIUM | LOW |
| --- | --- | --- | --- |
| claude | 40 | 59 | 1 |
| codex | 93 | 7 | 0 |

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

Reported in full in [`taxonomy_comparison.md`](./taxonomy_comparison.md); see also the frozen protocol in [`../protocol/phase2_protocol.md`](../protocol/phase2_protocol.md).

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

