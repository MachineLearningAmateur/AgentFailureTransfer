"""Fine-label and family-level agreement mechanics on hand-built toy data."""

from __future__ import annotations

import pytest

from agentfailuretransfer.agreement import agreement
from agentfailuretransfer.taxonomy import UNASSIGNED

TOY_MAPPING = {
    "false_premise_about_existing_code": "REPOSITORY_UNDERSTANDING",
    "misdiagnosed_root_cause": "REPOSITORY_UNDERSTANDING",
    "masked_symptom_instead_of_fixing": "REPOSITORY_UNDERSTANDING",
    "vacuous_verification": "VACUOUS_VERIFICATION",
    "wrong_baseline_or_branch": "BASELINE_STATE",
}


def include_both_assigned(codex: dict, claude: dict) -> list[str]:
    """The AIDev inclusion rule, restated for the toy fixture."""
    return [
        case_id
        for case_id in sorted(codex)
        if codex[case_id] != UNASSIGNED and claude[case_id] != UNASSIGNED
    ]


def test_toy_fine_agreement_counts():
    codex = {
        "01": "false_premise_about_existing_code",
        "02": "misdiagnosed_root_cause",
        "03": "vacuous_verification",
        "04": UNASSIGNED,
        "05": "wrong_baseline_or_branch",
    }
    claude = {
        "01": "false_premise_about_existing_code",
        "02": "masked_symptom_instead_of_fixing",
        "03": "wrong_baseline_or_branch",
        "04": "vacuous_verification",
        "05": UNASSIGNED,
    }
    included = include_both_assigned(codex, claude)
    assert included == ["01", "02", "03"]

    fine = agreement([codex[c] for c in included], [claude[c] for c in included])
    assert fine["n"] == 3
    assert fine["exact_agreements"] == 1
    assert fine["agreement_rate"] == pytest.approx(1 / 3)


def test_toy_family_mapping_absorbs_a_fine_disagreement():
    codex = {"01": "misdiagnosed_root_cause", "02": "vacuous_verification"}
    claude = {"01": "masked_symptom_instead_of_fixing", "02": "wrong_baseline_or_branch"}
    included = include_both_assigned(codex, claude)

    fine = agreement([codex[c] for c in included], [claude[c] for c in included])
    family = agreement(
        [TOY_MAPPING[codex[c]] for c in included],
        [TOY_MAPPING[claude[c]] for c in included],
    )
    assert fine["exact_agreements"] == 0
    # Case 01 is a fine disagreement inside one family; case 02 is not.
    assert family["exact_agreements"] == 1


def test_unassigned_cases_are_excluded_not_counted_as_agreement():
    codex = {"01": UNASSIGNED, "02": UNASSIGNED}
    claude = {"01": UNASSIGNED, "02": "vacuous_verification"}
    assert include_both_assigned(codex, claude) == []
