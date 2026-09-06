# Phase 2 ODC review — reviewer instructions (Claude)

You are one of two independent reviewers in a measurement control experiment. You will classify
100 frozen synthetic-bug cases using one external taxonomy: the **ODC Defect Type** dimension.

Work in this bundle only. Do not leave it.

> **Do not use web access.** Do not search the internet for ODC, for any defect type, for a
> repository, for a test, or for anything else, at any point during this review. Every reviewer
> must apply the same frozen rubric; a reviewer who consults an external explanation of ODC is
> applying a different instrument, and the experiment's headline number would then measure that
> difference instead of the taxonomy. The rubric in this bundle is the complete and only source
> of ODC semantics for this review.

## Your ten obligations

1. **Read the frozen ODC rubric in full** — `taxonomy/odc_defect_type_v1.md`, all of it, once,
   before you classify anything.
2. **Run the Phase 2 preflight** before your first case:
   ```bash
   python scripts/check_phase2_ready.py --reviewer claude
   ```
   If it reports any hash mismatch or missing artifact, stop and report. Do not start.
3. **Review all 100 cases independently.** One case at a time, on its own evidence.
4. **Classify the defect using only ODC Defect Type.** No other ODC dimension is in scope, and
   no other taxonomy is in scope.
5. **Never inspect the other reviewer.** Do not look for, open, or reconstruct any file under
   another reviewer's `reviews/` directory.
6. **Never inspect Phase 1 results.** No Phase 1 label, no Phase 1 agreement status, no Phase 1
   report, no AIDev taxonomy category or family.
7. **Never inspect generation metadata.** No generation method, no generation family, no source
   model, no trajectory, no attempt count, no population frequency, no instance mapping.
8. **Validate each case immediately**, one file at a time, as described below. Never batch: a
   session that dies mid-run should lose one case, not fifty.
9. **Finalize only after all 100 cases exist and are valid.**
10. **Stop after review completion. Do not run comparative analysis.** Do not compute agreement,
    do not compare taxonomies, do not join anything to generation metadata.

**Never open the `reviews/` directory of the other reviewer, and there is no `hidden/` or
`analysis/` directory in this bundle by design.** If you find one, that is a contaminated bundle:
stop and report it rather than reading it.

You write **only** under `reviews/claude/`. Nothing else in this bundle is yours to modify — not
the packets, not the manifests, not the rubric, not the schema, not the validator.

## The task

For each case, the operational question is exactly this:

> What kind of software correction is required to repair the observed defect?

Use only the frozen evidence in that case's packet: `BUG_DIFF`, the `CODE_CONTEXT_NN` files, the
`SPECIFICATION`, the `TEST_FAILURE_NN` evidence, and `REFERENCE_REPAIR`.

Three things must be explicit.

> Do not classify what the synthetic bug generator "thought" or "intended." ODC Defect Type
> concerns the software defect and the semantics of the correction.

> BUG_DIFF introduces the bug. REFERENCE_REPAIR reverses it.

> If two ODC types seem plausible, use the frozen operational tie-breaking guidance. If no ODC
> type is defensible, use UNCLASSIFIABLE rather than forcing a fit.

The tie-breaking guidance is the nine numbered rules in the rubric. Apply them in order; the
first rule that applies decides the primary type.

`UNCLASSIFIABLE` is not a failure on your part. It is data about how far the taxonomy reaches.
Forcing a bad fit to avoid it would corrupt the measurement.

## What you record

Exactly these six fields, and no others:

| Field | Content |
| --- | --- |
| `case_id` | the packet's `SWESMITH_nnn` id |
| `odc_defect_type` | one allowed value, below |
| `taxonomy_fit` | one allowed value, below |
| `pattern_confidence` | one allowed value, below |
| `supporting_evidence_ids` | evidence IDs that actually exist in that packet |
| `reasoning_summary` | short, evidence-based justification |

Allowed `odc_defect_type`:

```text
FUNCTION
INTERFACE
CHECKING
ASSIGNMENT
TIMING_SERIALIZATION
BUILD_PACKAGE_MERGE
DOCUMENTATION
ALGORITHM
UNCLASSIFIABLE
```

Allowed `taxonomy_fit`:

```text
DIRECT
AMBIGUOUS
OUT_OF_SCOPE
```

Allowed `pattern_confidence`:

```text
HIGH
MEDIUM
LOW
```

Rules:

- `odc_defect_type: UNCLASSIFIABLE` requires `taxonomy_fit: OUT_OF_SCOPE`;
- `taxonomy_fit: OUT_OF_SCOPE` requires `odc_defect_type: UNCLASSIFIABLE`;
- confidence is descriptive only — it is never used to include, exclude or weight a case, so
  record what you actually think rather than managing the number;
- `reasoning_summary` is short and evidence-based. It is a justification, not a transcript; never
  record private chain-of-thought;
- every cited evidence ID must exist in that packet;
- no unexpected fields;
- no duplicate case IDs.

## Your output format: one YAML file per case

Write one file per case:

```text
reviews/claude/cases/SWESMITH_nnn.yaml
```

Example record — **illustrative only.** `TOY_001` is not a study case, and the values below are
not guidance about any real case:

```yaml
case_id: TOY_001
odc_defect_type: CHECKING
taxonomy_fit: DIRECT
pattern_confidence: HIGH
supporting_evidence_ids:
  - BUG_DIFF
  - CODE_CONTEXT_01
  - REFERENCE_REPAIR
reasoning_summary: >-
  The bug diff removes the bounds guard before the lookup, and the reference repair
  restores exactly that guard; the correction is validation logic.
```

## Validating and finalising

Validate immediately after writing each case:

```bash
python scripts/validate_phase2_review.py --reviewer claude --case SWESMITH_nnn
```

Fix anything it rejects before moving to the next case.

When all 100 cases exist and validate, and only then:

```bash
python scripts/validate_phase2_review.py --reviewer claude --finalize
```

That seals the review: it builds `reviews/claude/review_results.jsonl`, writes
`review_metadata.json`, and writes the `COMPLETE` marker. It refuses if any case is missing or
invalid, or if the snapshot manifest hash has changed since the review started.

**Then stop.** Report that the review is complete. Do not run any comparative analysis, do not
look at the other reviewer, and do not attempt to interpret the result.

## Stop and report if

- the preflight reports a hash mismatch or a missing artifact;
- a packet is missing, unreadable, or does not match its recorded hash;
- you find a Phase 1 label, a Phase 1 report, generation metadata, an instance mapping, AIDev
  data, a `hidden/` directory, an `analysis/` directory, or the other reviewer's output anywhere
  in this bundle;
- you are asked to write outside `reviews/claude/`;
- the rubric seems to need a new tie-break rule.

The last one especially: the rubric is frozen. If it fits a case badly, record that through
`UNCLASSIFIABLE` and `taxonomy_fit` and move on. Do not amend the rubric, and do not invent a
tenth rule.
