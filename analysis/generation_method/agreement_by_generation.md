# Agreement by synthetic bug-generation family

Recomputed from the imported sealed SWE-smith labels. The generation crosswalk was withheld from both reviewers and is joined only after the labels are loaded.

- Crosswalk: `data/swesmith/hidden/sample_metadata.csv`
- Crosswalk sha256: `0ef1a5720f9f2a24caefb5abf7076fbf636d027a1dfe54d90f3307180fde84a1`
- Mapping authority: materialised method_family column, produced by SWE-Smith-Bug-Analysis@ssr/swesmith.py::method_family()

## Frozen broad-family mapping (the published level)

| Generation family | n | exact agreement | rate | Cohen's kappa | kappa (4 dp) |
| --- | ---: | ---: | ---: | ---: | ---: |
| combine | 2 | 0 | 0.0% | 0.0000000000 | 0.0 |
| llm | 36 | 20 | 55.6% | 0.2975609756 | 0.2976 |
| mirror | 28 | 15 | 53.6% | 0.3933333333 | 0.3933 |
| procedural | 34 | 6 | 17.6% | 0.1274060495 | 0.1274 |
| **pooled (all cases)** | 100 | 41 | 41.0% | 0.2420349435 | 0.242 |

## Fine-grained taxonomy (for completeness, NOT the published level)

| Generation family | n | exact agreement | rate | Cohen's kappa | kappa (4 dp) |
| --- | ---: | ---: | ---: | ---: | ---: |
| combine | 2 | 0 | 0.0% | 0.0000000000 | 0.0 |
| llm | 36 | 20 | 55.6% | 0.3364055300 | 0.3364 |
| mirror | 28 | 15 | 53.6% | 0.3933333333 | 0.3933 |
| procedural | 34 | 6 | 17.6% | 0.1274060495 | 0.1274 |
| **pooled (all cases)** | 100 | 41 | 41.0% | 0.2535425101 | 0.2535 |

Each subgroup kappa uses that subgroup's own marginals, not the pooled marginals.

## Generation methods behind each family

- **combine**: `combine_file` (2)
- **llm**: `lm_rewrite` (36)
- **mirror**: `pr_mirror` (28)
- **procedural**: `func_pm_ctrl_shuffle` (12), `func_pm_remove_assign` (5), `func_pm_ctrl_invert_if` (5), `func_pm_remove_cond` (3), `func_pm_class_rm_funcs` (2), `func_pm_class_rm_base` (2), `func_pm_remove_wrapper` (1), `func_pm_op_change` (1), `func_pm_op_change_const` (1), `func_pm_op_swap` (1), `func_pm_remove_loop` (1)

## Caveats

- The broad-family mapping was developed from AIDev disagreement data (analysis/taxonomy/family_mapping_analysis.md in the source study). The AIDev family-level agreement is therefore partly IN-SAMPLE and is not an out-of-sample estimate. The SWE-smith family-level agreement is the out-of-sample application of the same frozen mapping.
- The two populations are NOT structurally comparable. The AIDev metrics are computed on the 49 cases where both reviewers assigned a technical pattern; the SWE-smith metrics are computed on all 100 cases, because the SWE-smith review schema has no UNASSIGNED value.
- Agreement measures reproducibility between two LLM reviewers. It is not a measure of correctness.
- The combine generation family has n = 2 and is not interpretable. Its agreement and kappa are reported only for completeness.
- The per-generation-family kappas reported as the headline are FAMILY-LEVEL. The fine-level values are listed beside them and differ (notably for llm).
