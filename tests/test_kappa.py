"""Cohen's kappa: cross-checked against sklearn, plus the degenerate cases.

The implementation under test must never depend on a hard-coded study result.
"""

from __future__ import annotations

import random

import pytest
from sklearn.metrics import cohen_kappa_score

from agentfailuretransfer.agreement import agreement, cohen_kappa

LABELS = ["A", "B", "C", "D"]


@pytest.mark.parametrize(
    "left,right",
    [
        (["A", "B", "C", "A"], ["A", "C", "C", "B"]),
        (["A", "A", "B", "B", "C"], ["B", "A", "B", "C", "C"]),
        (["A", "B"], ["B", "A"]),
        (["A", "A", "A", "B"], ["A", "A", "B", "B"]),
        (["X", "Y", "Z"], ["Z", "Y", "X"]),
    ],
)
def test_matches_sklearn_on_toy_data(left, right):
    assert cohen_kappa(left, right) == pytest.approx(
        float(cohen_kappa_score(left, right)), abs=1e-12
    )


def test_matches_sklearn_on_many_random_samples():
    rng = random.Random(20260830)
    for _ in range(200):
        n = rng.randint(2, 60)
        left = [rng.choice(LABELS) for _ in range(n)]
        right = [rng.choice(LABELS) for _ in range(n)]
        expected = float(cohen_kappa_score(left, right))
        if expected != expected:  # sklearn returns nan in the degenerate case
            continue
        assert cohen_kappa(left, right) == pytest.approx(expected, abs=1e-12)


def test_perfect_agreement_is_one():
    assert cohen_kappa(["A", "B", "A"], ["A", "B", "A"]) == pytest.approx(1.0)


def test_degenerate_single_label_perfect_agreement_is_one():
    # Expected agreement is 1.0 and observed agreement is 1.0.
    assert cohen_kappa(["A", "A", "A"], ["A", "A", "A"]) == 1.0


def test_degenerate_single_label_mismatch_is_zero():
    # Both raters used exactly one label each, but different ones: expected
    # agreement is 0.0 here, not 1.0, so this is the ordinary formula.
    assert cohen_kappa(["A", "A"], ["B", "B"]) == 0.0


def test_empty_input_is_zero():
    assert cohen_kappa([], []) == 0.0
    block = agreement([], [])
    assert block["n"] == 0
    assert block["cohens_kappa"] == 0.0
    assert block["agreement_rate"] is None


def test_disjoint_label_sets_give_a_genuine_zero_not_nan():
    """The `combine` (n=2) situation: disjoint labels -> real kappa of 0.0."""
    left = ["disproportionate_or_duplicative_solution", "false_premise_about_existing_code"]
    right = ["broke_existing_contract_or_behavior", "broke_existing_contract_or_behavior"]
    value = cohen_kappa(left, right)
    assert value == 0.0
    assert value == value  # not nan


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError):
        cohen_kappa(["A"], ["A", "B"])
    with pytest.raises(ValueError):
        agreement(["A"], ["A", "B"])


def test_agreement_counts_and_rounding():
    block = agreement(["A", "B", "C", "A"], ["A", "C", "C", "B"])
    assert block["n"] == 4
    assert block["exact_agreements"] == 2
    assert block["agreement_rate"] == pytest.approx(0.5)
    assert block["cohens_kappa_4dp"] == round(block["cohens_kappa"], 4)
