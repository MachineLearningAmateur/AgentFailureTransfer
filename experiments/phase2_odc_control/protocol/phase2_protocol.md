# Phase 2 — ODC external-taxonomy control: pre-registered protocol

**Status: SETUP.** This protocol is written and frozen before any Phase 2 case is reviewed. No
Phase 2 review has been run. Nothing in this file may be revised once the freeze commit exists;
a change after that point is a protocol amendment and must be recorded as one.

Phase 2 is a **measurement control experiment**. It re-measures the same 100 frozen SWE-smith
cases with a different instrument. It does not relabel, reinterpret or modify anything from
Phase 1.

> **No Phase 1 reviewer classification is modified during Phase 2.** The Phase 1 sealed labels
> are read-only inputs to the paired comparison and to nothing else.

## 1. Purpose: two explanations Phase 1 cannot separate

Phase 1 established that the frozen AIDev-derived failure taxonomy transferred much less
reproducibly to SWE-smith than to AIDev, with especially low agreement on procedural SWE-smith
mutations.

But the AIDev taxonomy was created from *real coding-agent repair failures*, and several of its
labels depend on an agent's process, beliefs, diagnosis or verification behavior. A static
synthetic bug state has none of those. So Phase 1 alone is consistent with two explanations:

**Explanation A — measurement mismatch.** The AIDev taxonomy is a useful taxonomy of
coding-agent failures, but it is the wrong measuring instrument for static synthetic bugs.

**Explanation B — synthetic-bug difficulty / mismatch.** Even under an independent code-defect
taxonomy, SWE-smith bugs — especially procedural mutations — remain difficult to classify
reproducibly.

Phase 2 introduces an external taxonomy control to distinguish them.

### Motivating Phase 1 numbers

Cited here only as motivation. Under the AIDev-derived taxonomy the two blind reviewers agreed
on 41 of the 100 SWE-smith cases (41.0%) at both levels, with broad-family κ 0.2420 and
fine-label κ 0.2535; agreement was 6/34 among procedurally generated cases against 35/66 among
nonprocedural cases.

**These figures are not hard-coded anywhere in the Phase 2 analysis.** The analysis script loads
them from the frozen Phase 1 artifacts, exactly as `scripts/reproduce_headline_results.py` and
`scripts/run_phase1b_robustness.py` do. Quoting them in prose is a convenience for the reader;
computing from a quoted number would be a defect.

## 2. Research questions

**RQ3**

> Does an independent mechanism-neutral software-defect taxonomy yield higher inter-reviewer
> reproducibility on the same SWE-smith cases than the AIDev-derived agent-failure taxonomy?

**RQ4**

> Under the external taxonomy, does reviewer agreement still vary by SWE-smith generation
> mechanism, particularly procedural versus nonprocedural generation?

These are the only new scientific questions in this phase. Phase 2 is not a coverage study, not
a taxonomy-v2 exercise, and not an adjudication.

## 3. Design

```text
same 100 cases
same evidence
same two reviewer families
same blind independence
different taxonomy
```

The taxonomy is the only deliberate difference between Phase 1 and Phase 2.

- **Cases.** The same frozen `SWESMITH_001`–`SWESMITH_100` evidence used in Phase 1. Nothing is
  resampled, rebuilt, regenerated or edited. Packets are imported read-only from the pinned
  SWE-smith source repository and verified against the frozen snapshot and review manifests; the
  importer refuses to proceed on any hash mismatch.
- **Evidence.** Substantively identical to Phase 1 — see §4.
- **Reviewers.** The same two reviewer families as Phase 1, "Claude" and "Codex", each in a
  **fresh session**. Phase 1 reviewer sessions are not continued. Note the standing caveat: the
  SWE-smith reviewer metadata names no model or provider, so "Claude" and "Codex" are reviewer
  identities in this study's sense and not claims about specific models.
- **Independence.** Each reviewer works from its own physically isolated bundle, cannot see the
  other's output, and is told nothing about Phase 1 labels, Phase 1 disagreements, or generation
  metadata. See [`blinding_protocol.md`](blinding_protocol.md).
- **Taxonomy.** The frozen ODC Defect Type rubric, `odc_defect_type_v1`
  ([`../taxonomy/odc_defect_type_v1.md`](../taxonomy/odc_defect_type_v1.md)), with the
  study-level `UNCLASSIFIABLE` sentinel. Selection rationale and limits in
  [`external_taxonomy_selection.md`](external_taxonomy_selection.md).

### Provenance of this phase

Phase 2 is branched from the tip of the Phase 1B branch `analysis/phase1b-robustness` at
commit `e68d2329120de4724ee600eda55cc0cd1953fb4f` (a README summary of the Phase 1 findings,
whose parent `0d1250a79a1546cf220cdec6beea3a29585e09bb` is the Phase 1B robustness-analysis
commit), on branch `experiment/phase2-odc-control`. It is not branched from an older Phase 1A
commit. The freeze tag `phase2-odc-pre-review-frozen` does
**not** exist yet; it is created only at freeze time (§8) and is never moved afterwards.

## 4. Evidence equivalence

The evidence a Phase 2 reviewer sees must be substantively identical to what a Phase 1 reviewer
saw. Each reviewer may see:

- the neutral `SWESMITH_nnn` case ID;
- the repository/code context already present in the frozen packet;
- `BUG_DIFF`;
- the specification;
- the failing-test evidence;
- `REFERENCE_REPAIR`.

Nothing else. The following must **not** be exposed to a reviewer, in any file, path, filename
or string:

- the Phase 1 Claude label;
- the Phase 1 Codex label;
- Phase 1 agreement/disagreement status;
- the AIDev taxonomy category;
- the AIDev broad family;
- the generation method;
- the generation family;
- the source model;
- the trajectory;
- the attempt count;
- the population frequency;
- the hidden instance mapping;
- any previous analysis output.

The packets' own `reviewer_question` string is taxonomy-neutral and is carried through
unchanged; the ODC framing is supplied by the rubric and the reviewer prompt, not by editing
evidence.

## 5. Reviewer isolation

Because this repository now contains Phase 1 results, **the Phase 2 reviewers are not run in the
full repository checkout.** Each reviewer works in a physically isolated bundle generated
outside the repository by `scripts/make_phase2_review_bundle.py` from the frozen commit.

A bundle contains only:

```text
ODC reviewer instructions
frozen ODC taxonomy
review schema
validator
the 100 frozen evidence packets
review manifest / packet hashes
empty reviewer output directory
```

A bundle must physically exclude:

```text
Phase 1 reviewer labels
Phase 1 reports
generation metadata
hidden sample mapping
other reviewer's Phase 2 output
AIDev data
cross-corpus analysis
```

The bundle creator scans for forbidden paths and content and **refuses to export a contaminated
bundle**. Both bundles are generated from the same frozen commit. Details, stop conditions and
the preflight hash check are in [`blinding_protocol.md`](blinding_protocol.md).

## 6. Reviewer output

Both reviewers record the same six semantic fields, in the serialization format that reviewer
already uses in this study's convention:

```text
codex  -> reviews/codex/cases/SWESMITH_nnn.json
claude -> reviews/claude/cases/SWESMITH_nnn.yaml
```

Fields, and no others:

| Field | Content |
| --- | --- |
| `case_id` | the packet's `SWESMITH_nnn` id |
| `odc_defect_type` | one ODC Defect Type, or the sentinel |
| `taxonomy_fit` | `DIRECT`, `AMBIGUOUS` or `OUT_OF_SCOPE` |
| `pattern_confidence` | `HIGH`, `MEDIUM` or `LOW` |
| `supporting_evidence_ids` | evidence IDs that exist in that packet |
| `reasoning_summary` | short, evidence-based |

Allowed `odc_defect_type`: `FUNCTION`, `INTERFACE`, `CHECKING`, `ASSIGNMENT`,
`TIMING_SERIALIZATION`, `BUILD_PACKAGE_MERGE`, `DOCUMENTATION`, `ALGORITHM`, `UNCLASSIFIABLE`.

Allowed `taxonomy_fit`: `DIRECT`, `AMBIGUOUS`, `OUT_OF_SCOPE`.

Allowed `pattern_confidence`: `HIGH`, `MEDIUM`, `LOW`.

Rules, all enforced by `scripts/validate_phase2_review.py`:

- `odc_defect_type: UNCLASSIFIABLE` requires `taxonomy_fit: OUT_OF_SCOPE`;
- `taxonomy_fit: OUT_OF_SCOPE` requires `odc_defect_type: UNCLASSIFIABLE`;
- confidence is descriptive only and is never an inclusion criterion;
- reasoning must be short and evidence-based, and must not record private chain-of-thought;
- every cited evidence ID must exist in that packet;
- no unexpected fields;
- no duplicate case IDs.

Each reviewer finalises to `reviews/<reviewer>/review_results.jsonl` plus
`review_metadata.json` and a `COMPLETE` marker, and only after all 100 per-case records exist
and validate.

## 7. Workflow states

| State | Meaning | Entered when |
| --- | --- | --- |
| `SETUP` | protocol, rubric, schema, scripts and tests being written | now |
| `FROZEN_PRE_REVIEW` | every protocol-critical artifact hashed into the freeze manifest; pre-review commit made and tagged | §8 completes |
| `CLAUDE_COMPLETE` | the Claude bundle's 100 records validate and are finalised and sealed | Claude finalises |
| `CODEX_COMPLETE` | the Codex bundle's 100 records validate and are finalised and sealed | Codex finalises |
| `BOTH_COMPLETE` | both `COMPLETE` markers exist and both result files are sealed | both of the above |
| `ANALYZED` | `analyze_phase2_odc.py` has run and written `analysis/` | after `BOTH_COMPLETE` |

Gates:

- No bundle may be generated before `FROZEN_PRE_REVIEW`.
- No review may start before `FROZEN_PRE_REVIEW`, and none may start without explicit
  authorization from the study owner.
- `CLAUDE_COMPLETE` and `CODEX_COMPLETE` are independent and may occur in either order; neither
  reviewer's output may become visible to the other before that other reviewer is complete.
- **The analysis script refuses to run before `BOTH_COMPLETE`.** Generation metadata and Phase 1
  labels may not be joined to any ODC label before that point.

## 8. Freeze procedure

Before either reviewer begins, hash every protocol-critical artifact and record the hashes in a
machine-readable freeze manifest:

```text
phase2_protocol.md
external_taxonomy_selection.md
blinding_protocol.md
odc_defect_type_v1.md
odc_defect_type_v1.yaml
review result schema
review manifest
review snapshot manifest
all 100 packet files
reviewer prompts
```

SHA-256 for each. Then make the pre-review commit and create the tag:

```text
phase2-odc-pre-review-frozen
```

The tag is created **only at freeze time** and is never moved afterwards. Both reviewer bundles
are generated from that exact commit. If any preflight hash differs from the freeze manifest, no
review is launched — that is a stop condition, not something to re-hash past.

Before the freeze, the workflow is exercised end to end on **toy records that are not among
`SWESMITH_001`–`SWESMITH_100`** (`TOY_nnn` ids), to check serialization, validation, bundle
isolation, `COMPLETE` markers, aggregation and the analysis scripts. Study cases are never used
to debug tooling or to tune the rubric, and toy outputs are never written under
`experiments/phase2_odc_control/reviews/`.

## 9. Primary endpoints

After both reviews are sealed, compute across all 100 cases:

- ODC exact agreement;
- ODC Cohen's κ;
- the ODC confusion matrix;
- ODC taxonomy-fit agreement;
- the `UNCLASSIFIABLE` rate per reviewer;
- the `AMBIGUOUS` rate per reviewer.

The primary comparison is against the **Phase 1 AIDev-derived broad-family result on the same
100 SWE-smith cases**, with the fine-label result reported alongside it. Both Phase 1 values are
loaded from the frozen Phase 1 artifacts, never hard-coded into the calculation.

κ is computed with this repository's single unweighted Cohen's κ implementation (see
[`../../../docs/study_design.md`](../../../docs/study_design.md)); the Phase 2 analysis reuses
`agentfailuretransfer.agreement` and `agentfailuretransfer.stats` rather than reimplementing
them.

## 10. Paired comparison against Phase 1 (McNemar)

Both taxonomies are applied to the same 100 cases by the same two reviewer families, so the
comparison is paired and must be analysed as such. For each case define:

```text
phase1_agree = 1 if Claude and Codex agreed under the AIDev-derived family taxonomy
odc_agree    = 1 if Claude and Codex agree under ODC
```

Construct the paired table:

```text
                      ODC agree   ODC disagree
Phase1 agree              a            b
Phase1 disagree           c            d
```

Apply a **two-sided McNemar test** to the discordant counts `b` and `c`. Report:

- the Phase 1 agreement rate;
- the ODC agreement rate;
- the paired absolute difference;
- the McNemar discordant counts;
- the two-sided p-value.

**An unpaired test must not be used for the main taxonomy comparison.**

## 11. Paired bootstrap

Add a paired case-level bootstrap:

```text
seed        = 20260906
replicates  = 10000
```

Resample the same case IDs with replacement, and within each resampled case preserve all four
labels together:

```text
Phase 1 Claude label
Phase 1 Codex label
ODC Claude label
ODC Codex label
```

For each replicate compute:

```text
ODC agreement - Phase 1 agreement
ODC kappa     - Phase 1 family kappa
```

Report percentile 95% intervals. If κ is undefined for a replicate, **count and report those
replicates rather than replacing them with zero** — the same rule Phase 1B uses, for the same
reason: a degenerate resample carries no information about κ and folding it in as `0.0` moves
the interval by an artefact of the degenerate rule.

Pairing the resample is the point. Treating the two κ values as independent samples would
overstate the uncertainty of their difference.

## 12. Generation-family analysis — only after `BOTH_COMPLETE`

**Only after both ODC reviews are `COMPLETE`** may ODC labels be joined to the hidden SWE-smith
generation metadata. This is the same discipline Phase 1 used: the crosswalk is joined after the
labels are sealed, never before.

Reproduce the four families `llm`, `mirror`, `procedural`, `combine`, and for each report:

- `n`;
- ODC exact agreement;
- ODC κ;
- the taxonomy-fit distribution;
- `UNCLASSIFIABLE` counts.

`combine` has n = 2 and supports no substantive claim. Report it for completeness and draw
nothing from it.

### Procedural vs nonprocedural

Use the same frozen grouping as Phase 1B:

```text
procedural
vs
nonprocedural = llm + mirror + combine
```

and report the sensitivity contrast `procedural` vs `llm + mirror` only. Compute agreement
rates, the absolute rate difference, the risk ratio, the odds ratio, a two-sided Fisher exact
test, and Wilson confidence intervals for the group agreement rates. This answers whether the
procedural agreement problem survives the taxonomy change.

### Comparing the procedural effect across taxonomies

Descriptively compare the procedural agreement, the nonprocedural agreement and the procedural
gap under each taxonomy. If it is straightforward, estimate the change in the gap with a paired
bootstrap over cases; if the implementation becomes fragile, drop it rather than complicate it.

No causal claim is made either way. The permitted phrasings are:

> the procedural subset remained associated with lower reviewer agreement.

or:

> the procedural agreement gap substantially narrowed under ODC.

depending on the observed data. These remain exploratory association tests on one contrast, with
no multiplicity correction, exactly as in Phase 1B.

## 13. Interpretation matrix

**The conclusion is not decided in advance.** The four outcomes below are pre-registered so that
whichever is observed, the reading of it was fixed beforehand. Each is conditional; none is
predicted.

### Outcome A — ODC agreement much higher, procedural gap narrows substantially

> Phase 1's poor transfer was substantially attributable to a construct mismatch between an
> agent-process taxonomy and static synthetic bugs.

Do **not** conclude that SWE-smith is fully realistic.

### Outcome B — ODC agreement much higher, procedural still much worse than nonprocedural

> The agent-process taxonomy contributed to the Phase 1 transfer failure, but procedural
> mutations retain an additional classification mismatch even under an independent defect
> taxonomy.

This would be the most informative outcome, and also the one most easily overstated.

### Outcome C — ODC agreement remains near Phase 1 levels

> Replacing the AIDev-derived taxonomy with an independent generic defect taxonomy does not
> resolve the reproducibility problem, which weakens the explanation that Phase 1 was only a
> taxonomy-design artifact.

Do **not** conclude from this that SWE-smith is "bad".

### Outcome D — ODC agreement is worse

> ODC itself may be poorly suited to these modern repair tasks, and no claim about SWE-smith
> realism follows without additional controls.

So that the reading is applied mechanically rather than chosen after the fact,
`scripts/analyze_phase2_odc.py` maps the observed numbers onto the matrix with the following
pre-stated rule, which it prints in full in every report. Let *d* be the ODC exact agreement
rate minus the Phase 1 family exact agreement rate, and let each taxonomy's procedural gap be
its nonprocedural agreement rate minus its procedural agreement rate.

- "much higher" requires all three of: *d* ≥ 0.15; the paired-bootstrap 95% interval for *d*
  excluding 0; and the exact two-sided McNemar p-value below 0.05;
- "worse" requires all three of: *d* ≤ −0.10; that interval excluding 0; and that p-value
  below 0.05;
- anything else is read as Outcome C. C is the default; an inconclusive result is never
  promoted to A, B or D;
- within "much higher", the procedural gap decides A from B: the gap counts as substantially
  narrowed when the ODC gap is at most 0.10 and at most half the Phase 1 gap (if the Phase 1
  gap was already at most 0.10, only the 0.10 test applies). Otherwise the reading is B. The
  same test selects which of the two permitted §12 phrasings is used.

These thresholds are stated before any Phase 2 label exists and encode no preferred outcome.
The boundaries between these outcomes are otherwise qualitative. The quantitative results —
the paired difference, the McNemar p-value, the bootstrap intervals, the per-family rates — are
reported in full regardless of which outcome they are read as, and the reader can disagree with
the reading without disagreeing with the numbers.

## 14. What Phase 2 does not establish

Regardless of outcome, none of the following may be claimed:

- that ODC is ground truth;
- that higher inter-reviewer agreement means greater real-world realism;
- that SWE-smith is good or bad overall;
- that procedural mutations cause poor downstream model performance;
- that ODC categories are the correct training-data distribution;
- that SWE-smith lacks a particular real-agent failure family;
- that training utility equals failure realism;
- that the AIDev taxonomy is invalid for its original purpose.

Agreement measures reproducibility between two reviewers applying one scheme. It does not
measure correctness, and no ground truth exists for these cases. Phase 2 is a measurement
control experiment and nothing more. Further caveats are in
[`../../../docs/threats_to_validity.md`](../../../docs/threats_to_validity.md).

## 15. Standing rules for this phase

- **No Phase 1 reviewer classification is modified.** Phase 1 labels are read-only inputs to the
  paired comparison.
- **No case-level Phase 1 inspection while building the ODC rubric.** During Phase 2 setup, the
  per-case Phase 1 SWE-smith classifications must not be inspected in order to decide how ODC
  should be operationalised. In particular the rubric must not be tuned around Claude's old
  labels, Codex's old labels, Claude `OTHER` cases, false-premise disagreements, or procedural
  cases known to disagree. Aggregate Phase 1 findings are already known and may be cited as
  motivation; case-level Phase 1 labels must not influence the Phase 2 rubric. Loading those
  labels programmatically inside the analysis script, after both reviews are sealed, is a
  different thing and is permitted.
- **The source repositories remain read-only.** Packet import reads the pinned SWE-smith source
  and never writes to it.
- **No review without authorization.** Neither the Claude nor the Codex review may be launched
  without explicit authorization from the study owner, after the setup report has been reviewed.
- **Stop rather than repair.** Every provenance ambiguity is a hard stop with a report, not a
  silent fix. The stop conditions are listed in [`blinding_protocol.md`](blinding_protocol.md).

## 16. Reporting

After both reviews complete, `scripts/analyze_phase2_odc.py` writes
`../analysis/odc_agreement.md` and `../analysis/taxonomy_comparison.md`, covering: motivation;
why ODC was selected; the exact frozen ODC operationalisation; packet/evidence equivalence;
reviewer blinding; ODC agreement; the Phase 1 vs ODC paired comparison; the McNemar result; the
paired bootstrap intervals; the ODC confusion matrix; the generation-family analysis; the
procedural/nonprocedural analysis; the `UNCLASSIFIABLE`/`AMBIGUOUS` analysis; limitations; the
interpretation read through §13; and provenance with hashes.

The report states explicitly:

> No Phase 1 reviewer classification was modified during Phase 2.
