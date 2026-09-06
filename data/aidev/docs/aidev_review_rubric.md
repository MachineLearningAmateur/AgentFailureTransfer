# Canonical AIDev review rubric

Version: 1.0

This is the sole canonical classification rubric for both independent reviewers. Assign only what the frozen evidence defensibly supports. Rejection alone is not evidence of technical failure, and merger alone is not proof of correctness. Prefer `UNCLEAR` and `UNASSIGNED` over guessing or force-fitting.

## Top-level outcome

Assign exactly one.

### `TECHNICAL_FAILURE_EVIDENCE`

Concrete evidence shows that the coding agent's implementation contained a technical defect. Acceptable support includes issue-specific execution, named CI/test failure attributable to the patch, a maintainer/reviewer explanation of the defect, a clear substantive corrective commit, or comparably strong external evidence. Do not infer this simply from rejection.

### `MERGED_NO_OBSERVED_CORRECTION`

The PR merged and the available evidence does not show a substantive human correction of the agent implementation. This does not claim that the fix was proven correct.

### `MERGED_AFTER_HUMAN_CORRECTION`

The coding agent produced an implementation, a human subsequently made a substantive change that corrected it, and the PR then merged. Formatting, documentation-only cleanup, lockfile noise, merge commits, and unrelated edits do not qualify.

### `NONTECHNICAL_REJECTION`

The PR was closed or rejected for a reason that does not establish an implementation defect, such as duplicate, superseded, inactivity, low priority, wrong repository, workflow/provider/session failure, or no longer desired work.

### `UNCLEAR`

The evidence is insufficient to defensibly assign another outcome.

## Failure pattern

Assign a technical pattern only for `TECHNICAL_FAILURE_EVIDENCE` or `MERGED_AFTER_HUMAN_CORRECTION`. Otherwise use `UNASSIGNED`.

### `masked_symptom_instead_of_fixing`

The patch suppresses, bypasses, or hides the observed symptom without correcting the underlying defect.

### `false_premise_about_existing_code`

The patch relies on an incorrect assumption about repository behavior, APIs, types, language semantics, data contracts, or architecture.

### `incomplete_change_propagation`

A change is made in one place but not propagated to other required callers, representations, files, branches, schemas, platforms, or related code paths.

### `misdiagnosed_root_cause`

The agent identifies the wrong underlying cause and therefore changes the wrong component or logic.

### `broke_existing_contract_or_behavior`

The proposed fix violates or regresses behavior that the repository already promises or relies on.

### `disproportionate_or_duplicative_solution`

The patch adds unnecessary, duplicated, or overly broad implementation relative to the defect, and that excess causes or constitutes the technical problem.

### `vacuous_verification`

The agent's claimed verification does not test the behavior needed to establish the fix.

### `violated_project_constraint_or_convention`

The implementation conflicts with a documented or established repository-specific constraint, invariant, architectural rule, compatibility target, or required convention in a technically meaningful way.

### `unverified_trial_and_error`

The chronology shows repeated speculative implementation changes without validation of the underlying hypothesis.

### `wrong_baseline_or_branch`

The implementation targets the wrong repository state, branch, version, or baseline, making the fix inappropriate.

### `OTHER_TECHNICAL_PATTERN`

Concrete technical failure exists but no defined pattern fits. Supply a concise description in `proposed_other_pattern`.

### `UNASSIGNED`

No technical pattern can be defensibly assigned. Do not force-fit a label.

## Failure scope

Assign exactly one:

- `CODE_STATE`: the failure is a property of the resulting patch or repository state.
- `REPAIR_PROCESS`: the failure primarily concerns how the agent worked rather than the resulting code state.
- `BOTH`: supported evidence establishes both aspects.
- `UNKNOWN`: the scope cannot be established.

## Verification level

Assign exactly one.

- `EXECUTION_VERIFIED`: a relevant test or reproduction distinguishes the agent state from a corrected/later accepted state and corresponds to the reported issue.
- `CI_VERIFIED`: historical CI/check evidence directly exposes a technical defect attributable to the agent patch.
- `HUMAN_CORRECTION_VERIFIED`: attributable history clearly shows a substantive human correction of the agent implementation.
- `REVIEW_EVIDENCE`: a maintainer/reviewer explicitly explains the technical defect, without stronger execution, CI, or corrective-commit evidence.
- `LLM_INFERRED`: the technical judgment rests mainly on the reviewer's code reasoning without sufficient external evidence.
- `UNCLEAR_VERIFICATION`: no defensible verification level can be established.

Verification level is independent from the failure-pattern label.

## Confidence and evidence strength

Use `HIGH`, `MEDIUM`, or `LOW` for both outcome and pattern confidence. Assign evidence strength as `HIGH`, `MEDIUM`, or `LOW`; use `HIGH` only when cited evidence directly supports the conclusion.

## Audit questions

- `test_issue_alignment`: `YES`, `NO`, `UNCLEAR`, or `NOT_APPLICABLE`
- `human_correction`: `YES`, `NO`, `UNCLEAR`, or `NOT_APPLICABLE`
- `evidence_overstated`: `YES`, `NO`, or `UNCLEAR`

## Justification rules

- Cite exact evidence IDs present in the packet.
- Every substantive non-`UNCLEAR` outcome needs at least one citation.
- Use a short factual `reasoning_summary`; never expose private chain-of-thought.
- Do not interpret missing evidence as proof that an event did not happen.
- Do not consult mutable web evidence, old labels, consensus results, or the other reviewer.
