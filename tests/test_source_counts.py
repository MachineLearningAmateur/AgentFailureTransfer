"""Expected counts in the imported sealed sources and the generation crosswalk."""

from __future__ import annotations

from collections import Counter

EXPECTED_GENERATION_FAMILY_COUNTS = {
    "llm": 36,
    "mirror": 28,
    "procedural": 34,
    "combine": 2,
}


def test_aidev_reviewed_case_counts(aidev_reviews):
    assert len(aidev_reviews["codex"]) == 100
    assert len(aidev_reviews["claude"]) == 100


def test_swesmith_reviewed_case_counts(swesmith_reviews):
    assert len(swesmith_reviews["codex"]) == 100
    assert len(swesmith_reviews["claude"]) == 100


def test_manifests_record_the_same_counts(aidev_manifest, swesmith_manifest):
    for manifest in (aidev_manifest, swesmith_manifest):
        for reviewer in ("codex", "claude"):
            entry = manifest["review_completion"][reviewer]
            assert entry["complete_marker_present"] is True
            assert entry["reviewed_cases"] == 100


def test_generation_family_values_are_the_expected_four(swesmith_crosswalk):
    families = {row["method_family"] for row in swesmith_crosswalk.values()}
    assert families <= set(EXPECTED_GENERATION_FAMILY_COUNTS)


def test_generation_family_counts(swesmith_crosswalk):
    counts = Counter(row["method_family"] for row in swesmith_crosswalk.values())
    assert dict(counts) == EXPECTED_GENERATION_FAMILY_COUNTS
    assert sum(counts.values()) == 100


def test_crosswalk_covers_exactly_the_reviewed_cases(swesmith_crosswalk, swesmith_reviews):
    assert set(swesmith_crosswalk) == set(swesmith_reviews["codex"])
    assert set(swesmith_crosswalk) == set(swesmith_reviews["claude"])


def test_crosswalk_is_all_python(swesmith_crosswalk):
    assert {row["language"] for row in swesmith_crosswalk.values()} == {"python"}


def test_pr_mirror_normalisation_is_materialised(swesmith_crosswalk):
    """Every `mirror` row carries the normalised pr_mirror method."""
    mirror_methods = {
        row["generation_method"]
        for row in swesmith_crosswalk.values()
        if row["method_family"] == "mirror"
    }
    assert mirror_methods == {"pr_mirror"}
