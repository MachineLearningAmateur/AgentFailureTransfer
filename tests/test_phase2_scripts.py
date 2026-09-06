"""End-to-end wiring of the Phase 2 command-line entry points.

Everything runs against a toy root in ``tmp_path``. The scripts are invoked as
subprocesses so that argument parsing, exit codes and the ``STOP:`` convention
are exercised the way a reviewer would meet them.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from agentfailuretransfer import paths as repo_paths
from agentfailuretransfer.phase2.paths import Phase2Paths
from agentfailuretransfer.phase2.review_records import dump_record, format_for_reviewer
from phase2_fixtures import TOY_CASE_IDS, build_toy_root, toy_record

SCRIPTS = repo_paths.REPO_ROOT / "scripts"


def run(script: str, *args: str, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )


@pytest.fixture
def toy(tmp_path):
    return Phase2Paths(build_toy_root(tmp_path / "toy"))


def write_records(paths: Phase2Paths, reviewer: str) -> None:
    fmt = format_for_reviewer(reviewer)
    for case_id in TOY_CASE_IDS:
        target = paths.reviewer_case_file(reviewer, case_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(dump_record(toy_record(case_id), fmt), encoding="utf-8")


def test_preflight_fails_before_the_freeze_and_passes_after(toy):
    before = run("check_phase2_ready.py", "--root", str(toy.root), "--reviewer", "claude")
    assert before.returncode == 1
    assert "FREEZE_MANIFEST" in before.stdout

    frozen = run("freeze_phase2.py", "--root", str(toy.root))
    assert frozen.returncode == 0, frozen.stderr
    assert "phase2-odc-pre-review-frozen" in frozen.stdout
    assert "does not create the git tag" in frozen.stdout

    after = run("check_phase2_ready.py", "--root", str(toy.root), "--reviewer", "claude")
    assert after.returncode == 0, after.stdout + after.stderr
    assert "ready for review" in after.stdout


def test_preflight_allows_setup_only_when_asked(toy):
    assert run("check_phase2_ready.py", "--root", str(toy.root)).returncode == 1
    assert run("check_phase2_ready.py", "--root", str(toy.root), "--allow-setup").returncode == 0


def test_freeze_check_detects_drift(toy):
    assert run("freeze_phase2.py", "--root", str(toy.root)).returncode == 0
    assert run("freeze_phase2.py", "--root", str(toy.root), "--check").returncode == 0
    with toy.taxonomy_yaml.open("a", encoding="utf-8") as handle:
        handle.write("\n# drift\n")
    drifted = run("freeze_phase2.py", "--root", str(toy.root), "--check")
    assert drifted.returncode == 1
    assert drifted.stderr.startswith("STOP:")


def test_refreezing_over_drift_is_refused(toy):
    run("freeze_phase2.py", "--root", str(toy.root))
    with toy.taxonomy_yaml.open("a", encoding="utf-8") as handle:
        handle.write("\n# drift\n")
    again = run("freeze_phase2.py", "--root", str(toy.root))
    assert again.returncode == 1
    assert "would silently redefine" in again.stderr


@pytest.mark.parametrize("reviewer", ["claude", "codex"])
def test_validate_then_finalize_then_lock(toy, reviewer):
    run("freeze_phase2.py", "--root", str(toy.root))
    write_records(toy, reviewer)

    one = run(
        "validate_phase2_review.py", "--root", str(toy.root),
        "--reviewer", reviewer, "--case", "TOY_001",
    )
    assert one.returncode == 0, one.stderr
    assert json.loads(one.stdout)["case_id_universe"] == "NON_STUDY"
    assert "REHEARSAL CORPUS" in one.stderr

    every = run(
        "validate_phase2_review.py", "--root", str(toy.root), "--reviewer", reviewer, "--all"
    )
    assert every.returncode == 0
    assert json.loads(every.stdout)["validated_cases"] == len(TOY_CASE_IDS)

    sealed = run(
        "validate_phase2_review.py", "--root", str(toy.root), "--reviewer", reviewer, "--finalize"
    )
    assert sealed.returncode == 0, sealed.stderr
    summary = json.loads(sealed.stdout)
    assert summary["finalized"] is True and summary["locked"] is True
    assert summary["cases"] == len(TOY_CASE_IDS)
    assert toy.reviewer_complete(reviewer).is_file()

    again = run(
        "validate_phase2_review.py", "--root", str(toy.root), "--reviewer", reviewer, "--finalize"
    )
    assert again.returncode == 1
    assert "finalization lock" in again.stderr


def test_finalize_refuses_an_incomplete_review(toy):
    run("freeze_phase2.py", "--root", str(toy.root))
    write_records(toy, "claude")
    toy.reviewer_case_file("claude", "TOY_003").unlink()
    result = run(
        "validate_phase2_review.py", "--root", str(toy.root), "--reviewer", "claude", "--finalize"
    )
    assert result.returncode == 1
    assert "case(s) missing" in result.stderr
    assert not toy.reviewer_complete("claude").is_file()


def test_finalize_refuses_an_unexpected_case(toy):
    run("freeze_phase2.py", "--root", str(toy.root))
    write_records(toy, "codex")
    extra = toy.reviewer_case_file("codex", "TOY_009")
    extra.write_text(dump_record(toy_record("TOY_009"), "json"), encoding="utf-8")
    result = run(
        "validate_phase2_review.py", "--root", str(toy.root), "--reviewer", "codex", "--finalize"
    )
    assert result.returncode == 1
    assert not toy.reviewer_complete("codex").is_file()


def test_validate_reports_an_invalid_record_without_writing_a_seal(toy):
    run("freeze_phase2.py", "--root", str(toy.root))
    write_records(toy, "claude")
    bad = toy.reviewer_case_file("claude", "TOY_002")
    bad.write_text(
        dump_record(toy_record("TOY_002", taxonomy_fit="OUT_OF_SCOPE"), "yaml"), encoding="utf-8"
    )
    result = run(
        "validate_phase2_review.py", "--root", str(toy.root), "--reviewer", "claude", "--all"
    )
    assert result.returncode == 1
    assert "UNCLASSIFIABLE" in result.stderr
    assert not toy.reviewer_complete("claude").is_file()


def test_bundle_export_refuses_before_the_freeze(toy, tmp_path):
    result = run(
        "make_phase2_review_bundle.py", "--root", str(toy.root),
        "--reviewer", "claude", "--out", str(tmp_path / "bundle"), "--allow-dirty",
    )
    assert result.returncode == 1
    assert "FROZEN_PRE_REVIEW is required" in result.stderr
    assert not (tmp_path / "bundle").exists()


def test_bundle_exported_with_allow_setup_is_marked_dry_run(toy, tmp_path):
    out = tmp_path / "bundle"
    result = run(
        "make_phase2_review_bundle.py", "--root", str(toy.root),
        "--reviewer", "claude", "--out", str(out), "--allow-setup", "--allow-dirty",
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["dry_run"] is True
    assert json.loads((out / "BUNDLE_MANIFEST.json").read_text(encoding="utf-8"))["dry_run"] is True


def test_a_bundle_is_a_complete_standalone_review_checkout(toy, tmp_path):
    """Export, then run the whole review inside the bundle with no repository."""
    run("freeze_phase2.py", "--root", str(toy.root))
    out = tmp_path / "bundle_claude"
    exported = run(
        "make_phase2_review_bundle.py", "--root", str(toy.root),
        "--reviewer", "claude", "--out", str(out), "--allow-dirty",
    )
    assert exported.returncode == 0, exported.stderr

    bundle = Phase2Paths(out)
    assert bundle.is_bundle

    preflight = subprocess.run(
        [sys.executable, "scripts/check_phase2_ready.py", "--reviewer", "claude"],
        capture_output=True, text=True, cwd=str(out),
    )
    assert preflight.returncode == 0, preflight.stdout + preflight.stderr
    assert "the other reviewer (codex) is absent" in preflight.stdout

    write_records(bundle, "claude")
    sealed = subprocess.run(
        [sys.executable, "scripts/validate_phase2_review.py", "--reviewer", "claude", "--finalize"],
        capture_output=True, text=True, cwd=str(out),
    )
    assert sealed.returncode == 0, sealed.stderr
    assert bundle.reviewer_complete("claude").is_file()
    marker = bundle.reviewer_complete("claude").read_text(encoding="utf-8")
    assert "case_id_universe NON_STUDY" in marker
