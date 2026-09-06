"""Manifest schema, hash verification, and the tampering negative case."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from agentfailuretransfer.hashing import sha256_file
from agentfailuretransfer.manifest import (
    MANIFEST_FILE_ENTRY_KEYS,
    MANIFEST_REQUIRED_KEYS,
    validate_manifest_schema,
    verify_manifest_hashes,
)

PINNED = {
    "AIBugAnalysis": "85e4bf9caf0a63436a1a305592d82294536ccd8e",
    "SWE-Smith-Bug-Analysis": "0345139bf449f1fe9401f2a708d0d3b5961d14b2",
}


@pytest.fixture(params=["aidev", "swesmith"])
def manifest(request, aidev_manifest, swesmith_manifest):
    return aidev_manifest if request.param == "aidev" else swesmith_manifest


def test_manifest_schema_is_valid(manifest):
    assert validate_manifest_schema(manifest) == []


def test_manifest_has_every_required_key(manifest):
    for key in MANIFEST_REQUIRED_KEYS:
        assert key in manifest


def test_manifest_file_entries_are_well_formed(manifest):
    assert manifest["files"]
    for entry in manifest["files"]:
        for key in MANIFEST_FILE_ENTRY_KEYS:
            assert key in entry
        assert len(entry["sha256"]) == 64
        assert entry["bytes"] > 0
        assert not entry["imported_path"].startswith("/")


def test_manifest_is_pinned_to_the_expected_commit(manifest):
    assert manifest["commit_sha"] == PINNED[manifest["name"]]
    assert manifest["pinned_commit_sha"] == PINNED[manifest["name"]]
    assert manifest["commit_matches_pin"] is True
    assert manifest["source_branch"] == "main"


def test_manifest_declares_the_frozen_taxonomy_version(manifest):
    assert manifest["taxonomy_version"] == "aidev_failure_taxonomy_v1"


def test_manifest_roles_are_distinct(aidev_manifest, swesmith_manifest):
    assert aidev_manifest["role"] == "real_agent_failure_source"
    assert swesmith_manifest["role"] == "synthetic_training_bug_source"


def test_reference_scripts_are_cited_but_not_imported(manifest, repo_root):
    imported = {entry["imported_path"] for entry in manifest["files"]}
    assert manifest["reference_scripts"]
    for entry in manifest["reference_scripts"]:
        assert entry["imported"] is False
        assert len(entry["sha256"]) == 64
        # A cited script must not have been copied under any imported path.
        assert not any(path.endswith(Path(entry["source_path"]).name) for path in imported)


def test_all_imported_hashes_verify(manifest, repo_root):
    assert verify_manifest_hashes(manifest, repo_root) == []


def test_tampered_copy_is_detected(manifest, repo_root, tmp_path):
    """Negative case: mutate a temp copy of the tree and expect a hash failure."""
    entry = next(e for e in manifest["files"] if e["imported_path"].endswith(".jsonl"))
    staged = tmp_path / entry["imported_path"]
    staged.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(repo_root / entry["imported_path"], staged)

    # Untampered copy verifies.
    assert verify_manifest_hashes({"files": [entry]}, tmp_path) == []

    # A single appended byte must be caught.
    with staged.open("ab") as handle:
        handle.write(b"\n")
    problems = verify_manifest_hashes({"files": [entry]}, tmp_path)
    assert problems
    assert any("sha256 mismatch" in p for p in problems)
    assert sha256_file(staged) != entry["sha256"]


def test_missing_file_is_detected(manifest, tmp_path):
    entry = manifest["files"][0]
    problems = verify_manifest_hashes({"files": [entry]}, tmp_path)
    assert problems == [f"missing imported file: {entry['imported_path']}"]


def test_schema_rejects_a_broken_manifest(manifest):
    broken = json.loads(json.dumps(manifest))
    broken["commit_sha"] = "not-a-sha"
    broken["files"][0].pop("sha256")
    problems = validate_manifest_schema(broken)
    assert any("commit_sha" in p for p in problems)
    assert any("missing key: sha256" in p for p in problems)


def test_known_provenance_hashes(aidev_manifest, swesmith_manifest):
    mapping = "1ce7232047437f87e7116d84b369e4f820e854481cbc744faf3b1d4c1af60985"
    taxonomy = "ecf76f0d752afd2632d4a2825b648a36cce4c16926782aec18fd4e2637fe4cc7"
    for manifest in (aidev_manifest, swesmith_manifest):
        assert manifest["family_mapping_sha256"] == mapping
        assert manifest["taxonomy_sha256"] == taxonomy
    assert (
        swesmith_manifest["snapshot_sha256"]
        == "981694c07ffcc9ee9bcf00527d71a0c94b15884ebfc7d8aa537363b3f646a6de"
    )
    assert (
        swesmith_manifest["review_manifest_sha256"]
        == "64e607800de2a08e4321b371d616841bbd4fbe6deaddb1321dfd355333caebfa"
    )
