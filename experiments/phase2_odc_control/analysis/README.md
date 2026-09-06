# Phase 2 analysis outputs

**This directory is deliberately empty.** No Phase 2 result exists: no ODC review has been run,
so there is nothing to analyse and nothing has been computed.

`scripts/analyze_phase2_odc.py` writes here, and only here, and only once the Phase 2 workflow
state reaches `BOTH_COMPLETE` — a verified freeze manifest plus two sealed reviews, each bound
to its own `review_results.jsonl` by hash. Below that state it exits 1 with a `STOP:` message
and writes nothing at all. The lock is the blinding, not a formality: joining Phase 1 labels or
the hidden generation crosswalk to ODC labels before both reviews are sealed would break the
independence the design depends on.

When it does run it writes exactly six files:

| File | Contents |
| --- | --- |
| `odc_agreement.json` | the ODC primary endpoints, per-reviewer distributions and the confusion matrix |
| `odc_agreement.md` | the ODC agreement report |
| `odc_confusion.csv` | the confusion matrix, rows = claude, columns = codex, in the frozen label order |
| `taxonomy_comparison.json` | the paired Phase 1 vs ODC comparison, bootstrap, generation families and interpretation |
| `taxonomy_comparison.md` | the taxonomy-comparison report |
| `generation_method_analysis.csv` | the per-generation-family breakdown |

The presence of `odc_agreement.json` and `taxonomy_comparison.json` is what moves the workflow
state to `ANALYZED`.

No timestamp appears in any of them. Two runs on unchanged input produce byte-identical files:
every random draw is seeded (seed 20260906, 10,000 replicates) and every collection is emitted
in a declared order, so a diff means the inputs changed.

**No Phase 1 reviewer classification is modified by any of this.** The sealed Phase 1 labels are
read-only inputs to the paired comparison, recomputed from the frozen per-case records rather
than copied from a previous artifact.

The analysis plan these files implement is pre-registered in
[`../protocol/phase2_protocol.md`](../protocol/phase2_protocol.md) sections 9–13. It was frozen
before any Phase 2 case was reviewed, including the thresholds used to read the result against
the interpretation matrix.
