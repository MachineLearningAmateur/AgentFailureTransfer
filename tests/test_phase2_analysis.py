"""The Phase 2 ODC analysis: its gate, its arithmetic, and its determinism.

Everything here runs against a **toy** Phase 2 root in ``tmp_path`` whose case
ids are ``TOY_001``..``TOY_003``, against a toy Phase 1 label set, a toy family
mapping and a toy generation crosswalk written in this file. No study case, no
study label and no study crosswalk row is involved, and nothing is written
inside the repository.

The statistics are checked against hand computations rather than against the
real corpus, and no test asserts anything about what the real Phase 2 result
should be. That is deliberate: a test suite that encoded a desired scientific
outcome would make the experiment unfalsifiable.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from math import comb
from pathlib import Path

import pytest

from agentfailuretransfer import paths as repo_paths
from agentfailuretransfer.agreement import agreement as agreement_block
from agentfailuretransfer.hashing import sha256_file
from agentfailuretransfer.phase2 import Phase2Error
from agentfailuretransfer.phase2 import analysis
from agentfailuretransfer.phase2.freeze import (
    build_manifest,
    freeze_manifest_sha256,
    write_manifest,
)
from agentfailuretransfer.phase2.paths import REVIEWERS, Phase2Paths
from agentfailuretransfer.phase2.state import (
    ANALYZED,
    BOTH_COMPLETE,
    CLAUDE_COMPLETE,
    STATE_RANK,
    compute_state,
    finalize,
    save_case,
)
from agentfailuretransfer.phase2.taxonomy import (
    DEFECT_TYPES,
    SENTINEL_DEFECT_TYPE,
    TAXONOMY_FITS,
    taxonomy_fingerprint,
)
from agentfailuretransfer.stats import cohen_kappa_or_none
from agentfailuretransfer.taxonomy import FINE_LABELS
from phase2_fixtures import TOY_CASE_IDS, build_toy_root, toy_record

SCRIPT = repo_paths.REPO_ROOT / "scripts" / "analyze_phase2_odc.py"

# ---------------------------------------------------------------------------
# Toy labels. Hand-chosen so every count below can be verified by eye.
# ---------------------------------------------------------------------------
#: ODC: case 1 agrees, cases 2 and 3 do not. claude records one AMBIGUOUS fit
#: and one UNCLASSIFIABLE sentinel; codex records neither.
TOY_ODC: dict[str, dict[str, tuple[str, str, str]]] = {
    "claude": {
        "TOY_001": ("ALGORITHM", "DIRECT", "HIGH"),
        "TOY_002": ("CHECKING", "AMBIGUOUS", "MEDIUM"),
        "TOY_003": (SENTINEL_DEFECT_TYPE, "OUT_OF_SCOPE", "LOW"),
    },
    "codex": {
        "TOY_001": ("ALGORITHM", "DIRECT", "MEDIUM"),
        "TOY_002": ("ASSIGNMENT", "DIRECT", "LOW"),
        "TOY_003": ("ALGORITHM", "DIRECT", "HIGH"),
    },
}

#: Phase 1: family agreement on cases 1 and 2, fine agreement on case 2 only.
TOY_PHASE1: dict[str, dict[str, str]] = {
    "claude": {
        "TOY_001": "misdiagnosed_root_cause",
        "TOY_002": "vacuous_verification",
        "TOY_003": "wrong_baseline_or_branch",
    },
    "codex": {
        "TOY_001": "false_premise_about_existing_code",
        "TOY_002": "vacuous_verification",
        "TOY_003": "broke_existing_contract_or_behavior",
    },
}

#: A toy family mapping. It must cover exactly the frozen fine labels, because
#: that is what ``taxonomy.load_family_mapping`` enforces; the family names are
#: invented for this test and mean nothing.
TOY_FAMILIES: dict[str, list[str]] = {
    "TOY_FAMILY_X": [
        "masked_symptom_instead_of_fixing",
        "false_premise_about_existing_code",
        "incomplete_change_propagation",
        "misdiagnosed_root_cause",
    ],
    "TOY_FAMILY_Y": [
        "broke_existing_contract_or_behavior",
        "disproportionate_or_duplicative_solution",
        "vacuous_verification",
        "violated_project_constraint_or_convention",
    ],
    "TOY_FAMILY_Z": [
        "unverified_trial_and_error",
        "wrong_baseline_or_branch",
        "OTHER_TECHNICAL_PATTERN",
    ],
}

TOY_GENERATION = {
    "TOY_001": "procedural",
    "TOY_002": "llm",
    "TOY_003": "mirror",
}

EXPECTED_ODC_AGREE = [1, 0, 0]
EXPECTED_PHASE1_FAMILY_AGREE = [1, 1, 0]
EXPECTED_PHASE1_FINE_AGREE = [0, 1, 0]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def odc_record(reviewer: str, case_id: str) -> dict:
    defect, fit, confidence = TOY_ODC[reviewer][case_id]
    return toy_record(
        case_id,
        odc_defect_type=defect,
        taxonomy_fit=fit,
        pattern_confidence=confidence,
    )


def freeze(paths: Phase2Paths) -> None:
    write_manifest(paths, build_manifest(paths))


def seal(paths: Phase2Paths, reviewer: str) -> None:
    records = [odc_record(reviewer, case_id) for case_id in TOY_CASE_IDS]
    for record in records:
        save_case(paths, reviewer, record)
    finalize(
        paths,
        reviewer,
        records,
        taxonomy_fingerprint=taxonomy_fingerprint(paths.taxonomy_yaml, paths.schema),
        snapshot_manifest_sha256=sha256_file(paths.snapshot_manifest),
        freeze_manifest_sha256=freeze_manifest_sha256(paths),
        case_id_universe="NON_STUDY",
    )


def write_phase1_inputs(directory: Path) -> analysis.Phase1Inputs:
    """A complete toy Phase 1 side, written under ``directory``."""
    directory.mkdir(parents=True, exist_ok=True)
    import yaml

    for reviewer in ("claude", "codex"):
        (directory / f"{reviewer}_review_results.jsonl").write_text(
            "".join(
                json.dumps({"case_id": case_id, "failure_pattern": label}) + "\n"
                for case_id, label in sorted(TOY_PHASE1[reviewer].items())
            ),
            encoding="utf-8",
        )
    (directory / "toy_families.yaml").write_text(
        yaml.safe_dump(TOY_FAMILIES, sort_keys=True), encoding="utf-8"
    )
    with (directory / "toy_crosswalk.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["case_id", "method_family"])
        for case_id, family in sorted(TOY_GENERATION.items()):
            writer.writerow([case_id, family])
    (directory / "toy_source_manifest.json").write_text(
        json.dumps({"commit_sha": "0" * 40, "repository": "toy/source"}, indent=2) + "\n",
        encoding="utf-8",
    )

    inputs = analysis.Phase1Inputs(
        codex_results=directory / "codex_review_results.jsonl",
        claude_results=directory / "claude_review_results.jsonl",
        family_mapping=directory / "toy_families.yaml",
        crosswalk=directory / "toy_crosswalk.csv",
        headline_results=directory / "toy_headline.json",
        source_manifest=directory / "toy_source_manifest.json",
    )
    labels = analysis.load_phase1_labels(inputs, list(TOY_CASE_IDS))
    family = agreement_block(labels.family["claude"], labels.family["codex"])
    fine = agreement_block(labels.fine["claude"], labels.fine["codex"])
    (directory / "toy_headline.json").write_text(
        json.dumps(
            {
                "swesmith": {
                    "family": {
                        "n": family["n"],
                        "exact_agreements": family["exact_agreements"],
                        "cohens_kappa": family["cohens_kappa"],
                    },
                    "fine_grained": {
                        "n": fine["n"],
                        "exact_agreements": fine["exact_agreements"],
                        "cohens_kappa": fine["cohens_kappa"],
                    },
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return inputs


@pytest.fixture
def toy(tmp_path):
    return Phase2Paths(build_toy_root(tmp_path / "toy"))


@pytest.fixture
def sealed(toy):
    freeze(toy)
    seal(toy, "claude")
    seal(toy, "codex")
    return toy


@pytest.fixture
def phase1_inputs(tmp_path):
    return write_phase1_inputs(tmp_path / "phase1_toy")


def run_script(paths: Phase2Paths, inputs: analysis.Phase1Inputs, *extra: str):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(paths.root),
            "--phase1-codex",
            str(inputs.codex_results),
            "--phase1-claude",
            str(inputs.claude_results),
            "--phase1-family-mapping",
            str(inputs.family_mapping),
            "--phase1-crosswalk",
            str(inputs.crosswalk),
            "--phase1-headline-results",
            str(inputs.headline_results),
            "--phase1-source-manifest",
            str(inputs.source_manifest),
            *extra,
        ],
        capture_output=True,
        text=True,
    )


def toy_reviews(paths: Phase2Paths) -> analysis.OdcReviews:
    return analysis.load_odc_reviews(paths, expected_case_ids=list(TOY_CASE_IDS))


# ===========================================================================
# The gate
# ===========================================================================
def test_the_toy_mapping_covers_exactly_the_frozen_fine_labels():
    covered = {label for labels in TOY_FAMILIES.values() for label in labels}
    assert covered == set(FINE_LABELS)


def test_analysis_refuses_before_both_complete(toy):
    freeze(toy)
    with pytest.raises(Phase2Error, match="BOTH_COMPLETE"):
        toy_reviews(toy)

    seal(toy, "claude")
    assert compute_state(toy) == CLAUDE_COMPLETE
    with pytest.raises(Phase2Error, match="BOTH_COMPLETE"):
        toy_reviews(toy)

    seal(toy, "codex")
    assert compute_state(toy) == BOTH_COMPLETE
    assert toy_reviews(toy).n == len(TOY_CASE_IDS)


def test_generation_metadata_is_joined_only_after_completion(toy, phase1_inputs):
    freeze(toy)
    seal(toy, "claude")
    with pytest.raises(Phase2Error, match="BOTH_COMPLETE"):
        analysis.load_generation_crosswalk(
            toy, phase1_inputs.crosswalk, case_ids=list(TOY_CASE_IDS)
        )
    seal(toy, "codex")
    joined = analysis.load_generation_crosswalk(
        toy, phase1_inputs.crosswalk, case_ids=list(TOY_CASE_IDS)
    )
    assert joined == TOY_GENERATION


def test_a_tampered_seal_closes_the_gate_again(sealed):
    assert toy_reviews(sealed).n == 3
    with sealed.reviewer_results("codex").open("a", encoding="utf-8") as handle:
        handle.write("\n")
    with pytest.raises(Phase2Error, match="BOTH_COMPLETE"):
        toy_reviews(sealed)


def test_mismatched_case_id_sets_are_refused(sealed):
    with pytest.raises(Phase2Error, match="expected"):
        analysis.load_odc_reviews(sealed, expected_case_ids=["TOY_001", "TOY_002"])


# ===========================================================================
# ODC endpoints
# ===========================================================================
def test_odc_agreement_matches_the_hand_computation(sealed):
    reviews = toy_reviews(sealed)
    assert reviews.agree_indicators() == EXPECTED_ODC_AGREE

    endpoints = analysis.odc_endpoints(reviews)
    defect = endpoints["defect_type"]
    assert defect["n"] == 3
    assert defect["exact_agreements"] == 1
    assert defect["agreement_rate"] == pytest.approx(1 / 3)

    # Hand computation of the unweighted kappa on these three cases.
    # claude: ALGORITHM, CHECKING, UNCLASSIFIABLE; codex: ALGORITHM, ASSIGNMENT,
    # ALGORITHM. Expected agreement = (1/3 * 2/3) for ALGORITHM only = 2/9.
    expected_kappa = (1 / 3 - 2 / 9) / (1 - 2 / 9)
    assert defect["cohens_kappa"] == pytest.approx(expected_kappa)
    assert defect["cohens_kappa_or_none"] == pytest.approx(expected_kappa)


def test_taxonomy_fit_agreement_is_reported_separately(sealed):
    endpoints = analysis.odc_endpoints(toy_reviews(sealed))
    # claude: DIRECT, AMBIGUOUS, OUT_OF_SCOPE; codex: DIRECT, DIRECT, DIRECT.
    assert endpoints["taxonomy_fit"]["exact_agreements"] == 1
    assert endpoints["taxonomy_fit"]["n"] == 3


def test_unclassifiable_and_ambiguous_rates_per_reviewer(sealed):
    per_reviewer = analysis.odc_endpoints(toy_reviews(sealed))["per_reviewer"]
    assert per_reviewer["claude"]["unclassifiable_count"] == 1
    assert per_reviewer["claude"]["unclassifiable_rate"] == pytest.approx(1 / 3)
    assert per_reviewer["claude"]["ambiguous_count"] == 1
    assert per_reviewer["claude"]["ambiguous_rate"] == pytest.approx(1 / 3)
    assert per_reviewer["codex"]["unclassifiable_count"] == 0
    assert per_reviewer["codex"]["ambiguous_count"] == 0
    assert per_reviewer["codex"]["unclassifiable_rate"] == 0.0
    # The sentinel and the out-of-scope fit are two views of the same records.
    assert (
        per_reviewer["claude"]["taxonomy_fit_distribution"]["OUT_OF_SCOPE"]
        == per_reviewer["claude"]["unclassifiable_count"]
    )


def test_pattern_confidence_is_descriptive_only(sealed):
    per_reviewer = analysis.odc_endpoints(toy_reviews(sealed))["per_reviewer"]
    assert per_reviewer["claude"]["pattern_confidence_distribution"] == {
        "HIGH": 1,
        "MEDIUM": 1,
        "LOW": 1,
    }
    assert sum(per_reviewer["codex"]["pattern_confidence_distribution"].values()) == 3


# ===========================================================================
# Confusion matrix
# ===========================================================================
def test_confusion_matrix_shape_order_and_margins(sealed):
    reviews = toy_reviews(sealed)
    matrix = analysis.confusion_matrix(
        reviews.defect_types("claude"), reviews.defect_types("codex")
    )
    assert len(matrix) == len(DEFECT_TYPES) == 9
    assert all(len(row) == 9 for row in matrix)

    order = list(DEFECT_TYPES)
    assert order[0] == "FUNCTION" and order[-1] == SENTINEL_DEFECT_TYPE

    # Row sums are the row reviewer's label counts, column sums the column
    # reviewer's, and the grand total is n.
    for index, label in enumerate(order):
        assert sum(matrix[index]) == reviews.defect_types("claude").count(label)
        assert sum(row[index] for row in matrix) == reviews.defect_types("codex").count(
            label
        )
    assert sum(sum(row) for row in matrix) == reviews.n
    assert sum(matrix[i][i] for i in range(9)) == sum(reviews.agree_indicators())


def test_confusion_matrix_is_oriented_rows_claude_columns_codex(sealed):
    reviews = toy_reviews(sealed)
    endpoints = analysis.odc_endpoints(reviews)
    block = endpoints["confusion_matrix"]
    assert block["rows"] == "claude" and block["columns"] == "codex"
    order = block["categories"]
    counts = block["counts"]
    # TOY_003: claude UNCLASSIFIABLE, codex ALGORITHM. Asymmetric on purpose.
    row = order.index(SENTINEL_DEFECT_TYPE)
    column = order.index("ALGORITHM")
    assert counts[row][column] == 1
    assert counts[column][row] == 0


def test_confusion_matrix_rejects_an_unknown_label():
    with pytest.raises(ValueError, match="outside the frozen category list"):
        analysis.confusion_matrix(["ALGORITHM"], ["NOT_A_TYPE"])


# ===========================================================================
# McNemar
# ===========================================================================
def test_mcnemar_table_construction_on_a_known_pairing():
    baseline = [1, 1, 1, 1, 0, 0, 0, 0, 0, 0]
    comparison = [1, 1, 0, 0, 1, 1, 1, 0, 0, 0]
    table = analysis.mcnemar_table(baseline, comparison)
    assert table == {"a": 2, "b": 2, "c": 3, "d": 3, "n": 10}
    assert table["a"] + table["b"] == sum(baseline)
    assert table["a"] + table["c"] == sum(comparison)


def test_mcnemar_table_on_the_toy_root(sealed, phase1_inputs):
    reviews = toy_reviews(sealed)
    labels = analysis.load_phase1_labels(phase1_inputs, list(reviews.case_ids))
    assert labels.family_agree_indicators() == EXPECTED_PHASE1_FAMILY_AGREE
    assert labels.fine_agree_indicators() == EXPECTED_PHASE1_FINE_AGREE
    table = analysis.mcnemar_table(
        labels.family_agree_indicators(), reviews.agree_indicators()
    )
    assert table == {"a": 1, "b": 1, "c": 0, "d": 1, "n": 3}


def test_mcnemar_exact_p_value_against_a_hand_computation():
    # b = 2, c = 8: two-sided exact binomial on 10 discordant pairs.
    baseline = [1] * 2 + [0] * 8
    comparison = [0] * 2 + [1] * 8
    result = analysis.mcnemar_test(baseline, comparison)
    assert result["discordant_b_phase1_only"] == 2
    assert result["discordant_c_odc_only"] == 8
    by_hand = 2 * sum(comb(10, k) for k in range(3)) / 2**10
    assert result["p_value_two_sided"] == pytest.approx(by_hand)
    assert by_hand == pytest.approx(112 / 1024)


def test_mcnemar_reports_the_corrected_chi_square_as_reference_only():
    baseline = [1] * 2 + [0] * 8
    comparison = [0] * 2 + [1] * 8
    chi = analysis.mcnemar_test(baseline, comparison)["continuity_corrected_chi_square"]
    assert chi["statistic"] == pytest.approx((abs(2 - 8) - 1) ** 2 / 10)
    assert "REFERENCE ONLY" in chi["status"]


def test_mcnemar_with_no_discordant_pairs_is_defined():
    result = analysis.mcnemar_test([1, 0, 1], [1, 0, 1])
    assert result["discordant_pairs"] == 0
    assert result["p_value_two_sided"] == 1.0
    assert result["continuity_corrected_chi_square"]["statistic"] is None


def test_mcnemar_rejects_non_binary_indicators():
    with pytest.raises(ValueError, match="0/1"):
        analysis.mcnemar_table([2, 0], [1, 0])


# ===========================================================================
# Paired bootstrap
# ===========================================================================
def bootstrap_population(n: int = 40):
    """A synthetic paired population with room for both kappas to vary."""
    phase1_left, phase1_right, odc_left, odc_right = [], [], [], []
    for index in range(n):
        phase1_left.append("P" if index % 2 else "Q")
        phase1_right.append("P" if index % 3 else "Q")
        odc_left.append("ALGORITHM" if index % 4 else "CHECKING")
        odc_right.append("ALGORITHM" if index % 5 else "ASSIGNMENT")
    return phase1_left, phase1_right, odc_left, odc_right


def test_paired_bootstrap_is_reproducible_under_a_fixed_seed():
    population = bootstrap_population()
    first = analysis.paired_bootstrap_taxonomy_difference(*population, replicates=300)
    second = analysis.paired_bootstrap_taxonomy_difference(*population, replicates=300)
    assert first == second
    assert first["seed"] == analysis.SEED


def test_a_different_seed_gives_a_different_bootstrap():
    population = bootstrap_population()
    fixed = analysis.paired_bootstrap_taxonomy_difference(*population, replicates=300)
    other = analysis.paired_bootstrap_taxonomy_difference(
        *population, seed=analysis.SEED + 1, replicates=300
    )
    assert other["agreement_difference"]["point_estimate"] == pytest.approx(
        fixed["agreement_difference"]["point_estimate"]
    )
    assert (
        other["agreement_difference"]["bootstrap_mean"]
        != fixed["agreement_difference"]["bootstrap_mean"]
    )


def test_paired_bootstrap_point_estimates_are_the_observed_differences():
    phase1_left, phase1_right, odc_left, odc_right = bootstrap_population()
    result = analysis.paired_bootstrap_taxonomy_difference(
        phase1_left, phase1_right, odc_left, odc_right, replicates=100
    )
    n = len(phase1_left)
    observed = (
        sum(a == b for a, b in zip(odc_left, odc_right)) / n
        - sum(a == b for a, b in zip(phase1_left, phase1_right)) / n
    )
    assert result["agreement_difference"]["point_estimate"] == pytest.approx(observed)
    assert result["kappa_difference"]["point_estimate"] == pytest.approx(
        cohen_kappa_or_none(odc_left, odc_right)
        - cohen_kappa_or_none(phase1_left, phase1_right)
    )


def test_paired_bootstrap_counts_undefined_kappa_replicates_instead_of_zeroing():
    """A degenerate Phase 1 side: both reviewers used one and the same label."""
    n = 12
    phase1_left = ["SAME"] * n
    phase1_right = ["SAME"] * n
    odc_left = ["ALGORITHM" if index % 2 else "CHECKING" for index in range(n)]
    odc_right = ["ALGORITHM" if index % 3 else "CHECKING" for index in range(n)]
    result = analysis.paired_bootstrap_taxonomy_difference(
        phase1_left, phase1_right, odc_left, odc_right, replicates=200
    )
    kappa = result["kappa_difference"]
    assert kappa["undefined_replicates"] == 200
    assert kappa["undefined_replicates_phase1_side"] == 200
    assert kappa["valid_replicates"] == 0
    assert kappa["ci_low"] is None and kappa["ci_high"] is None
    assert kappa["point_estimate"] is None
    # The agreement difference is still defined for every replicate.
    assert result["agreement_difference"]["valid_replicates"] == 200
    assert result["agreement_difference"]["ci_low"] is not None


def test_paired_bootstrap_keeps_the_four_labels_of_a_case_together():
    """Shuffling the ODC side against the Phase 1 side changes the answer."""
    phase1_left, phase1_right, odc_left, odc_right = bootstrap_population()
    paired = analysis.paired_bootstrap_taxonomy_difference(
        phase1_left, phase1_right, odc_left, odc_right, replicates=400
    )
    broken = analysis.paired_bootstrap_taxonomy_difference(
        phase1_left,
        phase1_right,
        list(reversed(odc_left)),
        list(reversed(odc_right)),
        replicates=400,
    )
    assert (
        paired["kappa_difference"]["ci_low"] != broken["kappa_difference"]["ci_low"]
    )


def test_the_bootstrap_kappa_helper_matches_cohen_kappa_or_none():
    import numpy as np

    left = ["A", "B", "A", "C", "B", "A"]
    right = ["A", "C", "A", "C", "B", "B"]
    codes_left, codes_right, n_labels = analysis._encode(left, right)
    assert analysis._kappa_from_codes(
        codes_left, codes_right, n_labels
    ) == pytest.approx(cohen_kappa_or_none(left, right))
    empty = np.array([], dtype=np.int64)
    assert analysis._kappa_from_codes(empty, empty, n_labels) is None


def test_gap_bootstrap_counts_undefined_replicates():
    procedural = [1, 0, 0, 0]
    phase1 = [1, 1, 0, 0]
    odc = [0, 1, 1, 0]
    result = analysis.paired_bootstrap_gap_change(
        procedural, phase1, odc, replicates=300
    )
    assert result["valid_replicates"] + result["undefined_replicates"] == 300
    assert result["undefined_replicates"] > 0  # resamples with no procedural case
    assert result["point_estimate"] == pytest.approx(
        (2 / 3 - 0.0) - (1 / 3 - 1.0)
    )


# ===========================================================================
# Phase 1 side and its cross-check
# ===========================================================================
def test_phase1_labels_are_mapped_not_modified(phase1_inputs):
    labels = analysis.load_phase1_labels(phase1_inputs, list(TOY_CASE_IDS))
    assert labels.fine["claude"] == [
        TOY_PHASE1["claude"][case_id] for case_id in TOY_CASE_IDS
    ]
    assert labels.family["claude"] == [
        "TOY_FAMILY_X",
        "TOY_FAMILY_Y",
        "TOY_FAMILY_Z",
    ]


def test_phase1_crosscheck_passes_on_a_consistent_checkpoint(phase1_inputs):
    labels = analysis.load_phase1_labels(phase1_inputs, list(TOY_CASE_IDS))
    result = analysis.crosscheck_phase1_against_headline(
        labels, phase1_inputs.headline_results
    )
    assert result["agrees"] is True
    assert result["problems"] == []
    assert {check["level"] for check in result["checks"]} == {"family", "fine"}
    # Only recomputed values leave this function; nothing recorded is echoed.
    for check in result["checks"]:
        assert set(check) >= {"recomputed_exact_agreements", "recomputed_cohens_kappa"}
        assert not any(key.startswith("recorded") for key in check)


def test_phase1_crosscheck_fails_when_the_checkpoint_disagrees(phase1_inputs, tmp_path):
    labels = analysis.load_phase1_labels(phase1_inputs, list(TOY_CASE_IDS))
    recorded = json.loads(phase1_inputs.headline_results.read_text(encoding="utf-8"))
    recorded["swesmith"]["family"]["exact_agreements"] += 1
    perturbed = tmp_path / "perturbed_headline.json"
    perturbed.write_text(json.dumps(recorded), encoding="utf-8")
    result = analysis.crosscheck_phase1_against_headline(labels, perturbed)
    assert result["agrees"] is False
    assert any("exact agreements" in problem for problem in result["problems"])


# ===========================================================================
# Generation families and the procedural contrasts
# ===========================================================================
def test_generation_family_blocks_are_ordered_and_counted(sealed, phase1_inputs):
    reviews = toy_reviews(sealed)
    families = analysis.load_generation_crosswalk(
        sealed, phase1_inputs.crosswalk, case_ids=list(reviews.case_ids)
    )
    blocks = analysis.generation_family_blocks(reviews, families)
    assert [block["generation_family"] for block in blocks] == [
        "llm",
        "mirror",
        "procedural",
    ]
    assert sum(block["n"] for block in blocks) == reviews.n
    procedural = next(b for b in blocks if b["generation_family"] == "procedural")
    assert procedural["n"] == 1 and procedural["exact_agreements"] == 1
    for block in blocks:
        for reviewer in REVIEWERS:
            fits = block["per_reviewer"][reviewer]["taxonomy_fit_distribution"]
            assert set(fits) == set(TAXONOMY_FITS)
            assert sum(fits.values()) == block["n"]


def test_combine_would_be_flagged_as_carrying_no_substantive_claim():
    assert "no substantive claim" in analysis.NO_SUBSTANTIVE_CLAIM_NOTE


def test_compare_groups_matches_a_hand_built_two_by_two():
    result = analysis.compare_groups(
        [1, 0, 0, 0],
        [1, 1, 1, 0, 0, 0],
        comparison="toy",
        taxonomy="toy taxonomy",
    )
    assert result["table_2x2_row_major"] == [[1, 3], [3, 3]]
    assert result["group_a_rate"] == pytest.approx(0.25)
    assert result["group_b_rate"] == pytest.approx(0.5)
    assert result["gap_group_b_minus_group_a"] == pytest.approx(0.25)
    assert 0.0 <= result["fisher_exact"]["p_value"] <= 1.0
    assert result["fisher_exact"]["alternative"] == "two-sided"


def test_compare_groups_refuses_an_empty_group():
    with pytest.raises(ValueError, match="non-empty"):
        analysis.compare_groups([], [1, 0], comparison="toy")


# ===========================================================================
# Interpretation
# ===========================================================================
def interpretation(**overrides):
    arguments = {
        "phase1_agreement_rate": 0.41,
        "odc_agreement_rate": 0.41,
        "agreement_difference_ci": (-0.10, 0.10),
        "mcnemar_p_value": 0.9,
        "phase1_procedural_gap": 0.35,
        "odc_procedural_gap": 0.35,
    }
    arguments.update(overrides)
    return analysis.interpret_outcome(**arguments)


def test_interpretation_returns_outcome_a_when_agreement_jumps_and_the_gap_closes():
    result = interpretation(
        odc_agreement_rate=0.80,
        agreement_difference_ci=(0.25, 0.50),
        mcnemar_p_value=1e-6,
        odc_procedural_gap=0.02,
    )
    assert result["outcome"] == "A"
    assert result["interpretation"] == analysis.OUTCOME_INTERPRETATIONS["A"]
    assert (
        result["permitted_procedural_phrasing"]
        == analysis.PROCEDURAL_PHRASING_NARROWED
    )


def test_interpretation_returns_outcome_b_when_the_gap_persists():
    result = interpretation(
        odc_agreement_rate=0.80,
        agreement_difference_ci=(0.25, 0.50),
        mcnemar_p_value=1e-6,
        odc_procedural_gap=0.30,
    )
    assert result["outcome"] == "B"
    assert result["interpretation"] == analysis.OUTCOME_INTERPRETATIONS["B"]
    assert (
        result["permitted_procedural_phrasing"]
        == analysis.PROCEDURAL_PHRASING_PERSISTS
    )


def test_interpretation_returns_outcome_c_when_nothing_moves():
    result = interpretation()
    assert result["outcome"] == "C"
    assert result["interpretation"] == analysis.OUTCOME_INTERPRETATIONS["C"]


def test_interpretation_returns_outcome_d_when_odc_is_worse():
    result = interpretation(
        odc_agreement_rate=0.20,
        agreement_difference_ci=(-0.35, -0.08),
        mcnemar_p_value=0.001,
    )
    assert result["outcome"] == "D"
    assert result["interpretation"] == analysis.OUTCOME_INTERPRETATIONS["D"]


def test_an_inconclusive_result_is_never_promoted_out_of_c():
    # A large point difference whose interval straddles zero stays inconclusive.
    straddling = interpretation(
        odc_agreement_rate=0.80,
        agreement_difference_ci=(-0.05, 0.60),
        mcnemar_p_value=1e-6,
    )
    assert straddling["outcome"] == "C"
    # As does one whose McNemar p-value is not below the stated threshold.
    weak = interpretation(
        odc_agreement_rate=0.80,
        agreement_difference_ci=(0.25, 0.50),
        mcnemar_p_value=0.20,
    )
    assert weak["outcome"] == "C"


def test_a_nonpositive_odc_gap_carries_an_explicit_caveat():
    result = interpretation(
        odc_agreement_rate=0.80,
        agreement_difference_ci=(0.25, 0.50),
        mcnemar_p_value=1e-6,
        odc_procedural_gap=-0.20,
    )
    assert (
        result["permitted_procedural_phrasing"]
        == analysis.PROCEDURAL_PHRASING_NARROWED
    )
    assert "not positive" in result["procedural_phrasing_caveat"]
    # A genuine narrowing from a large gap needs no caveat.
    clean = interpretation(
        odc_agreement_rate=0.80,
        agreement_difference_ci=(0.25, 0.50),
        mcnemar_p_value=1e-6,
        odc_procedural_gap=0.05,
    )
    assert clean["procedural_phrasing_caveat"] == ""


def test_the_interpretation_states_its_thresholds_and_is_outcome_agnostic():
    result = interpretation()
    assert result["thresholds"] == analysis.INTERPRETATION_THRESHOLDS
    assert result["rule_applied"]
    assert "conditional" in result["conditional_reading"].lower()
    assert set(analysis.OUTCOME_INTERPRETATIONS) == {"A", "B", "C", "D"}
    # The four readings are stored verbatim and are not paraphrased anywhere.
    assert result["outcome"] in analysis.OUTCOME_INTERPRETATIONS


def test_every_outcome_is_reachable():
    reached = {
        interpretation()["outcome"],
        interpretation(
            odc_agreement_rate=0.80,
            agreement_difference_ci=(0.25, 0.50),
            mcnemar_p_value=1e-6,
            odc_procedural_gap=0.02,
        )["outcome"],
        interpretation(
            odc_agreement_rate=0.80,
            agreement_difference_ci=(0.25, 0.50),
            mcnemar_p_value=1e-6,
            odc_procedural_gap=0.30,
        )["outcome"],
        interpretation(
            odc_agreement_rate=0.20,
            agreement_difference_ci=(-0.35, -0.08),
            mcnemar_p_value=0.001,
        )["outcome"],
    }
    assert reached == {"A", "B", "C", "D"}


# ===========================================================================
# The script end to end, on the toy root
# ===========================================================================
def test_script_refuses_before_both_complete_and_writes_nothing(toy, phase1_inputs):
    freeze(toy)
    seal(toy, "claude")
    before = {path for path in toy.root.rglob("*")}
    result = run_script(toy, phase1_inputs)
    assert result.returncode == 1
    assert result.stderr.startswith("STOP:")
    assert "BOTH_COMPLETE" in result.stderr
    assert not toy.analysis_dir.exists()
    assert {path for path in toy.root.rglob("*")} == before


def test_script_runs_after_both_complete_and_reaches_analyzed(sealed, phase1_inputs):
    result = run_script(sealed, phase1_inputs)
    assert result.returncode == 0, result.stderr
    for name in (
        "odc_agreement.json",
        "odc_agreement.md",
        "odc_confusion.csv",
        "taxonomy_comparison.json",
        "taxonomy_comparison.md",
        "generation_method_analysis.csv",
    ):
        assert (sealed.analysis_dir / name).is_file(), name
    assert compute_state(sealed) == ANALYZED


def test_script_output_is_byte_identical_across_two_runs(sealed, phase1_inputs):
    assert run_script(sealed, phase1_inputs).returncode == 0
    first = {
        path.name: path.read_bytes() for path in sorted(sealed.analysis_dir.iterdir())
    }
    assert run_script(sealed, phase1_inputs).returncode == 0
    second = {
        path.name: path.read_bytes() for path in sorted(sealed.analysis_dir.iterdir())
    }
    assert first == second


def test_no_artifact_carries_a_timestamp(sealed, phase1_inputs):
    assert run_script(sealed, phase1_inputs).returncode == 0
    for path in sealed.analysis_dir.iterdir():
        text = path.read_text(encoding="utf-8")
        for needle in ("_at_utc", "generated_at", "20260906T", "Z\","):
            assert needle not in text, f"{path.name} contains {needle!r}"


def test_reports_carry_every_required_section_and_sentence(sealed, phase1_inputs):
    assert run_script(sealed, phase1_inputs).returncode == 0
    for name in ("odc_agreement.md", "taxonomy_comparison.md"):
        text = (sealed.analysis_dir / name).read_text(encoding="utf-8")
        assert "No Phase 1 reviewer classification was modified during Phase 2." in text
        for number in range(1, 17):
            assert f"## {number}. " in text, f"{name} is missing section {number}"
        assert "provenance" in text.lower()


def test_reports_make_no_causal_claim(sealed, phase1_inputs):
    assert run_script(sealed, phase1_inputs).returncode == 0
    forbidden = (" causes ", " caused by ", "because the generator")
    for name in ("odc_agreement.md", "taxonomy_comparison.md"):
        text = (sealed.analysis_dir / name).read_text(encoding="utf-8").lower()
        for needle in forbidden:
            assert needle not in text


def test_confusion_csv_matches_the_json_matrix(sealed, phase1_inputs):
    assert run_script(sealed, phase1_inputs).returncode == 0
    rows = list(
        csv.reader(
            (sealed.analysis_dir / "odc_confusion.csv")
            .read_text(encoding="utf-8")
            .splitlines()
        )
    )
    header, body = rows[0], rows[1:]
    assert header[0] == "claude_label"
    assert header[1:] == [f"codex_{label}" for label in DEFECT_TYPES]
    assert [row[0] for row in body] == list(DEFECT_TYPES)
    counts = [[int(cell) for cell in row[1:]] for row in body]
    payload = json.loads(
        (sealed.analysis_dir / "odc_agreement.json").read_text(encoding="utf-8")
    )
    assert counts == payload["odc"]["confusion_matrix"]["counts"]
    assert sum(sum(row) for row in counts) == payload["n_cases"]


def test_generation_csv_covers_every_family_present(sealed, phase1_inputs):
    assert run_script(sealed, phase1_inputs).returncode == 0
    rows = list(
        csv.DictReader(
            (sealed.analysis_dir / "generation_method_analysis.csv")
            .read_text(encoding="utf-8")
            .splitlines()
        )
    )
    assert [row["generation_family"] for row in rows] == ["llm", "mirror", "procedural"]
    assert sum(int(row["n"]) for row in rows) == 3
    for reviewer in REVIEWERS:
        assert f"{reviewer}_fit_DIRECT" in rows[0]
        assert f"{reviewer}_unclassifiable" in rows[0]


def test_json_artifacts_carry_the_provenance_block(sealed, phase1_inputs):
    assert run_script(sealed, phase1_inputs).returncode == 0
    for name in ("odc_agreement.json", "taxonomy_comparison.json"):
        payload = json.loads(
            (sealed.analysis_dir / name).read_text(encoding="utf-8")
        )
        provenance = payload["provenance"]
        assert provenance["taxonomy_fingerprint"] == taxonomy_fingerprint(
            sealed.taxonomy_yaml, sealed.schema
        )
        assert provenance["freeze_manifest_sha256"] == sha256_file(
            sealed.freeze_manifest
        )
        for reviewer in REVIEWERS:
            assert provenance["complete_marker_sha256"][reviewer] == sha256_file(
                sealed.reviewer_complete(reviewer)
            )
        assert set(provenance["phase1_source_sha256"]) >= {
            "phase1_claude_review_results",
            "phase1_codex_review_results",
            "phase1_family_mapping",
            "phase1_generation_crosswalk",
        }
        assert provenance["phase1_source_commit_sha"] == "0" * 40


def test_the_checkpoint_flag_stops_the_run_on_a_disagreeing_checkpoint(
    sealed, phase1_inputs, tmp_path
):
    recorded = json.loads(phase1_inputs.headline_results.read_text(encoding="utf-8"))
    recorded["swesmith"]["family"]["cohens_kappa"] = 0.999
    perturbed = tmp_path / "bad_headline.json"
    perturbed.write_text(json.dumps(recorded), encoding="utf-8")

    checked = run_script(
        sealed, phase1_inputs, "--phase1-headline-results", str(perturbed)
    )
    assert checked.returncode == 1
    assert checked.stderr.startswith("STOP:")
    assert not sealed.analysis_dir.exists()

    skipped = run_script(
        sealed,
        phase1_inputs,
        "--phase1-headline-results",
        str(perturbed),
        "--no-check-phase1",
    )
    assert skipped.returncode == 0, skipped.stderr


def test_no_recorded_checkpoint_number_reaches_an_artifact(sealed, phase1_inputs):
    assert run_script(sealed, phase1_inputs).returncode == 0
    payload = json.loads(
        (sealed.analysis_dir / "taxonomy_comparison.json").read_text(encoding="utf-8")
    )
    crosscheck = payload["phase1_crosscheck"]
    assert crosscheck["agrees"] is True
    for check in crosscheck["checks"]:
        # only recomputed values and booleans; no value copied from the file
        assert not any(key.startswith("recorded") for key in check)
        assert all(
            isinstance(value, (int, float, bool, str))
            for value in check.values()
        )
    assert crosscheck["kappa_tolerance"] == analysis.PHASE1_KAPPA_TOLERANCE


# ===========================================================================
# The real repository: the script must refuse there, and change nothing
# ===========================================================================
def test_the_real_analysis_refuses_while_no_review_exists():
    real = Phase2Paths(repo_paths.PHASE2_DIR)
    if STATE_RANK[compute_state(real)] >= STATE_RANK[BOTH_COMPLETE]:
        pytest.skip("both Phase 2 reviews are sealed; this guard no longer applies")
    before = sorted(
        path.name for path in real.analysis_dir.iterdir()
    ) if real.analysis_dir.is_dir() else []
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True
    )
    assert result.returncode == 1
    assert result.stderr.startswith("STOP:")
    after = sorted(
        path.name for path in real.analysis_dir.iterdir()
    ) if real.analysis_dir.is_dir() else []
    assert after == before
    assert all(name in {"README.md", ".gitkeep"} for name in after)
