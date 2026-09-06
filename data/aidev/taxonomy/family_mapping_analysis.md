# Pattern-family mapping analysis

Status: **REVIEWED AND FROZEN AS TAXONOMY v1 (2026-08-29).** This document
records how the proposal was derived and what the review decided. The
canonical frozen record is `frozen_failure_taxonomy_v1.md`; the
machine-readable mapping is `proposed_pattern_families.yaml`.

Review decisions: the CONTRACT_VIOLATION merge was **dropped** (single
observed pair); masked_symptom inside REPOSITORY_UNDERSTANDING was
**accepted**; the code-state precedence rule was **adopted** for future
reviews. Frozen mapping result: 36/49 (73.5%), Cohen's κ = 0.6575.

## Method

Both sealed reviews were joined by `case_id`
(`scripts/analyze_dual_reviews.py`). Among the 49 cases where both reviewers
assigned an actual technical pattern (i.e. neither side is `UNASSIGNED`),
there are 31 exact agreements and 18 disagreements. The mapping proposal was
built from the empirical disagreement matrix
(`analysis/dual_review/pattern_confusion.csv`,
`pattern_disagreement_pairs.csv`), then applied deterministically to both
reviewers' original labels (`scripts/apply_pattern_families.py`). No case was
re-classified and no reviewer output was modified.

Merge rule (from the calibration protocol): a merge requires **both**
repeated empirical disagreement and conceptual justification. Merges were not
added merely to raise kappa.

## Disagreement structure (symmetric pair counts, n = 18)

| Label pair | Count |
|---|---:|
| false_premise_about_existing_code ↔ masked_symptom_instead_of_fixing | 2 |
| misdiagnosed_root_cause ↔ masked_symptom_instead_of_fixing | 2 |
| false_premise_about_existing_code ↔ vacuous_verification | 2 |
| incomplete_change_propagation ↔ vacuous_verification | 2 |
| false_premise_about_existing_code ↔ misdiagnosed_root_cause | 1 |
| misdiagnosed_root_cause ↔ vacuous_verification | 1 |
| misdiagnosed_root_cause ↔ broke_existing_contract_or_behavior | 1 |
| misdiagnosed_root_cause ↔ unverified_trial_and_error | 1 |
| false_premise_about_existing_code ↔ unverified_trial_and_error | 1 |
| false_premise_about_existing_code ↔ incomplete_change_propagation | 1 |
| false_premise_about_existing_code ↔ violated_project_constraint_or_convention | 1 |
| broke_existing_contract_or_behavior ↔ violated_project_constraint_or_convention | 1 |
| unverified_trial_and_error ↔ violated_project_constraint_or_convention | 1 |
| violated_project_constraint_or_convention ↔ disproportionate_or_duplicative_solution | 1 |

Two structures stand out:

1. **A diagnosis triangle.** `false_premise_about_existing_code`,
   `misdiagnosed_root_cause`, and `masked_symptom_instead_of_fixing` are
   confused with each other 5 times (2 + 2 + 1), including both repeated
   pairs that involve `masked_symptom`. In every one of these cases (003,
   015, 033, 037, 074) the two reviewers describe the same evidence and the
   same defect; one names the wrong belief about the code (the cause) and the
   other names the symptom-suppressing patch that resulted (the effect).
2. **A facet conflict between process labels and code-state labels.** 8 of
   the 18 disagreements (016, 017, 018, 023, 048, 049, 050, 067) pair a
   verification-process label (`vacuous_verification`,
   `unverified_trial_and_error`) on one side with a code-state label on the
   other. These are not label-adjacency confusions: most failed PRs exhibit
   both a defective code state and false or absent verification claims, and
   the reviewers disagreed about which facet is primary. Notably,
   `vacuous_verification` and `unverified_trial_and_error` are **never
   confused with each other** (0 pairs).

## Evaluation of candidate mappings

| Mapping | Agreement (n = 49) | Cohen's κ | Disagreements resolved |
|---|---:|---:|---:|
| Fine-grained labels (no mapping) | 31 (63.3%) | 0.5828 | — |
| Handoff starting hypothesis | 33 (67.3%) | 0.5571 | 2 |
| Full proposal (with CONTRACT_VIOLATION) | 37 (75.5%) | 0.6766 | 6 |
| **Frozen v1 (CONTRACT_VIOLATION dropped at review)** | **36 (73.5%)** | **0.6575** | **5** |

The starting hypothesis (REPOSITORY_UNDERSTANDING without `masked_symptom`,
CHANGE_CONSISTENCY with `incomplete_change_propagation`, REPAIR_VERIFICATION,
standalone SYMPTOM_LEVEL_FIX) is **not supported by the data**: it resolves
only cases 001 and 037, and its Cohen's κ (0.5571) is *below* the
fine-grained κ, because it merges high-agreement labels without absorbing the
actual confusion pairs.

## Adopted merges

### REPOSITORY_UNDERSTANDING = {false_premise_about_existing_code, misdiagnosed_root_cause, masked_symptom_instead_of_fixing}

- **Disagreements resolved:** 5 of 18 (cases 003, 015, 033, 037, 074).
- **Empirical support:** the two most frequent disagreement pairs (2 + 2)
  plus the 1 false_premise ↔ misdiagnosed pair all lie inside this family.
- **Conceptual overlap:** all three labels describe a repair grounded in an
  incorrect model of the existing code or defect. `masked_symptom` is the
  characteristic patch shape produced by a misdiagnosis; reviewers reliably
  detect the phenomenon but split on whether to label the mistaken belief or
  its downstream patch.
- **Interpretability lost:** the cause (wrong belief about code / wrong root
  cause) vs. effect (symptom suppressed) distinction, and the distinction
  between a factual false premise and an incorrect causal diagnosis. All are
  preserved in the retained fine-grained labels.

### CONTRACT_VIOLATION = {broke_existing_contract_or_behavior, violated_project_constraint_or_convention} — PROPOSED, THEN DROPPED AT REVIEW

- **Disagreements resolved:** 1 of 18 (case 001).
- **Empirical support:** one observed pair only. This merge is therefore the
  **weakest** in the proposal and is flagged as scientifically questionable
  (see below).
- **Conceptual overlap:** both labels describe a change that conflicts with
  something the repository already guarantees — a behavioral/API contract or
  an explicit project constraint. Case 001 (a public-API breaking change) is
  simultaneously both, and the labels are near-synonymous for API-stability
  constraints.
- **Interpretability lost:** whether the conflicted guarantee was a runtime
  behavior/contract or a project policy/convention.
- **Review outcome (2026-08-29): DROPPED.** The single observed pair does
  not meet the repeated-disagreement criterion. In frozen v1 the two labels
  are separate single-member families (BROKEN_CONTRACT,
  CONSTRAINT_VIOLATION), and case 001 remains a disagreement.

## Rejected merges

- **REPAIR_VERIFICATION** (`vacuous_verification` +
  `unverified_trial_and_error`): resolves **0** disagreements — the two
  labels were never confused with each other. Fails the empirical criterion;
  not adopted. Each remains a single-member family.
- **`incomplete_change_propagation` into a CHANGE_CONSISTENCY family:**
  `incomplete_change_propagation` has **0** disagreements with
  `broke_existing_contract_or_behavior` or
  `violated_project_constraint_or_convention`; its confusions are with
  `vacuous_verification` (2) and `false_premise` (1), which are cross-facet
  conflicts, not adjacency. Merging it would cost interpretability and
  resolve nothing. It remains a single-member family
  (INCOMPLETE_PROPAGATION).
- **Standalone SYMPTOM_LEVEL_FIX family:** contradicted by the data — all 4
  of `masked_symptom`'s disagreements are with the two understanding labels.
- **Any merge across the process/code-state boundary** (e.g. absorbing
  `vacuous_verification` into code-state families to capture its 5
  cross-facet disagreements): rejected. It would collapse the repair-process
  vs. code-state distinction that `failure_scope` exists to carry, and would
  be a clear case of merging distinct categories to raise kappa.

## Residual disagreements (13 cases under frozen v1)

After the frozen mapping, 13 of 49 cases still disagree:

- **8 facet-priority cases** (016, 017, 018, 023, 048, 049, 050, 067): a
  verification-process label vs. a code-state label, as described above.
- **5 diffuse one-off cases** (001, 004, 022, 027, 028): singleton
  cross-family pairs; no repeated structure justifies further merging
  (001 rejoined this group when the CONTRACT_VIOLATION merge was dropped).

**Recommendation for the frozen taxonomy (decision rule, not a merge):** for
future reviews, add an explicit precedence rule — when the evidence supports
both a code-state pattern and a verification-process pattern, assign the
code-state pattern as `failure_pattern` and record the verification problem
via `failure_scope` / `verification_level` (or a dedicated boolean facet).
This rule cannot be applied retroactively to the sealed reviews (it would
require re-classification), so the 8 facet cases remain disagreements in
this calibration; they are listed in
`analysis/dual_review/pattern_family_disagreements.csv`.

## Review decisions (2026-08-29)

1. CONTRACT_VIOLATION merge: **dropped** (single observed pair; failed the
   repeated-disagreement criterion).
2. REPOSITORY_UNDERSTANDING including `masked_symptom_instead_of_fixing`:
   **accepted** (strongest empirical support in the data).
3. Code-state-precedence decision rule for future reviews: **adopted**
   (recorded in `frozen_failure_taxonomy_v1.md`; not applied retroactively
   to the sealed reviews).
