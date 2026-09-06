"""The frozen fine-grained taxonomy and the frozen fine -> family mapping.

Nothing here reclassifies anything. The mapping is applied deterministically to
BOTH reviewers' original sealed labels, exactly as the two source studies did.
"""

from __future__ import annotations

from pathlib import Path

import yaml

TAXONOMY_VERSION = "aidev_failure_taxonomy_v1"

UNASSIGNED = "UNASSIGNED"

#: The 11 technical fine labels of the frozen taxonomy. ``UNASSIGNED`` is NOT a
#: technical pattern; it is the AIDev "no technical pattern" sentinel and is
#: deliberately absent from the family mapping.
FINE_LABELS = frozenset(
    {
        "masked_symptom_instead_of_fixing",
        "false_premise_about_existing_code",
        "incomplete_change_propagation",
        "misdiagnosed_root_cause",
        "broke_existing_contract_or_behavior",
        "disproportionate_or_duplicative_solution",
        "vacuous_verification",
        "violated_project_constraint_or_convention",
        "unverified_trial_and_error",
        "wrong_baseline_or_branch",
        "OTHER_TECHNICAL_PATTERN",
    }
)


def load_family_mapping(path: str | Path) -> dict[str, str]:
    """Load the frozen family YAML as a ``fine label -> family`` dict.

    Raises if a fine label is mapped twice, or if the mapping does not cover
    exactly :data:`FINE_LABELS`.
    """
    families = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(families, dict):
        raise ValueError(f"{path}: expected a mapping of family -> [fine labels]")

    fine_to_family: dict[str, str] = {}
    for family, fines in families.items():
        for fine in fines:
            if fine in fine_to_family:
                raise ValueError(f"{path}: label {fine!r} mapped to two families")
            fine_to_family[fine] = family

    missing = FINE_LABELS - fine_to_family.keys()
    extra = fine_to_family.keys() - FINE_LABELS
    if missing or extra:
        raise ValueError(
            f"{path}: mapping mismatch missing={sorted(missing)} extra={sorted(extra)}"
        )
    return fine_to_family


def family_for(fine_label: str, mapping: dict[str, str]) -> str:
    """Map one fine label to its broad family.

    ``UNASSIGNED`` has no family. It is never mapped here; callers must exclude
    ``UNASSIGNED`` cases before mapping (this is the AIDev inclusion rule).
    """
    if fine_label == UNASSIGNED:
        raise ValueError(
            "UNASSIGNED has no broad family; exclude the case before mapping"
        )
    try:
        return mapping[fine_label]
    except KeyError as exc:  # pragma: no cover - guarded by load_family_mapping
        raise ValueError(f"unknown fine label {fine_label!r}") from exc
