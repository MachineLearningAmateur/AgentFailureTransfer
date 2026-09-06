"""Bringing one reviewer's sealed review home from its bundle.

Every test runs against a toy Phase 2 root in ``tmp_path`` -- ``TOY_001..003``,
never a study case -- and a real exported bundle built from it. The importer is
invoked as a subprocess, so the ``STOP:`` convention and the exit codes are
exercised exactly as an operator meets them.

Two properties are asserted everywhere: a refused import leaves the repository
untouched, and no import of any kind ever writes to the bundle.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from agentfailuretransfer import paths as repo_paths
from agentfailuretransfer.hashing import sha256_file
from agentfailuretransfer.phase2.bundle import export
from agentfailuretransfer.phase2.freeze import (
    build_manifest,
    freeze_manifest_sha256,
    write_manifest,
)
from agentfailuretransfer.phase2.paths import Phase2Paths
from agentfailuretransfer.phase2.state import (
    BOTH_COMPLETE,
    CLAUDE_COMPLETE,
    compute_state,
    finalize,
    progress,
    save_case,
)
from agentfailuretransfer.phase2.taxonomy import taxonomy_fingerprint
from phase2_fixtures import TOY_CASE_IDS, build_toy_root, toy_record

SCRIPT = repo_paths.REPO_ROOT / "scripts" / "import_phase2_review.py"

#: What a seal consists of, for the claude (YAML) and codex (JSON) reviewers.
SEAL_FILES = {
    reviewer: {
        *(f"cases/{case_id}{extension}" for case_id in TOY_CASE_IDS),
        "review_results.jsonl",
        "review_metadata.json",
        "COMPLETE",
    }
    for reviewer, extension in (("claude", ".yaml"), ("codex", ".json"))
}


def run_import(repo: Phase2Paths, bundle_root, reviewer: str, *extra: str):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--reviewer",
            reviewer,
            "--root",
            str(repo.root),
            "--bundle",
            str(bundle_root),
            *extra,
        ],
        capture_output=True,
        text=True,
    )


def tree_hashes(root) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def relative_files(root) -> set[str]:
    return {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }


@pytest.fixture
def repo(tmp_path) -> Phase2Paths:
    """A frozen toy Phase 2 root standing in for the repository side."""
    paths = Phase2Paths(build_toy_root(tmp_path / "repo"))
    write_manifest(paths, build_manifest(paths))
    return paths


def make_bundle(
    repo: Phase2Paths,
    reviewer: str,
    out,
    *,
    records=None,
    seal: bool = True,
    write_progress: bool = True,
) -> Phase2Paths:
    """Export a real bundle, run a toy review inside it, and seal it there."""
    export(repo, reviewer, out, repo_root=repo_paths.REPO_ROOT, source_commit="toy")
    bundle = Phase2Paths(out)
    records = [toy_record(case_id) for case_id in TOY_CASE_IDS] if records is None else records
    for record in records:
        save_case(bundle, reviewer, record)
    if write_progress:
        progress(bundle, reviewer, TOY_CASE_IDS)
    if seal:
        finalize(
            bundle,
            reviewer,
            records,
            taxonomy_fingerprint=taxonomy_fingerprint(bundle.taxonomy_yaml, bundle.schema),
            snapshot_manifest_sha256=sha256_file(bundle.snapshot_manifest),
            freeze_manifest_sha256=freeze_manifest_sha256(bundle),
            case_id_universe="NON_STUDY",
        )
    return bundle


def assert_repository_untouched(repo: Phase2Paths, reviewer: str) -> None:
    assert not repo.reviewer_complete(reviewer).is_file()
    assert not repo.reviewer_results(reviewer).is_file()
    assert not repo.reviewer_metadata(reviewer).is_file()
    assert list(repo.reviewer_cases(reviewer).iterdir()) == []
    assert not (repo.reviews_dir / f".{reviewer}.import-staging").exists()
    assert not (repo.reviews_dir / f".{reviewer}.import-replaced").exists()


# ---------------------------------------------------------------------------
# the success path
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("reviewer", ["claude", "codex"])
def test_import_copies_exactly_the_seal_and_sets_the_state(repo, tmp_path, reviewer):
    bundle = make_bundle(repo, reviewer, tmp_path / f"bundle_{reviewer}")
    before = tree_hashes(bundle.root)

    result = run_import(repo, bundle.root, reviewer)
    assert result.returncode == 0, result.stdout + result.stderr

    imported = repo.reviewer_dir(reviewer)
    assert relative_files(imported) == SEAL_FILES[reviewer]
    for relative in SEAL_FILES[reviewer]:
        assert sha256_file(imported / relative) == sha256_file(
            bundle.reviewer_dir(reviewer) / relative
        )

    state = "CLAUDE_COMPLETE" if reviewer == "claude" else "CODEX_COMPLETE"
    assert state in result.stdout
    assert compute_state(repo) == state
    # the other reviewer is neither read nor reported
    assert result.stdout.count("claude") + result.stdout.count("codex") == result.stdout.count(
        reviewer
    )
    # nothing was written to the bundle
    assert tree_hashes(bundle.root) == before


def test_progress_json_is_never_copied(repo, tmp_path):
    bundle = make_bundle(repo, "claude", tmp_path / "bundle_claude")
    assert bundle.reviewer_progress("claude").is_file()

    assert run_import(repo, bundle.root, "claude").returncode == 0
    assert not repo.reviewer_progress("claude").is_file()
    assert "progress.json" not in relative_files(repo.reviewer_dir("claude"))


def test_a_placeholder_already_in_the_repository_survives_the_swap(repo, tmp_path):
    keep = repo.reviewer_cases("codex") / ".gitkeep"
    keep.write_text("", encoding="utf-8")
    bundle = make_bundle(repo, "codex", tmp_path / "bundle_codex")

    assert run_import(repo, bundle.root, "codex").returncode == 0
    assert keep.is_file()


def test_both_imports_reach_both_complete_and_print_the_analysis_command(repo, tmp_path):
    claude = make_bundle(repo, "claude", tmp_path / "bundle_claude")
    codex = make_bundle(repo, "codex", tmp_path / "bundle_codex")

    first = run_import(repo, claude.root, "claude")
    assert first.returncode == 0, first.stderr
    assert BOTH_COMPLETE not in first.stdout
    assert compute_state(repo) == CLAUDE_COMPLETE

    second = run_import(repo, codex.root, "codex")
    assert second.returncode == 0, second.stderr
    assert BOTH_COMPLETE in second.stdout
    assert "scripts/analyze_phase2_odc.py" in second.stdout
    assert compute_state(repo) == BOTH_COMPLETE
    # printed, never run
    assert not repo.analysis_dir.exists()


def test_json_summary_reports_the_checks(repo, tmp_path):
    bundle = make_bundle(repo, "claude", tmp_path / "bundle_claude")
    result = run_import(repo, bundle.root, "claude", "--json")
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["cases"] == len(TOY_CASE_IDS)
    assert summary["workflow_state"] == CLAUDE_COMPLETE
    assert summary["results_sha256"] == sha256_file(repo.reviewer_results("claude"))
    assert len(summary["checks"]) >= 8


# ---------------------------------------------------------------------------
# refusals: nothing is written, and the bundle is never touched
# ---------------------------------------------------------------------------
def test_refuses_a_directory_that_is_not_a_bundle(repo, tmp_path):
    plain = tmp_path / "not_a_bundle"
    plain.mkdir()
    result = run_import(repo, plain, "claude")
    assert result.returncode == 1
    assert result.stderr.startswith("STOP:")
    assert "not a reviewer bundle" in result.stderr
    assert_repository_untouched(repo, "claude")


def test_refuses_the_other_reviewers_bundle(repo, tmp_path):
    bundle = make_bundle(repo, "claude", tmp_path / "bundle_claude")
    result = run_import(repo, bundle.root, "codex")
    assert result.returncode == 1
    assert "exported for reviewer 'claude'" in result.stderr
    assert_repository_untouched(repo, "codex")


def test_refuses_a_bundle_whose_freeze_manifest_differs(repo, tmp_path):
    bundle = make_bundle(repo, "claude", tmp_path / "bundle_claude")
    with bundle.freeze_manifest.open("a", encoding="utf-8") as handle:
        handle.write("\n")

    result = run_import(repo, bundle.root, "claude")
    assert result.returncode == 1
    assert "freeze mismatch" in result.stderr
    assert_repository_untouched(repo, "claude")


def test_refuses_an_unsealed_review(repo, tmp_path):
    bundle = make_bundle(repo, "claude", tmp_path / "bundle_claude", seal=False)
    assert not bundle.reviewer_complete("claude").is_file()

    result = run_import(repo, bundle.root, "claude")
    assert result.returncode == 1
    assert "has not sealed" in result.stderr
    assert_repository_untouched(repo, "claude")


def test_refuses_results_tampered_with_after_the_seal(repo, tmp_path):
    bundle = make_bundle(repo, "codex", tmp_path / "bundle_codex")
    with bundle.reviewer_results("codex").open("a", encoding="utf-8") as handle:
        handle.write("\n")

    result = run_import(repo, bundle.root, "codex")
    assert result.returncode == 1
    assert "void" in result.stderr
    assert_repository_untouched(repo, "codex")


def test_refuses_a_record_citing_evidence_the_packet_does_not_have(repo, tmp_path):
    records = [toy_record(case_id) for case_id in TOY_CASE_IDS]
    records[1] = toy_record(
        TOY_CASE_IDS[1], supporting_evidence_ids=["BUG_DIFF", "NOT_IN_THE_PACKET"]
    )
    bundle = make_bundle(repo, "claude", tmp_path / "bundle_claude", records=records)
    before = tree_hashes(bundle.root)

    result = run_import(repo, bundle.root, "claude")
    assert result.returncode == 1
    assert "not in the packet" in result.stderr
    assert_repository_untouched(repo, "claude")
    assert tree_hashes(bundle.root) == before


def test_refuses_a_duplicated_case(repo, tmp_path):
    records = [toy_record(TOY_CASE_IDS[0])] + [toy_record(case_id) for case_id in TOY_CASE_IDS]
    bundle = make_bundle(repo, "codex", tmp_path / "bundle_codex", records=records)

    result = run_import(repo, bundle.root, "codex")
    assert result.returncode == 1
    assert "duplicate review record" in result.stderr
    assert_repository_untouched(repo, "codex")


def test_refuses_a_missing_case(repo, tmp_path):
    records = [toy_record(case_id) for case_id in TOY_CASE_IDS[:-1]]
    bundle = make_bundle(repo, "claude", tmp_path / "bundle_claude", records=records)

    result = run_import(repo, bundle.root, "claude")
    assert result.returncode == 1
    assert f"no review record for {TOY_CASE_IDS[-1]}" in result.stderr
    assert_repository_untouched(repo, "claude")


def test_refuses_a_second_import_rather_than_overwriting(repo, tmp_path):
    bundle = make_bundle(repo, "claude", tmp_path / "bundle_claude")
    assert run_import(repo, bundle.root, "claude").returncode == 0
    imported = tree_hashes(repo.reviewer_dir("claude"))
    bundle_before = tree_hashes(bundle.root)

    again = run_import(repo, bundle.root, "claude")
    assert again.returncode == 1
    assert "already sealed in this repository" in again.stderr
    assert tree_hashes(repo.reviewer_dir("claude")) == imported
    assert tree_hashes(bundle.root) == bundle_before
    assert compute_state(repo) == CLAUDE_COMPLETE
