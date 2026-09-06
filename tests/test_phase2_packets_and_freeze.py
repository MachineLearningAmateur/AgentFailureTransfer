"""The frozen evidence, and the freeze manifest.

The tests that touch the real 100 packets are read-only and skip cleanly when
``scripts/import_phase2_packets.py`` has not been run. They assert *identity*
with the Phase 1 evidence -- never a label, never an outcome. No study packet
is opened here for its content.
"""

from __future__ import annotations

import json

import pytest

from agentfailuretransfer import paths as repo_paths
from agentfailuretransfer.hashing import sha256_file
from agentfailuretransfer.phase2 import Phase2Error
from agentfailuretransfer.phase2.freeze import (
    build_manifest,
    check_drift,
    comparable,
    load_manifest,
    recommended_tag_command,
    verify_freeze_manifest,
    write_manifest,
)
from agentfailuretransfer.phase2.packets import (
    digest_from_file_hashes,
    expected_case_ids,
    load_snapshot_manifest,
    packet_digest,
    packet_file_hashes,
    study_case_ids,
    verify_packets,
)
from agentfailuretransfer.phase2.paths import Phase2Paths
from phase2_fixtures import TOY_CASE_IDS, build_toy_root

KNOWN_SNAPSHOT_SHA256 = "981694c07ffcc9ee9bcf00527d71a0c94b15884ebfc7d8aa537363b3f646a6de"
KNOWN_REVIEW_MANIFEST_SHA256 = "64e607800de2a08e4321b371d616841bbd4fbe6deaddb1321dfd355333caebfa"


@pytest.fixture
def toy(tmp_path):
    return Phase2Paths(build_toy_root(tmp_path / "toy"))


@pytest.fixture(scope="module")
def imported():
    paths = Phase2Paths(repo_paths.PHASE2_DIR)
    if not paths.snapshot_manifest.is_file() or not paths.review_packets.is_dir():
        pytest.skip("run scripts/import_phase2_packets.py first")
    return paths


# ---------------------------------------------------------------------------
# case ids and the digest algorithm
# ---------------------------------------------------------------------------
def test_the_hundred_expected_case_ids():
    ids = study_case_ids()
    assert len(ids) == 100
    assert ids[0] == "SWESMITH_001"
    assert ids[-1] == "SWESMITH_100"
    assert ids == sorted(ids)
    assert len(set(ids)) == 100


def test_the_digest_is_the_sorted_path_colon_hash_join(toy):
    """The algorithm, stated independently of the implementation."""
    import hashlib

    directory = toy.packet_dir("TOY_001")
    hashes = packet_file_hashes(directory)
    expected = hashlib.sha256(
        "\n".join(f"{name}:{digest}" for name, digest in sorted(hashes.items())).encode("utf-8")
    ).hexdigest()
    assert packet_digest(directory) == expected
    assert digest_from_file_hashes(hashes) == expected


def test_a_one_byte_change_changes_the_digest(toy):
    directory = toy.packet_dir("TOY_001")
    before = packet_digest(directory)
    with (directory / "specification.md").open("a", encoding="utf-8") as handle:
        handle.write("\n")
    assert packet_digest(directory) != before


def test_an_added_file_changes_the_digest(toy):
    directory = toy.packet_dir("TOY_001")
    before = packet_digest(directory)
    (directory / "extra.md").write_text("x\n", encoding="utf-8")
    assert packet_digest(directory) != before


# ---------------------------------------------------------------------------
# verification on the toy corpus
# ---------------------------------------------------------------------------
def test_toy_packets_verify(toy):
    verification = verify_packets(toy)
    assert verification.ok
    assert verification.checked_packets == len(TOY_CASE_IDS)
    assert expected_case_ids(toy) == sorted(TOY_CASE_IDS)


def test_a_tampered_packet_file_is_reported(toy):
    (toy.packet_dir("TOY_002") / "bug_diff.diff").write_text("x\n", encoding="utf-8")
    problems = verify_packets(toy).problems
    assert any("sha256" in problem for problem in problems)
    assert any("digest" in problem for problem in problems)


def test_an_unlisted_extra_file_is_reported(toy):
    (toy.packet_dir("TOY_002") / "notes.md").write_text("x\n", encoding="utf-8")
    assert any("not in the frozen manifest" in p for p in verify_packets(toy).problems)


def test_an_unlisted_extra_packet_directory_is_reported(toy):
    (toy.review_packets / "TOY_009").mkdir()
    (toy.review_packets / "TOY_009" / "packet.json").write_text("{}", encoding="utf-8")
    assert any("TOY_009" in p for p in verify_packets(toy).problems)


def test_a_missing_snapshot_manifest_is_a_hard_failure(tmp_path):
    with pytest.raises(Phase2Error, match="snapshot manifest is missing"):
        load_snapshot_manifest(tmp_path / "nope.json")


# ---------------------------------------------------------------------------
# the freeze manifest
# ---------------------------------------------------------------------------
def test_freeze_manifest_is_reproducible(toy):
    first = build_manifest(toy, frozen_at_utc="2026-01-01T00:00:00Z")
    second = build_manifest(toy, frozen_at_utc="2099-12-31T23:59:59Z")
    assert comparable(first) == comparable(second)
    assert first["frozen_at_utc"] != second["frozen_at_utc"]


def test_freeze_manifest_covers_every_protocol_critical_artifact(toy):
    write_manifest(toy, build_manifest(toy))
    frozen = {entry["path"] for entry in load_manifest(toy)["files"]}
    assert "taxonomy/odc_defect_type_v1.yaml" in frozen
    assert "taxonomy/odc_defect_type_v1.md" in frozen
    assert "taxonomy/SOURCE_PROVENANCE.md" in frozen
    assert "schemas/odc_review_result.schema.json" in frozen
    assert "data/review_manifest.csv" in frozen
    assert "data/review_snapshot_manifest.json" in frozen
    assert "protocol/reviewer_prompt_claude.md" in frozen
    assert "protocol/reviewer_prompt_codex.md" in frozen
    for case_id in TOY_CASE_IDS:
        assert f"data/review_packets/{case_id}/packet.json" in frozen
    assert verify_freeze_manifest(toy) == []
    assert check_drift(toy) == []


def test_freeze_refuses_without_a_reviewer_prompt(toy):
    toy.reviewer_prompt("codex").unlink()
    with pytest.raises(Phase2Error, match="reviewer prompt for codex"):
        build_manifest(toy)


def test_freeze_refuses_without_the_rubric(toy):
    toy.taxonomy_yaml.unlink()
    with pytest.raises(Phase2Error, match="cannot freeze"):
        build_manifest(toy)


@pytest.mark.parametrize("relative", ["taxonomy/odc_defect_type_v1.yaml", "data/review_manifest.csv"])
def test_drift_in_a_frozen_file_is_detected(toy, relative):
    write_manifest(toy, build_manifest(toy))
    with (toy.root / relative).open("a", encoding="utf-8") as handle:
        handle.write("\n# drift\n")
    assert any("freeze drift" in problem for problem in check_drift(toy))


def test_a_new_file_under_a_frozen_directory_is_drift(toy):
    write_manifest(toy, build_manifest(toy))
    (toy.taxonomy_dir / "extra_notes.md").write_text("x\n", encoding="utf-8")
    assert any("not in the freeze manifest" in problem for problem in check_drift(toy))


def test_a_deleted_frozen_file_is_drift(toy):
    write_manifest(toy, build_manifest(toy))
    toy.taxonomy_provenance.unlink()
    assert check_drift(toy)


def test_verify_allows_missing_files_only_when_asked(toy):
    write_manifest(toy, build_manifest(toy))
    toy.reviewer_prompt("codex").unlink()
    assert verify_freeze_manifest(toy) != []
    assert verify_freeze_manifest(toy, allow_missing=True) == []


def test_the_tag_is_recommended_not_created(toy):
    write_manifest(toy, build_manifest(toy))
    command = recommended_tag_command()
    assert "phase2-odc-pre-review-frozen" in command
    assert "does not create the git tag" in command
    assert build_manifest(toy)["recommended_tag"] == "phase2-odc-pre-review-frozen"


# ---------------------------------------------------------------------------
# the real imported evidence (read-only; skipped before the import runs)
# ---------------------------------------------------------------------------
def test_imported_case_ids_are_the_hundred_frozen_cases(imported):
    assert expected_case_ids(imported) == study_case_ids()


def test_every_imported_packet_verifies(imported):
    verification = verify_packets(imported)
    assert verification.problems == []
    assert verification.checked_packets == 100


def test_imported_manifests_hash_to_the_phase1_values(imported):
    assert sha256_file(imported.snapshot_manifest) == KNOWN_SNAPSHOT_SHA256
    assert sha256_file(imported.review_manifest) == KNOWN_REVIEW_MANIFEST_SHA256


def test_the_phase2_evidence_is_the_phase1_evidence(imported):
    """Identity with the Phase 1 import, file for file."""
    if not repo_paths.SWESMITH_SNAPSHOT_MANIFEST.is_file():
        pytest.skip("run scripts/import_sources.py first")
    assert (
        imported.snapshot_manifest.read_bytes()
        == repo_paths.SWESMITH_SNAPSHOT_MANIFEST.read_bytes()
    )
    assert (
        imported.review_manifest.read_bytes()
        == repo_paths.SWESMITH_REVIEW_MANIFEST.read_bytes()
    )
    recorded = json.loads(repo_paths.SWESMITH_MANIFEST.read_text(encoding="utf-8"))
    assert recorded["snapshot_sha256"] == sha256_file(imported.snapshot_manifest)
    assert recorded["review_manifest_sha256"] == sha256_file(imported.review_manifest)


def test_import_provenance_records_the_pinned_commit_and_the_digest_rule(imported):
    if not imported.import_provenance.is_file():
        pytest.skip("run scripts/import_phase2_packets.py first")
    provenance = json.loads(imported.import_provenance.read_text(encoding="utf-8"))
    assert provenance["source_commit"] == provenance["source_pinned_commit"]
    assert provenance["source_commit"] == "0345139bf449f1fe9401f2a708d0d3b5961d14b2"
    assert provenance["packet_count"] == 100
    assert provenance["source_worktree_clean"] is True
    assert provenance["digest_reproduced_at_source"] is True
    assert provenance["digest_reproduced_after_copy"] is True
    assert provenance["leakage_scan"]["fatal_hits"] == []
    assert "sorted(files)" in provenance["packet_digest_algorithm"]


def test_the_reviews_directory_holds_no_review_output():
    """Phase 2 reviews/ must stay empty until a review is authorized and run."""
    reviews = repo_paths.PHASE2_REVIEWS_DIR
    if not reviews.is_dir():
        pytest.skip("the Phase 2 reviews directory has not been created")
    stray = [
        path.relative_to(reviews).as_posix()
        for path in reviews.rglob("*")
        if path.is_file() and path.name != ".gitkeep"
    ]
    assert stray == [], f"unexpected Phase 2 review output: {stray}"
