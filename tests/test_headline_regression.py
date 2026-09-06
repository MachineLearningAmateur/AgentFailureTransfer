"""Regression: the published exact agreement counts must reproduce.

The counts are recomputed here from the imported sealed labels. The kappa
implementation is never given a hard-coded result to aim at; only the exact
integer counts and the published kappas (at their stated precision) are
asserted, and the kappa function itself is validated separately in
tests/test_kappa.py against sklearn.
"""

from __future__ import annotations

from collections import defaultdict

import pytest

from agentfailuretransfer.agreement import agreement
from agentfailuretransfer.taxonomy import UNASSIGNED

KAPPA_TOLERANCE = 5e-4


@pytest.fixture(scope="module")
def aidev_both_assigned(aidev_reviews):
    codex, claude = aidev_reviews["codex"], aidev_reviews["claude"]
    return [
        case_id
        for case_id in sorted(codex)
        if codex[case_id]["failure_pattern"] != UNASSIGNED
        and claude[case_id]["failure_pattern"] != UNASSIGNED
    ]


def test_aidev_population_is_49(aidev_both_assigned):
    assert len(aidev_both_assigned) == 49


def test_aidev_fine_is_31_of_49(aidev_reviews, aidev_both_assigned):
    codex, claude = aidev_reviews["codex"], aidev_reviews["claude"]
    block = agreement(
        [codex[c]["failure_pattern"] for c in aidev_both_assigned],
        [claude[c]["failure_pattern"] for c in aidev_both_assigned],
    )
    assert (block["exact_agreements"], block["n"]) == (31, 49)
    assert block["cohens_kappa"] == pytest.approx(0.5828, abs=KAPPA_TOLERANCE)


def test_aidev_family_is_36_of_49(aidev_reviews, aidev_both_assigned, family_mapping):
    codex, claude = aidev_reviews["codex"], aidev_reviews["claude"]
    block = agreement(
        [family_mapping[codex[c]["failure_pattern"]] for c in aidev_both_assigned],
        [family_mapping[claude[c]["failure_pattern"]] for c in aidev_both_assigned],
    )
    assert (block["exact_agreements"], block["n"]) == (36, 49)
    assert block["cohens_kappa"] == pytest.approx(0.6575, abs=KAPPA_TOLERANCE)


def test_swesmith_fine_is_41_of_100(swesmith_reviews):
    codex, claude = swesmith_reviews["codex"], swesmith_reviews["claude"]
    case_ids = sorted(codex)
    block = agreement(
        [codex[c]["failure_pattern"] for c in case_ids],
        [claude[c]["failure_pattern"] for c in case_ids],
    )
    assert (block["exact_agreements"], block["n"]) == (41, 100)
    assert block["cohens_kappa"] == pytest.approx(0.254, abs=KAPPA_TOLERANCE)


def test_swesmith_family_is_41_of_100(swesmith_reviews, family_mapping):
    codex, claude = swesmith_reviews["codex"], swesmith_reviews["claude"]
    case_ids = sorted(codex)
    block = agreement(
        [family_mapping[codex[c]["failure_pattern"]] for c in case_ids],
        [family_mapping[claude[c]["failure_pattern"]] for c in case_ids],
    )
    assert (block["exact_agreements"], block["n"]) == (41, 100)
    assert block["cohens_kappa"] == pytest.approx(0.242, abs=KAPPA_TOLERANCE)


PER_FAMILY_EXPECTED = {
    "llm": {"n": 36, "exact": 20, "kappa": 0.298},
    "mirror": {"n": 28, "exact": 15, "kappa": 0.393},
    "procedural": {"n": 34, "exact": 6, "kappa": 0.127},
    "combine": {"n": 2, "exact": 0, "kappa": 0.0},
}


@pytest.mark.parametrize("family", sorted(PER_FAMILY_EXPECTED))
def test_per_generation_family_family_level(
    family, swesmith_reviews, swesmith_crosswalk, family_mapping
):
    """The published per-family kappas are FAMILY-level, not fine-level."""
    codex, claude = swesmith_reviews["codex"], swesmith_reviews["claude"]
    groups: dict[str, list[str]] = defaultdict(list)
    for case_id in sorted(codex):
        groups[swesmith_crosswalk[case_id]["method_family"]].append(case_id)

    subset = groups[family]
    expected = PER_FAMILY_EXPECTED[family]
    assert len(subset) == expected["n"]

    block = agreement(
        [family_mapping[codex[c]["failure_pattern"]] for c in subset],
        [family_mapping[claude[c]["failure_pattern"]] for c in subset],
    )
    assert block["exact_agreements"] == expected["exact"]
    assert block["cohens_kappa"] == pytest.approx(expected["kappa"], abs=KAPPA_TOLERANCE)


def test_combine_kappa_is_a_real_zero_not_undefined(
    swesmith_reviews, swesmith_crosswalk, family_mapping
):
    codex, claude = swesmith_reviews["codex"], swesmith_reviews["claude"]
    subset = [
        c
        for c in sorted(codex)
        if swesmith_crosswalk[c]["method_family"] == "combine"
    ]
    block = agreement(
        [family_mapping[codex[c]["failure_pattern"]] for c in subset],
        [family_mapping[claude[c]["failure_pattern"]] for c in subset],
    )
    assert block["n"] == 2
    assert block["cohens_kappa"] == 0.0
    assert block["cohens_kappa"] == block["cohens_kappa"]  # not nan


def test_derived_reconstructions_are_stable(aidev_reviews, family_mapping):
    """The 35-case strict code-state corpus, per the source study's rule."""
    codex, claude = aidev_reviews["codex"], aidev_reviews["claude"]
    technical = {"TECHNICAL_FAILURE_EVIDENCE", "MERGED_AFTER_HUMAN_CORRECTION"}
    code_state = {"CODE_STATE", "BOTH"}
    strict = [
        c
        for c in sorted(codex)
        if codex[c]["outcome_classification"] in technical
        and claude[c]["outcome_classification"] in technical
        and codex[c]["failure_scope"] in code_state
        and claude[c]["failure_scope"] in code_state
        and codex[c]["failure_pattern"] != UNASSIGNED
        and claude[c]["failure_pattern"] != UNASSIGNED
        and family_mapping[codex[c]["failure_pattern"]]
        == family_mapping[claude[c]["failure_pattern"]]
    ]
    assert len(strict) == 35


def test_emitted_headline_json_matches_the_recomputation(
    headline_results, aidev_reviews, swesmith_reviews, aidev_both_assigned
):
    assert headline_results["aidev"]["n_included"] == len(aidev_both_assigned)
    assert headline_results["aidev"]["fine_grained"]["exact_agreements"] == 31
    assert headline_results["aidev"]["family"]["exact_agreements"] == 36
    assert headline_results["swesmith"]["fine_grained"]["exact_agreements"] == 41
    assert headline_results["swesmith"]["family"]["exact_agreements"] == 41
    assert headline_results["taxonomy_version"] == "aidev_failure_taxonomy_v1"


def test_emitted_headline_matches_the_imported_source_metrics(headline_results):
    """Independent cross-check against the source study's published metrics."""
    import json

    from agentfailuretransfer import paths

    published = json.loads(
        paths.AIDEV_AGREEMENT_METRICS.read_text(encoding="utf-8")
    )
    assert published["pattern_both_assigned"]["n"] == 49
    assert (
        published["pattern_both_assigned"]["exact_agreement"]
        == headline_results["aidev"]["fine_grained"]["exact_agreements"]
    )
    assert (
        published["pattern_family_both_assigned"]["exact_agreement"]
        == headline_results["aidev"]["family"]["exact_agreements"]
    )
    assert published["pattern_both_assigned"]["cohen_kappa"] == pytest.approx(
        headline_results["aidev"]["fine_grained"]["cohens_kappa"], abs=1e-9
    )
