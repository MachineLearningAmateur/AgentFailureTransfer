"""Phase 1B: robustness analysis, its statistics, and its determinism.

Nothing here writes into ``data/`` or ``sources/``; one module-scoped fixture
runs ``scripts/run_phase1b_robustness.py`` twice and hashes the imported
artifacts on either side of it, which is itself one of the assertions.
"""

from __future__ import annotations

import csv
import itertools
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pytest
from scipy import stats as scipy_stats

from agentfailuretransfer import paths
from agentfailuretransfer.agreement import agreement, cohen_kappa
from agentfailuretransfer.hashing import sha256_file
from agentfailuretransfer.stats import (
    bootstrap_kappa,
    cohen_kappa_or_none,
    risk_difference_newcombe,
    risk_ratio_wald,
    wilson_interval,
)
from agentfailuretransfer.taxonomy import UNASSIGNED

SCRIPT = paths.REPO_ROOT / "scripts" / "run_phase1b_robustness.py"

# Source-study checkpoint values. Assertions only; never inputs to a computation.
SOURCE_ALL100_AGREEMENTS = 65
SOURCE_ALL100_KAPPA = 0.5531154239019408
KAPPA_TOLERANCE = 5e-4


# --------------------------------------------------------------------------
# Population construction
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def aidev_all100(aidev_reviews):
    """The source study's all-100 cross-model pattern population.

    AIBugAnalysis@scripts/compare_reviews.py: all 100 reviewed cases sorted by
    case_id, raw failure_pattern strings, UNASSIGNED kept as an ordinary label.
    """
    codex, claude = aidev_reviews["codex"], aidev_reviews["claude"]
    case_ids = sorted(codex)
    return (
        case_ids,
        [codex[c]["failure_pattern"] for c in case_ids],
        [claude[c]["failure_pattern"] for c in case_ids],
    )


def test_all100_population_is_every_reviewed_case(aidev_all100, aidev_reviews):
    case_ids, left, right = aidev_all100
    assert len(case_ids) == 100
    assert case_ids == sorted(aidev_reviews["claude"])
    assert len(left) == len(right) == 100
    # No filtering, no substitution: the labels are the sealed strings verbatim.
    assert left == [aidev_reviews["codex"][c]["failure_pattern"] for c in case_ids]
    assert right == [aidev_reviews["claude"][c]["failure_pattern"] for c in case_ids]


def test_all100_keeps_unassigned_as_an_ordinary_label(aidev_all100):
    _, left, right = aidev_all100
    assert UNASSIGNED in left and UNASSIGNED in right
    both_unassigned = sum(
        1 for a, b in zip(left, right) if a == b == UNASSIGNED
    )
    # UNASSIGNED/UNASSIGNED pairs are agreements under the source semantics.
    assert both_unassigned == 34
    assert both_unassigned < sum(a == b for a, b in zip(left, right))


def test_all100_reproduces_the_source_study_value(aidev_all100):
    _, left, right = aidev_all100
    block = agreement(left, right)
    assert (block["exact_agreements"], block["n"]) == (SOURCE_ALL100_AGREEMENTS, 100)
    assert block["cohens_kappa"] == pytest.approx(SOURCE_ALL100_KAPPA, abs=1e-9)


def test_all100_differs_from_the_both_assigned_population(aidev_reviews):
    """The sensitivity analysis is a different population, not a re-labelling."""
    codex, claude = aidev_reviews["codex"], aidev_reviews["claude"]
    both = [
        c
        for c in sorted(codex)
        if codex[c]["failure_pattern"] != UNASSIGNED
        and claude[c]["failure_pattern"] != UNASSIGNED
    ]
    assert len(both) == 49
    assert set(both) < set(sorted(codex))


# --------------------------------------------------------------------------
# Regression assertions on the frozen counts
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def swesmith_groups(swesmith_reviews, swesmith_crosswalk):
    codex = swesmith_reviews["codex"]
    groups: dict[str, list[str]] = {}
    for case_id in sorted(codex):
        groups.setdefault(swesmith_crosswalk[case_id]["method_family"], []).append(
            case_id
        )
    return groups


def family_agreement(reviews, mapping, case_ids, level="family"):
    codex, claude = reviews["codex"], reviews["claude"]
    left = [codex[c]["failure_pattern"] for c in case_ids]
    right = [claude[c]["failure_pattern"] for c in case_ids]
    if level == "family":
        left = [mapping[x] for x in left]
        right = [mapping[x] for x in right]
    return agreement(left, right)


def test_phase1a_counts_are_unchanged(aidev_reviews, swesmith_reviews, family_mapping):
    codex, claude = aidev_reviews["codex"], aidev_reviews["claude"]
    both = [
        c
        for c in sorted(codex)
        if codex[c]["failure_pattern"] != UNASSIGNED
        and claude[c]["failure_pattern"] != UNASSIGNED
    ]
    fine = family_agreement(aidev_reviews, family_mapping, both, "fine")
    family = family_agreement(aidev_reviews, family_mapping, both, "family")
    assert (fine["exact_agreements"], fine["n"]) == (31, 49)
    assert (family["exact_agreements"], family["n"]) == (36, 49)

    swesmith_ids = sorted(swesmith_reviews["codex"])
    swesmith_family = family_agreement(
        swesmith_reviews, family_mapping, swesmith_ids, "family"
    )
    assert (swesmith_family["exact_agreements"], swesmith_family["n"]) == (41, 100)


def test_procedural_and_nonprocedural_group_membership(
    swesmith_groups, swesmith_reviews, swesmith_crosswalk, family_mapping
):
    procedural = swesmith_groups["procedural"]
    nonprocedural = sorted(
        itertools.chain(
            swesmith_groups["llm"], swesmith_groups["mirror"], swesmith_groups["combine"]
        )
    )
    llm_mirror = sorted(
        itertools.chain(swesmith_groups["llm"], swesmith_groups["mirror"])
    )

    # The groups partition the 100 cases and never overlap.
    assert len(procedural) == 34
    assert len(nonprocedural) == 66
    assert len(llm_mirror) == 64
    assert set(procedural).isdisjoint(nonprocedural)
    assert set(procedural) | set(nonprocedural) == set(sorted(swesmith_reviews["codex"]))
    assert set(llm_mirror) < set(nonprocedural)
    assert all(
        swesmith_crosswalk[c]["method_family"] == "procedural" for c in procedural
    )
    assert all(
        swesmith_crosswalk[c]["method_family"] != "procedural" for c in nonprocedural
    )

    procedural_block = family_agreement(swesmith_reviews, family_mapping, procedural)
    nonprocedural_block = family_agreement(
        swesmith_reviews, family_mapping, nonprocedural
    )
    assert (procedural_block["exact_agreements"], procedural_block["n"]) == (6, 34)
    assert (nonprocedural_block["exact_agreements"], nonprocedural_block["n"]) == (
        35,
        66,
    )


# --------------------------------------------------------------------------
# Wilson interval
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "successes,n",
    [(6, 34), (35, 66), (31, 49), (41, 100), (20, 36), (15, 28), (1, 3), (7, 7)],
)
def test_wilson_endpoints_solve_the_score_equation(successes, n):
    """Each endpoint p satisfies |p_hat - p| = z * sqrt(p(1-p)/n)."""
    z = float(scipy_stats.norm.ppf(0.975))
    p_hat = successes / n
    low, high = wilson_interval(successes, n)
    for endpoint in (low, high):
        if 0.0 < endpoint < 1.0:
            residual = abs(p_hat - endpoint) - z * np.sqrt(
                endpoint * (1.0 - endpoint) / n
            )
            assert residual == pytest.approx(0.0, abs=1e-12)


def test_wilson_is_not_the_wald_interval():
    z = float(scipy_stats.norm.ppf(0.975))
    successes, n = 0, 2
    low, high = wilson_interval(successes, n)
    wald_half_width = z * np.sqrt(0.0 * 1.0 / n)
    assert (low, high) != (0.0 - wald_half_width, 0.0 + wald_half_width)
    assert low == 0.0
    assert high > 0.0  # Wald would collapse to a zero-width interval here


def test_wilson_contains_the_point_estimate_and_stays_in_range():
    for n in range(1, 40):
        for successes in range(0, n + 1):
            low, high = wilson_interval(successes, n)
            assert 0.0 <= low <= successes / n <= high <= 1.0


def test_wilson_rejects_impossible_counts():
    with pytest.raises(ValueError):
        wilson_interval(5, 4)


def test_wilson_of_zero_denominator_is_uninformative():
    assert wilson_interval(0, 0) == (0.0, 1.0)


# --------------------------------------------------------------------------
# Kappa variants and the bootstrap
# --------------------------------------------------------------------------
def test_kappa_or_none_matches_the_published_kappa_on_real_data(
    swesmith_reviews, family_mapping
):
    case_ids = sorted(swesmith_reviews["codex"])
    left = [
        family_mapping[swesmith_reviews["codex"][c]["failure_pattern"]]
        for c in case_ids
    ]
    right = [
        family_mapping[swesmith_reviews["claude"][c]["failure_pattern"]]
        for c in case_ids
    ]
    assert cohen_kappa_or_none(left, right) == cohen_kappa(left, right)


def test_kappa_or_none_is_none_where_the_published_rule_returns_a_number():
    left = ["A", "A", "A"]
    right = ["A", "A", "A"]
    assert cohen_kappa_or_none(left, right) is None  # expected agreement == 1.0
    assert cohen_kappa(left, right) == 1.0  # the source-study degenerate rule
    assert cohen_kappa_or_none([], []) is None
    assert cohen_kappa([], []) == 0.0


def reference_bootstrap(left, right, seed, replicates):
    """Independent paired-bootstrap reference, written the obvious slow way."""
    n = len(left)
    rng = np.random.default_rng(seed)
    estimates = []
    undefined = 0
    for _ in range(replicates):
        index = rng.integers(0, n, size=n)
        sample_left = [left[i] for i in index]
        sample_right = [right[i] for i in index]
        value = cohen_kappa_or_none(sample_left, sample_right)
        if value is None:
            undefined += 1
        else:
            estimates.append(value)
    return estimates, undefined


def test_bootstrap_matches_an_independent_paired_reference(
    swesmith_reviews, swesmith_groups, family_mapping
):
    """Same seed, same draws, same values -- and the reference resamples ROWS."""
    subset = swesmith_groups["procedural"]
    left = [
        family_mapping[swesmith_reviews["codex"][c]["failure_pattern"]] for c in subset
    ]
    right = [
        family_mapping[swesmith_reviews["claude"][c]["failure_pattern"]] for c in subset
    ]
    result = bootstrap_kappa(left, right, seed=[20260906, 7], replicates=300)
    estimates, undefined = reference_bootstrap(left, right, [20260906, 7], 300)

    assert result["valid_replicates"] == len(estimates)
    assert result["undefined_replicates"] == undefined
    assert result["ci_low"] == pytest.approx(np.percentile(estimates, 2.5), abs=1e-12)
    assert result["ci_high"] == pytest.approx(np.percentile(estimates, 97.5), abs=1e-12)


def test_bootstrap_is_reproducible_under_a_fixed_seed():
    left = ["A", "B", "A", "C", "B", "A", "C", "C", "B", "A"]
    right = ["A", "C", "A", "C", "B", "B", "C", "A", "B", "A"]
    first = bootstrap_kappa(left, right, seed=20260906, replicates=500)
    second = bootstrap_kappa(left, right, seed=20260906, replicates=500)
    assert first == second
    different = bootstrap_kappa(left, right, seed=20260907, replicates=500)
    assert (different["ci_low"], different["ci_high"]) != (
        first["ci_low"],
        first["ci_high"],
    )


def test_bootstrap_resamples_paired_rows_only():
    """Every attainable replicate value comes from a multiset of ORIGINAL pairs.

    The rows here are (A,A), (A,A), (B,C), (B,C). If the two reviewers' columns
    were resampled independently, pairs such as (A,C) would become attainable
    and would put kappa values outside the enumerated paired set.
    """
    left = ["A", "A", "B", "B"]
    right = ["A", "A", "C", "C"]
    n = len(left)
    attainable = set()
    for combination in itertools.combinations_with_replacement(range(n), n):
        value = cohen_kappa_or_none(
            [left[i] for i in combination], [right[i] for i in combination]
        )
        if value is not None:
            attainable.add(round(value, 12))

    result = bootstrap_kappa(left, right, seed=20260906, replicates=400)
    assert result["valid_replicates"] + result["undefined_replicates"] == 400
    assert round(result["ci_low"], 12) in attainable
    assert round(result["ci_high"], 12) in attainable

    # An independently-resampled (pairing-broken) run reaches values the paired
    # bootstrap cannot, which is what makes this assertion meaningful.
    rng = np.random.default_rng(20260906)
    broken = set()
    for _ in range(400):
        left_index = rng.integers(0, n, size=n)
        right_index = rng.integers(0, n, size=n)
        value = cohen_kappa_or_none(
            [left[i] for i in left_index], [right[i] for i in right_index]
        )
        if value is not None:
            broken.add(round(value, 12))
    assert broken - attainable


def test_bootstrap_counts_undefined_replicates_instead_of_zeroing_them():
    """A population where most resamples are degenerate must SAY so."""
    left = ["A", "A", "A", "B"]
    right = ["A", "A", "A", "B"]
    result = bootstrap_kappa(left, right, seed=20260906, replicates=1000)
    assert result["undefined_replicates"] > 0
    assert result["valid_replicates"] + result["undefined_replicates"] == 1000
    # Undefined replicates were excluded, not folded in as zeros.
    assert result["ci_low"] > 0.0


def test_bootstrap_point_estimate_is_the_observed_kappa(
    aidev_reviews, family_mapping
):
    codex, claude = aidev_reviews["codex"], aidev_reviews["claude"]
    case_ids = sorted(codex)
    left = [codex[c]["failure_pattern"] for c in case_ids]
    right = [claude[c]["failure_pattern"] for c in case_ids]
    result = bootstrap_kappa(left, right, seed=20260906, replicates=200)
    assert result["point_estimate"] == pytest.approx(SOURCE_ALL100_KAPPA, abs=1e-9)


# --------------------------------------------------------------------------
# 2x2 table, Fisher, effect sizes
# --------------------------------------------------------------------------
def test_fisher_table_construction_and_test(
    swesmith_reviews, swesmith_groups, family_mapping
):
    procedural = swesmith_groups["procedural"]
    nonprocedural = sorted(
        itertools.chain(
            swesmith_groups["llm"], swesmith_groups["mirror"], swesmith_groups["combine"]
        )
    )
    procedural_block = family_agreement(swesmith_reviews, family_mapping, procedural)
    nonprocedural_block = family_agreement(
        swesmith_reviews, family_mapping, nonprocedural
    )
    a = procedural_block["exact_agreements"]
    b = procedural_block["n"] - a
    c = nonprocedural_block["exact_agreements"]
    d = nonprocedural_block["n"] - c
    assert [[a, b], [c, d]] == [[6, 28], [35, 31]]
    assert a + b + c + d == 100

    odds_ratio, p_value = scipy_stats.fisher_exact([[a, b], [c, d]], "two-sided")
    assert odds_ratio == pytest.approx((a * d) / (b * c))
    assert 0.0 < p_value < 0.01


def test_risk_difference_and_ratio():
    result = risk_difference_newcombe(6, 34, 35, 66)
    assert result["risk_difference"] == pytest.approx(6 / 34 - 35 / 66)
    low_1, high_1 = wilson_interval(6, 34)
    low_2, high_2 = wilson_interval(35, 66)
    p1, p2 = 6 / 34, 35 / 66
    assert result["ci_low"] == pytest.approx(
        (p1 - p2) - np.sqrt((p1 - low_1) ** 2 + (high_2 - p2) ** 2)
    )
    assert result["ci_high"] == pytest.approx(
        (p1 - p2) + np.sqrt((high_1 - p1) ** 2 + (p2 - low_2) ** 2)
    )
    assert result["ci_high"] < 0.0  # the interval excludes "no difference"

    ratio = risk_ratio_wald(6, 34, 35, 66)
    assert ratio["risk_ratio"] == pytest.approx((6 / 34) / (35 / 66))
    assert ratio["ci_low"] < ratio["risk_ratio"] < ratio["ci_high"]
    assert ratio["ci_high"] < 1.0


def test_risk_ratio_with_a_zero_cell_reports_no_interval():
    ratio = risk_ratio_wald(0, 2, 35, 66)
    assert ratio["ci_low"] is None and ratio["ci_high"] is None


# --------------------------------------------------------------------------
# Running the script: determinism, and no mutation of the imported artifacts
# --------------------------------------------------------------------------
def hash_tree(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(paths.REPO_ROOT)): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.fixture(scope="module")
def script_runs() -> dict:
    before = {**hash_tree(paths.DATA_DIR), **hash_tree(paths.SOURCES_DIR)}
    phase1a = {
        name: sha256_file(paths.TAXONOMY_TRANSFER_DIR / name)
        for name in ("headline_results.json", "headline_results.md")
        if (paths.TAXONOMY_TRANSFER_DIR / name).is_file()
    }
    outputs = []
    for _ in range(2):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=paths.REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            pytest.fail(
                f"run_phase1b_robustness.py exited {completed.returncode}\n"
                f"{completed.stdout}\n{completed.stderr}"
            )
        outputs.append(hash_tree(paths.PHASE1B_DIR))
    after = {**hash_tree(paths.DATA_DIR), **hash_tree(paths.SOURCES_DIR)}
    return {
        "data_before": before,
        "data_after": after,
        "phase1a_before": phase1a,
        "first": outputs[0],
        "second": outputs[1],
    }


def test_script_does_not_mutate_imported_artifacts(script_runs):
    assert script_runs["data_before"] == script_runs["data_after"]
    assert script_runs["data_before"], "expected to have hashed some imported files"


def test_script_does_not_touch_phase1a_outputs(script_runs):
    for name, digest in script_runs["phase1a_before"].items():
        assert sha256_file(paths.TAXONOMY_TRANSFER_DIR / name) == digest


def test_script_output_is_byte_identical_across_two_runs(script_runs):
    assert script_runs["first"] == script_runs["second"]
    assert len(script_runs["first"]) == 7


def test_script_emits_every_required_artifact(script_runs):
    expected = {
        "agreement_confidence_intervals.csv",
        "aidev_denominator_sensitivity.csv",
        "bootstrap_summary.csv",
        "notes.md",
        "procedural_vs_nonprocedural.csv",
        "robustness_report.md",
        "robustness_results.json",
    }
    assert {Path(name).name for name in script_runs["first"]} == expected


# --------------------------------------------------------------------------
# The emitted artifacts
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def results(script_runs) -> dict:
    return json.loads(
        (paths.PHASE1B_DIR / "robustness_results.json").read_text(encoding="utf-8")
    )


def read_csv(name: str) -> list[dict]:
    with (paths.PHASE1B_DIR / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_results_json_has_every_required_section(results):
    for section in (
        "source_provenance",
        "aidev_primary",
        "aidev_all100_sensitivity",
        "swesmith_primary",
        "confidence_intervals",
        "bootstrap_kappa",
        "generation_family",
        "procedural_vs_nonprocedural",
        "analysis_settings",
    ):
        assert section in results, section
    settings = results["analysis_settings"]
    assert settings["bootstrap_seed"] == 20260906
    assert settings["bootstrap_replicates"] == 10000
    assert settings["permutations"] == 10000
    assert settings["fisher_alternative"] == "two-sided"
    assert settings["proportion_ci_method"] == "Wilson score interval"
    assert set(settings["software"]) == {"python", "numpy", "scipy"}


def test_results_json_carries_no_timestamp(script_runs):
    for name in script_runs["first"]:
        text = (paths.REPO_ROOT / name).read_text(encoding="utf-8")
        assert "imported_at_utc" not in text
        assert "generated_at" not in text


def test_results_json_reproduces_the_frozen_counts(results):
    assert results["aidev_primary"]["fine"]["agreements"] == 31
    assert results["aidev_primary"]["fine"]["n"] == 49
    assert results["aidev_primary"]["family"]["agreements"] == 36
    assert results["swesmith_primary"]["fine"]["agreements"] == 41
    assert results["swesmith_primary"]["family"]["agreements"] == 41
    sensitivity = results["aidev_all100_sensitivity"]
    assert (sensitivity["agreements"], sensitivity["n"]) == (65, 100)
    assert sensitivity["cohens_kappa"] == pytest.approx(SOURCE_ALL100_KAPPA, abs=1e-9)
    assert sensitivity["unassigned_vs_unassigned_cases"] == 34
    families = results["generation_family"]["families"]
    assert (families["procedural"]["agreements"], families["procedural"]["n"]) == (6, 34)
    assert (families["llm"]["agreements"], families["llm"]["n"]) == (20, 36)
    assert (families["mirror"]["agreements"], families["mirror"]["n"]) == (15, 28)
    assert (families["combine"]["agreements"], families["combine"]["n"]) == (0, 2)


def test_results_json_procedural_comparison(results):
    primary = [
        block
        for block in results["procedural_vs_nonprocedural"]["comparisons"]
        if block["comparison"] == "procedural_vs_nonprocedural"
        and block["metric_level"] == "family"
    ]
    assert len(primary) == 1
    block = primary[0]
    assert block["table_2x2_row_major"] == [[6, 28], [35, 31]]
    assert block["procedural_agreements"] == 6 and block["n_procedural"] == 34
    assert block["comparator_agreements"] == 35 and block["n_comparator"] == 66
    assert block["fisher_exact"]["alternative"] == "two-sided"
    assert block["fisher_exact"]["p_value"] < 0.01
    assert block["risk_difference"]["ci_high"] < 0.0
    assert block["permutation_test"]["label"] == (
        "exploratory permutation robustness check"
    )
    # both levels and both contrasts are emitted
    levels = {
        (b["comparison"], b["metric_level"])
        for b in results["procedural_vs_nonprocedural"]["comparisons"]
    }
    assert levels == {
        ("procedural_vs_nonprocedural", "family"),
        ("procedural_vs_nonprocedural", "fine"),
        ("procedural_vs_llm_mirror", "family"),
        ("procedural_vs_llm_mirror", "fine"),
    }


def test_csv_column_names(script_runs):
    sensitivity = read_csv("aidev_denominator_sensitivity.csv")
    assert {
        "analysis_population",
        "n",
        "agreements",
        "agreement_rate",
        "kappa",
        "definition",
    } <= set(sensitivity[0])

    intervals = read_csv("agreement_confidence_intervals.csv")
    assert {
        "corpus",
        "subset",
        "metric_level",
        "n",
        "agreements",
        "agreement_rate",
        "ci_method",
        "ci_low",
        "ci_high",
    } <= set(intervals[0])

    bootstrap = read_csv("bootstrap_summary.csv")
    assert {
        "point_estimate",
        "ci_low",
        "ci_high",
        "valid_replicates",
        "undefined_replicates",
        "seed",
    } <= set(bootstrap[0])


def test_bootstrap_csv_covers_the_eight_analysis_populations(script_runs):
    rows = read_csv("bootstrap_summary.csv")
    assert {row["analysis_population"] for row in rows} == {
        "aidev_primary_fine",
        "aidev_primary_family",
        "aidev_all100_fine",
        "swesmith_fine",
        "swesmith_family",
        "swesmith_llm_family",
        "swesmith_mirror_family",
        "swesmith_procedural_family",
    }
    for row in rows:
        assert int(row["seed"]) == 20260906
        assert int(row["replicates"]) == 10000
        assert int(row["valid_replicates"]) + int(row["undefined_replicates"]) == 10000
        assert float(row["ci_low"]) <= float(row["point_estimate"]) <= float(
            row["ci_high"]
        )


def test_combine_gets_no_substantive_interval(script_runs):
    rows = {
        row["analysis_population"]: row
        for row in read_csv("agreement_confidence_intervals.csv")
    }
    combine = rows["swesmith_combine_family"]
    assert combine["n"] == "2"
    assert combine["ci_low"] == "" and combine["ci_high"] == ""
    assert "not reported" in combine["ci_method"]


def test_report_structure_and_required_sentences(script_runs):
    text = (paths.PHASE1B_DIR / "robustness_report.md").read_text(encoding="utf-8")
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert headings == [
        "## 1. Purpose",
        "## 2. Frozen inputs",
        "## 3. Primary Phase 1A result",
        "## 4. AIDev denominator sensitivity",
        "## 5. Uncertainty intervals",
        "## 6. Generation-mechanism robustness",
        "## 7. Exploratory statistical comparison",
        "## 8. Interpretation",
        "## 9. Limitations",
        "## 10. Phase 1B conclusion",
    ]
    assert "> No reviewer classifications were changed." in text
    assert (
        "> If the AIDev-vs-SWE-smith gap remains under all-100 sensitivity and "
        "the procedural effect remains large with uncertainty quantified, "
        "Phase 1 is considered robust enough to freeze before beginning the "
        "external-taxonomy control experiment."
    ) in text
    assert (
        "taxonomy transfer being substantially weaker on SWE-smith than on "
        "AIDev and particularly weak for procedural mutations."
    ) in text
    assert "reviewer agreement was lower among procedurally generated cases" in text


def test_report_uses_no_causal_language(script_runs):
    for name in ("robustness_report.md", "notes.md"):
        text = (paths.PHASE1B_DIR / name).read_text(encoding="utf-8").lower()
        for forbidden in (
            "causes disagreement",
            "causes reviewer",
            "leads to disagreement",
            "because procedural generation",
        ):
            assert forbidden not in text


def test_report_states_the_limitations(script_runs):
    text = (paths.PHASE1B_DIR / "robustness_report.md").read_text(encoding="utf-8")
    for needle in (
        "two LLM reviewers",
        "not ground-truth validity",
        "in-sample",
        "Python",
        "multilingual",
        "n = 2",
        "exploratory",
        "No causal claim",
        "category-frequency",
    ):
        assert needle in text, needle


def test_notes_document_the_all100_label_construction(script_runs):
    text = (paths.PHASE1B_DIR / "notes.md").read_text(encoding="utf-8")
    assert "compare_reviews.py" in text
    assert "UNASSIGNED" in text
    assert "0.5531154239019408" in text
    assert "nontechnical rejection" in text
    assert "Newcombe" in text
    assert "20260906" in text


def test_report_labels_the_derived_family_variant_clearly(script_runs, results):
    derived = results["aidev_all100_sensitivity"]["derived_family_variant"]
    assert derived["definition"].startswith("DERIVED VARIANT")
    text = (paths.PHASE1B_DIR / "robustness_report.md").read_text(encoding="utf-8")
    assert "derived family variant" in text
    assert "not the source study's" in text


def test_agreement_rate_columns_are_consistent_with_the_counts(script_runs):
    for row in read_csv("agreement_confidence_intervals.csv"):
        assert float(row["agreement_rate"]) == pytest.approx(
            int(row["agreements"]) / int(row["n"]), abs=1e-9
        )


def walk_keys(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from walk_keys(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_keys(value)


def test_no_phase1b_output_hardcodes_a_checkpoint_expectation(script_runs, results):
    """Expected values are assertions in the script, never emitted as results."""
    assert not [key for key in walk_keys(results) if key.startswith("expected")]
    for name in ("robustness_results.json", "aidev_denominator_sensitivity.csv"):
        text = (paths.PHASE1B_DIR / name).read_text(encoding="utf-8")
        assert "checkpoint" not in text.lower()


def test_label_distributions_are_untouched(results, aidev_reviews):
    """The sensitivity analysis reads labels; it never rewrites one."""
    codex = aidev_reviews["codex"]
    counts = Counter(codex[c]["failure_pattern"] for c in sorted(codex))
    assert counts[UNASSIGNED] == 43
    assert sum(counts.values()) == 100
