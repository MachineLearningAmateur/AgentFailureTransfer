# Dual-review calibration report

Two independent blind reviews (Codex, Claude) classified the same 100 frozen
AIDev PR evidence packets under the same rubric. This report measures how
reproducibly they agreed, where they systematically diverged, and what that
implies for the failure taxonomy to be frozen for the later SSR comparison.

All numbers are computed deterministically from the immutable review files by
`scripts/analyze_dual_reviews.py` and `scripts/apply_pattern_families.py`;
machine-readable values are in `agreement_metrics.json`. No SSR/SWE-smith
data was used or consulted.

## 1. Top-level outcome agreement

- Exact agreement: **81 / 100** (81.0%), Cohen's κ = **0.7141**.
- Perfect agreement on all 20 merged PRs.
- All 19 disagreements lie inside {TECHNICAL_FAILURE_EVIDENCE,
  NONTECHNICAL_REJECTION, UNCLEAR}; matrix in `outcome_confusion.csv`,
  listing in `outcome_disagreements.csv`.

## 2. Binary technical-defect judgment

`technical_defect_evidence` := outcome ∈ {TECHNICAL_FAILURE_EVIDENCE,
MERGED_AFTER_HUMAN_CORRECTION}.

- Exact agreement: **85 / 100** (85.0%), Cohen's κ = **0.6914**.
- Consensus: **BOTH_YES = 51**, BOTH_NO = 34, **DISPUTED = 15**.
- The 51 BOTH_YES cases form
  `data/derived/aidev_consensus_technical_cases.parquet`; the 15 disputed
  cases are preserved separately in
  `data/derived/aidev_disputed_technical_cases.parquet` and are excluded from
  primary analysis (sensitivity use only).
- Disputed direction is roughly balanced: Codex defect-yes in 6, Claude
  defect-yes in 9.

## 3. Fine-grained failure pattern

Among the 49 cases where both reviewers assigned a technical pattern:

- Exact agreement: **31 / 49** (63.3%), Cohen's κ = **0.5828**.
- Confusion matrix: `pattern_confusion.csv`; ranked pairs:
  `pattern_disagreement_pairs.csv`.

Most frequent disagreement pairs (symmetric):

| Pair | Count |
|---|---:|
| false_premise_about_existing_code ↔ masked_symptom_instead_of_fixing | 2 |
| misdiagnosed_root_cause ↔ masked_symptom_instead_of_fixing | 2 |
| false_premise_about_existing_code ↔ vacuous_verification | 2 |
| incomplete_change_propagation ↔ vacuous_verification | 2 |
| (10 further pairs, 1 each) | 10 |

Structure of the 18 disagreements:

- **5** inside the diagnosis triangle {false_premise, misdiagnosed_root_cause,
  masked_symptom}: reviewers describe the same defect but one labels the
  wrong belief (cause) and the other the symptom-suppressing patch (effect).
- **8** facet-priority conflicts: a verification-process label
  (vacuous_verification / unverified_trial_and_error) vs. a code-state label,
  on PRs exhibiting both defective code and false verification claims.
- **5** diffuse one-off pairs (of which 1 is broke_contract ↔
  violated_constraint, merged below).

## 4. Broad pattern families (frozen as taxonomy v1, 2026-08-29)

`analysis/taxonomy/proposed_pattern_families.yaml`, frozen in
`analysis/taxonomy/frozen_failure_taxonomy_v1.md` (rationale and per-merge
accounting in `analysis/taxonomy/family_mapping_analysis.md`):

- REPOSITORY_UNDERSTANDING = {false_premise_about_existing_code,
  misdiagnosed_root_cause, masked_symptom_instead_of_fixing} — the only
  multi-member family.
- Single-member families: BROKEN_CONTRACT, CONSTRAINT_VIOLATION,
  INCOMPLETE_PROPAGATION, VACUOUS_VERIFICATION,
  UNVERIFIED_TRIAL_AND_ERROR, SOLUTION_SHAPE, BASELINE_STATE, OTHER.
- The proposed CONTRACT_VIOLATION merge (one observed pair) was dropped at
  review; a code-state precedence rule for future reviews was adopted.

The handoff's starting hypothesis (REPAIR_VERIFICATION merge, standalone
SYMPTOM_LEVEL_FIX, incomplete_change_propagation inside CHANGE_CONSISTENCY)
was tested and **rejected**: it resolves only 2 of 18 disagreements and its
κ (0.5571) falls below the fine-grained κ. vacuous_verification and
unverified_trial_and_error were never confused with each other (0 pairs).

## 5. Broad-family agreement (mapping applied to both original reviews)

- Exact agreement: **36 / 49** (73.5%), Cohen's κ = **0.6575**
  (fine-grained: 31/49 = 63.3%, κ = 0.5828).
- Resolves 5 of 18 disagreements; matrix in `pattern_family_confusion.csv`.
- Remaining 13 disagreeing cases
  (`pattern_family_disagreements.csv`): 001, 004, 016, 017, 018, 022, 023,
  027, 028, 048, 049, 050, 067 — 8 facet-priority cases and 5 diffuse
  one-offs.
  Further merging to absorb these would cross the process/code-state boundary
  or chase singletons, and was rejected. A code-state-precedence decision
  rule is instead proposed for future reviews (see
  `family_mapping_analysis.md`).

## 6. Other fields

- **Failure scope** (all 100 cases): 66% exact, κ = 0.4897; among the 51
  consensus technical cases: 32/51 (62.7%), κ = 0.2932. Nearly all scope
  disagreement is CODE_STATE vs BOTH; pure REPAIR_PROCESS is rare.
- **Verification level** (all 100 cases): 59% exact, κ = 0.4533
  (`verification_confusion.csv`). The dominant confusion is REVIEW_EVIDENCE
  (Codex) vs UNCLEAR_VERIFICATION (Claude), 20 cases — a threshold
  difference in what counts as review-grounded evidence, not a factual
  disagreement.

## 7. Corpus sizes

| Set | Rule | N |
|---|---|---:|
| Consensus technical-defect | technical_defect_consensus == BOTH_YES | **51** |
| Disputed technical-defect | consensus == DISPUTED (sensitivity only) | 15 |
| Consensus code-state | BOTH_YES and both scopes ∈ {CODE_STATE, BOTH} | **48** |
| Strict RQ1 primary (frozen v1) | code-state set ∩ both patterns assigned ∩ family agreement | **35** |

Code-state rule: CODE_STATE vs BOTH counts as compatible; a REPAIR_PROCESS or
UNKNOWN scope on either side excludes the case (excluded: 018, 019, 092).
`data/derived/aidev_rq1_primary_cases.parquet` was generated under frozen
taxonomy v1 with 35 cases. Family distribution:
REPOSITORY_UNDERSTANDING 16, INCOMPLETE_PROPAGATION 5, CONSTRAINT_VIOLATION
5, UNVERIFIED_TRIAL_AND_ERROR 3, BASELINE_STATE 2, BROKEN_CONTRACT 2,
SOLUTION_SHAPE 2.

## 8. Fields excluded for calibration reasons

- The `evidence_overstated` audit field exhibited systematic reviewer
  interpretation divergence and was excluded from subsequent analyses
  (Codex: 51 YES / 31 NO / 18 UNCLEAR; Claude: 100 NO). It is preserved
  verbatim in the joined dataset for provenance only.
- `outcome_confidence`, `pattern_confidence`, and `evidence_strength` are
  preserved descriptively but are **not** treated as calibrated across
  reviewers (Codex used HIGH substantially more often); they are not
  inclusion criteria. Externally interpretable provenance
  (`verification_level`) is preferred.

## 9. Methodological limitations

- Two reviewers only; Cohen's κ is a two-rater statistic and rare labels
  (e.g. wrong_baseline_or_branch, n = 2) make per-label κ uninterpretable —
  only aggregate κ is reported.
- The 8 facet-priority disagreements reflect a rubric ambiguity (one label
  per case despite multi-facet failures), not reviewer noise; they cannot be
  fixed retroactively without re-classification, which this calibration
  deliberately avoids.
- Both reviews used the same frozen evidence packets; agreement measures
  reproducibility of interpretation, not correctness against ground truth.
- Family-level agreement is computed on the same data used to propose the
  mapping; it is an in-sample estimate and should be validated on the next
  labeling exercise.
- No claims about SSR are made here; the taxonomy must be frozen before any
  SSR failure frequencies are examined.
