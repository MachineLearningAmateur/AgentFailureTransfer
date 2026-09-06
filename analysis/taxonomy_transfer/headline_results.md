# Headline taxonomy-transfer results

Recomputed from the imported sealed reviewer labels by `scripts/reproduce_headline_results.py`. No value here is read out of a source-study report, and no reviewer label was reinterpreted.

- Taxonomy version: `aidev_failure_taxonomy_v1`
- Family mapping sha256: `1ce7232047437f87e7116d84b369e4f820e854481cbc744faf3b1d4c1af60985`
- Kappa: unweighted Cohen's kappa, hand-rolled, expected agreement over the union of both raters' observed labels; reported at full precision and rounded to 4 dp. Degenerate rule: expected agreement == 1.0 (or n == 0) yields 0.0 unless observed agreement is 1.0, in which case 1.0.

## Fine-grained taxonomy

The 11 frozen fine-grained failure patterns, exactly as sealed.

| Corpus | n | exact agreement | rate | Cohen's kappa | kappa (4 dp) |
| --- | ---: | ---: | ---: | ---: | ---: |
| AIDev (real coding-agent repair attempts) | 49 | 31 | 63.3% | 0.5827814570 | 0.5828 |
| SWE-smith (synthetic training bugs) | 100 | 41 | 41.0% | 0.2535425101 | 0.2535 |

## Frozen broad-family mapping

The same sealed fine labels mapped deterministically through the frozen `fine -> family` mapping. Neither reviewer re-classified anything.

| Corpus | n | exact agreement | rate | Cohen's kappa | kappa (4 dp) |
| --- | ---: | ---: | ---: | ---: | ---: |
| AIDev (real coding-agent repair attempts) | 49 | 36 | 73.5% | 0.6575268817 | 0.6575 |
| SWE-smith (synthetic training bugs) | 100 | 41 | 41.0% | 0.2420349435 | 0.242 |

## Inclusion rules

- **AIDev (real coding-agent repair attempts)** (49 cases): both reviewers assigned a technical pattern (failure_pattern != "UNASSIGNED" on both sides)
  - source of the rule: `AIBugAnalysis@scripts/analyze_dual_reviews.py (both_pattern)`
- **SWE-smith (synthetic training bugs)** (100 cases): all frozen cases; the SWE-smith review schema has no UNASSIGNED value, so no exclusion rule applies
  - source of the rule: `SWE-Smith-Bug-Analysis@scripts/apply_frozen_families.py (no filtering)`

## Caveats

- The broad-family mapping was developed from AIDev disagreement data (analysis/taxonomy/family_mapping_analysis.md in the source study). The AIDev family-level agreement is therefore partly IN-SAMPLE and is not an out-of-sample estimate. The SWE-smith family-level agreement is the out-of-sample application of the same frozen mapping.
- The two populations are NOT structurally comparable. The AIDev metrics are computed on the 49 cases where both reviewers assigned a technical pattern; the SWE-smith metrics are computed on all 100 cases, because the SWE-smith review schema has no UNASSIGNED value.
- Agreement measures reproducibility between two LLM reviewers. It is not a measure of correctness.
- The combine generation family has n = 2 and is not interpretable. Its agreement and kappa are reported only for completeness.
- The per-generation-family kappas reported as the headline are FAMILY-LEVEL. The fine-level values are listed beside them and differ (notably for llm).

## Derived reconstructions

`data/derived/aidev_both_assigned_case_ids.json` and `data/derived/aidev_strict_code_state_case_ids.json` restate which imported cases satisfy the two source-study inclusion rules (49 and 35 cases respectively). They are derived from imported labels, not new classifications. Coverage of the strict corpus is deliberately not analysed here.
