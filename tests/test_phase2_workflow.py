"""The workflow state machine, the write boundary and the finalization lock."""

from __future__ import annotations

import json

import pytest

from agentfailuretransfer.hashing import sha256_file
from agentfailuretransfer.phase2 import Phase2Error
from agentfailuretransfer.phase2.freeze import (
    build_manifest,
    freeze_manifest_sha256,
    write_manifest,
)
from agentfailuretransfer.phase2.paths import Phase2Paths
from agentfailuretransfer.phase2.state import (
    ANALYZED,
    BOTH_COMPLETE,
    CLAUDE_COMPLETE,
    CODEX_COMPLETE,
    FROZEN_PRE_REVIEW,
    SETUP,
    STATE_RANK,
    assert_not_finalized,
    assert_state_at_least,
    assert_write_boundary,
    compute_state,
    compute_status,
    finalize,
    is_finalized,
    save_case,
)
from agentfailuretransfer.phase2.taxonomy import taxonomy_fingerprint
from phase2_fixtures import TOY_CASE_IDS, build_toy_root, toy_record


@pytest.fixture
def toy(tmp_path):
    return Phase2Paths(build_toy_root(tmp_path / "toy"))


def freeze(paths: Phase2Paths) -> None:
    write_manifest(paths, build_manifest(paths))


def seal(paths: Phase2Paths, reviewer: str) -> None:
    records = [toy_record(case_id) for case_id in TOY_CASE_IDS]
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


# ---------------------------------------------------------------------------
# the write boundary
# ---------------------------------------------------------------------------
def test_write_boundary_accepts_inside_the_reviewer_directory(toy):
    target = toy.reviewer_cases("claude") / "TOY_001.yaml"
    assert assert_write_boundary(toy, "claude", target) == target.resolve()


@pytest.mark.parametrize(
    "relative",
    [
        "taxonomy/odc_defect_type_v1.yaml",
        "data/review_packets/TOY_001/packet.json",
        "reviews/codex/cases/TOY_001.json",
        "FREEZE_MANIFEST.json",
        "../escape.txt",
    ],
)
def test_write_boundary_refuses_anything_outside(toy, relative):
    with pytest.raises(Phase2Error, match="write boundary"):
        assert_write_boundary(toy, "claude", toy.root / relative)


def test_write_boundary_refuses_a_traversal_back_into_the_other_reviewer(toy):
    sneaky = toy.reviewer_cases("claude") / ".." / ".." / "codex" / "cases" / "x.json"
    with pytest.raises(Phase2Error, match="write boundary"):
        assert_write_boundary(toy, "claude", sneaky)


def test_saving_a_case_only_ever_touches_the_reviewer_directory(toy):
    before = {path for path in toy.root.rglob("*") if path.is_file()}
    save_case(toy, "claude", toy_record("TOY_001"))
    after = {path for path in toy.root.rglob("*") if path.is_file()}
    for path in after - before:
        assert toy.reviewer_dir("claude") in path.parents


# ---------------------------------------------------------------------------
# the finalization lock
# ---------------------------------------------------------------------------
def test_finalization_lock_refuses_further_case_writes(toy):
    freeze(toy)
    seal(toy, "claude")
    assert is_finalized(toy, "claude")
    with pytest.raises(Phase2Error, match="finalization lock"):
        save_case(toy, "claude", toy_record("TOY_001", pattern_confidence="LOW"))
    with pytest.raises(Phase2Error, match="finalization lock"):
        assert_not_finalized(toy, "claude")


def test_finalizing_twice_is_refused(toy):
    freeze(toy)
    seal(toy, "claude")
    with pytest.raises(Phase2Error, match="finalization lock"):
        seal(toy, "claude")


def test_the_lock_is_per_reviewer(toy):
    freeze(toy)
    seal(toy, "claude")
    assert_not_finalized(toy, "codex")  # does not raise
    save_case(toy, "codex", toy_record("TOY_001"))


def test_complete_marker_records_the_whole_seal(toy):
    freeze(toy)
    seal(toy, "claude")
    marker = toy.reviewer_complete("claude").read_text(encoding="utf-8")
    metadata = json.loads(toy.reviewer_metadata("claude").read_text(encoding="utf-8"))
    for key in (
        "snapshot_manifest_sha256",
        "taxonomy_fingerprint",
        "freeze_manifest_sha256",
        "results_sha256",
        "case_count",
        "completed_at_utc",
    ):
        assert key in marker
    assert metadata["results_sha256"] == sha256_file(toy.reviewer_results("claude"))
    assert metadata["snapshot_manifest_sha256"] == sha256_file(toy.snapshot_manifest)
    assert metadata["freeze_manifest_sha256"] == sha256_file(toy.freeze_manifest)
    assert metadata["result_count"] == len(TOY_CASE_IDS)
    assert metadata["completed_at_utc"].endswith("Z")


def test_results_jsonl_is_sorted_canonical_and_field_limited(toy):
    freeze(toy)
    seal(toy, "codex")
    lines = toy.reviewer_results("codex").read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines]
    assert [record["case_id"] for record in records] == sorted(TOY_CASE_IDS)
    assert all(sorted(record) == sorted(toy_record("TOY_001")) for record in records)
    # canonical: sorted keys, no spaces
    assert lines[0] == json.dumps(records[0], sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# the state machine
# ---------------------------------------------------------------------------
def test_state_starts_at_setup(toy):
    assert compute_state(toy) == SETUP


def test_freezing_advances_to_frozen_pre_review(toy):
    freeze(toy)
    assert compute_state(toy) == FROZEN_PRE_REVIEW


def test_one_seal_then_both(toy):
    freeze(toy)
    seal(toy, "claude")
    assert compute_state(toy) == CLAUDE_COMPLETE
    seal(toy, "codex")
    assert compute_state(toy) == BOTH_COMPLETE


def test_codex_alone_gives_the_codex_state(toy):
    freeze(toy)
    seal(toy, "codex")
    assert compute_state(toy) == CODEX_COMPLETE


def test_the_two_single_reviewer_states_share_a_rank():
    assert STATE_RANK[CLAUDE_COMPLETE] == STATE_RANK[CODEX_COMPLETE]
    assert STATE_RANK[SETUP] < STATE_RANK[FROZEN_PRE_REVIEW] < STATE_RANK[CLAUDE_COMPLETE]
    assert STATE_RANK[CLAUDE_COMPLETE] < STATE_RANK[BOTH_COMPLETE] < STATE_RANK[ANALYZED]


def test_analysis_outputs_advance_to_analyzed(toy):
    freeze(toy)
    seal(toy, "claude")
    seal(toy, "codex")
    toy.analysis_dir.mkdir(parents=True, exist_ok=True)
    for path in toy.analysis_outputs:
        path.write_text("{}\n", encoding="utf-8")
    assert compute_state(toy) == ANALYZED


def test_freeze_drift_drops_the_state_back_to_setup(toy):
    freeze(toy)
    assert compute_state(toy) == FROZEN_PRE_REVIEW
    with toy.taxonomy_yaml.open("a", encoding="utf-8") as handle:
        handle.write("\n# drift\n")
    assert compute_state(toy) == SETUP


def test_a_tampered_results_file_breaks_the_seal(toy):
    freeze(toy)
    seal(toy, "claude")
    assert compute_state(toy) == CLAUDE_COMPLETE
    with toy.reviewer_results("claude").open("a", encoding="utf-8") as handle:
        handle.write("\n")
    status = compute_status(toy)
    assert status.state == FROZEN_PRE_REVIEW
    assert any("this review is void" in note for note in status.notes)


# ---------------------------------------------------------------------------
# the analysis gate
# ---------------------------------------------------------------------------
def test_analysis_is_blocked_before_both_complete(toy):
    freeze(toy)
    with pytest.raises(Phase2Error, match="BOTH_COMPLETE"):
        assert_state_at_least(toy, BOTH_COMPLETE)
    seal(toy, "claude")
    with pytest.raises(Phase2Error, match="BOTH_COMPLETE"):
        assert_state_at_least(toy, BOTH_COMPLETE)
    seal(toy, "codex")
    assert assert_state_at_least(toy, BOTH_COMPLETE).state == BOTH_COMPLETE


def test_assert_state_at_least_rejects_an_unknown_state(toy):
    with pytest.raises(Phase2Error, match="unknown workflow state"):
        assert_state_at_least(toy, "PUBLISHED")


def test_a_seal_without_a_freeze_is_reported_as_an_anomaly(toy):
    seal(toy, "claude")
    status = compute_status(toy)
    assert status.state == SETUP
    assert any(note.startswith("ANOMALY") for note in status.notes)
