"""Bundle isolation: what a reviewer receives, and what must never reach them.

The leakage tests build a toy repository layout that deliberately contains the
things a bundle must exclude -- a hidden crosswalk, a Phase 1 results file, the
other reviewer's directory, an analysis output -- export from it, and assert
that none of them survive. A separate test plants a leak that the exporter
*would* copy and asserts the export is refused and deleted.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from agentfailuretransfer import paths as repo_paths
from agentfailuretransfer.phase2 import Phase2Error
from agentfailuretransfer.phase2 import bundle as bundle_module
from agentfailuretransfer.phase2.bundle import (
    BUNDLE_EXCLUDED_LIBRARY_MODULES,
    BUNDLE_LIBRARY_MODULES,
    audit,
    export,
    scan_contents,
    scan_paths,
)
from agentfailuretransfer.phase2.freeze import build_manifest, write_manifest
from agentfailuretransfer.phase2.paths import Phase2Paths
from phase2_fixtures import build_toy_root

PLANTED = {
    "hidden/sample_metadata.csv": "case_id,generation_method,method_family\nTOY_001,x,y\n",
    "reviews/codex/review_results.jsonl": '{"case_id": "TOY_001", "failure_pattern": "FAKE"}\n',
    "analysis/odc_agreement.json": '{"agreement": 0.5}\n',
    "sources/swesmith_source.json": '{"commit_sha": "deadbeef"}\n',
    "data/derived/phase1_headline.json": '{"kappa": 0.0}\n',
}


@pytest.fixture
def contaminated_root(tmp_path):
    """A Phase 2 root that contains everything a bundle must not carry."""
    root = build_toy_root(tmp_path / "toy")
    for relative, text in PLANTED.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    paths = Phase2Paths(root)
    write_manifest(paths, build_manifest(paths))
    return paths


def do_export(paths, reviewer, out, **kwargs):
    return export(
        paths,
        reviewer,
        out,
        repo_root=repo_paths.REPO_ROOT,
        source_commit="0" * 40,
        **kwargs,
    )


def test_bundle_excludes_every_planted_leak(contaminated_root, tmp_path):
    out = tmp_path / "bundle_claude"
    manifest = do_export(contaminated_root, "claude", out)
    present = {path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file()}
    for relative in PLANTED:
        assert relative not in present
    assert not (out / "hidden").exists()
    assert not (out / "analysis").exists()
    assert not (out / "sources").exists()
    assert manifest["file_count"] == len(present) - 1  # the manifest itself


def test_phase1_labels_are_not_in_the_bundle(contaminated_root, tmp_path):
    out = tmp_path / "bundle_claude"
    do_export(contaminated_root, "claude", out)
    for path in out.rglob("*"):
        if path.is_file():
            assert path.name != "review_results.jsonl"
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            assert "FAKE" not in text


def test_the_other_reviewer_is_absent(contaminated_root, tmp_path):
    for reviewer, excluded in (("claude", "codex"), ("codex", "claude")):
        out = tmp_path / f"bundle_{reviewer}"
        do_export(contaminated_root, reviewer, out)
        assert (out / "reviews" / reviewer / "cases").is_dir()
        assert not (out / "reviews" / excluded).exists()
        assert not (out / "protocol" / f"reviewer_prompt_{excluded}.md").exists()
        assert audit(out, reviewer) == []


def test_the_bundle_ships_only_the_review_path_library(contaminated_root, tmp_path):
    out = tmp_path / "bundle_claude"
    do_export(contaminated_root, "claude", out)
    shipped = {
        path.relative_to(out / "src").as_posix()
        for path in (out / "src").rglob("*.py")
    }
    assert shipped == set(BUNDLE_LIBRARY_MODULES)
    for module in BUNDLE_EXCLUDED_LIBRARY_MODULES:
        assert module not in shipped


def test_the_bundled_library_needs_no_numpy_or_scipy(contaminated_root, tmp_path):
    """A reviewer needs the standard library and pyyaml. Nothing else."""
    out = tmp_path / "bundle_claude"
    do_export(contaminated_root, "claude", out)
    script = (
        "import sys; sys.path.insert(0, r'%s');"
        "import agentfailuretransfer.phase2.state,"
        " agentfailuretransfer.phase2.review_records,"
        " agentfailuretransfer.phase2.packets,"
        " agentfailuretransfer.phase2.freeze;"
        "assert 'numpy' not in sys.modules, 'numpy was imported';"
        "assert 'scipy' not in sys.modules, 'scipy was imported';"
        "print('ok')" % (out / "src")
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, cwd=out
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_bundle_packets_are_byte_identical_and_rehashed(contaminated_root, tmp_path):
    out = tmp_path / "bundle_claude"
    do_export(contaminated_root, "claude", out)
    source_packets = contaminated_root.review_packets
    for path in source_packets.rglob("*"):
        if path.is_file():
            mirrored = out / "data" / "review_packets" / path.relative_to(source_packets)
            assert mirrored.read_bytes() == path.read_bytes()
    assert bundle_module.verify_bundle_packets(out) == []


def test_a_planted_content_leak_refuses_the_export_and_deletes_it(tmp_path):
    root = build_toy_root(
        tmp_path / "toy",
        prompt_extra={"claude": "\nDo not reveal the generation" + "_method column.\n"},
    )
    paths = Phase2Paths(root)
    write_manifest(paths, build_manifest(paths))
    out = tmp_path / "bundle_claude"
    with pytest.raises(Phase2Error, match="would have leaked"):
        do_export(paths, "claude", out)
    assert not out.exists()


def test_a_tampered_packet_refuses_the_export(contaminated_root, tmp_path):
    packet = contaminated_root.packet_dir("TOY_001") / "specification.md"
    packet.write_text("tampered\n", encoding="utf-8")
    out = tmp_path / "bundle_claude"
    with pytest.raises(Phase2Error, match="would have leaked"):
        do_export(contaminated_root, "claude", out)
    assert not out.exists()


def test_export_refuses_to_write_inside_the_repository(contaminated_root):
    with pytest.raises(Phase2Error, match="refusing to export inside"):
        do_export(contaminated_root, "claude", repo_paths.PHASE2_BUNDLES_DIR / "x")


def test_export_refuses_an_existing_output_directory(contaminated_root, tmp_path):
    out = tmp_path / "bundle_claude"
    out.mkdir()
    with pytest.raises(Phase2Error, match="already exists"):
        do_export(contaminated_root, "claude", out)


def test_export_refuses_without_the_reviewer_prompt(contaminated_root, tmp_path):
    contaminated_root.reviewer_prompt("claude").unlink()
    with pytest.raises(Phase2Error, match="reviewer prompt for claude is missing"):
        do_export(contaminated_root, "claude", tmp_path / "bundle_claude")


def test_dry_run_is_stamped_in_the_manifest(contaminated_root, tmp_path):
    out = tmp_path / "bundle_claude"
    manifest = do_export(contaminated_root, "claude", out, dry_run=True)
    assert manifest["dry_run"] is True
    on_disk = json.loads((out / "BUNDLE_MANIFEST.json").read_text(encoding="utf-8"))
    assert on_disk["dry_run"] is True
    assert "must not be handed to a reviewer" in on_disk["dry_run_note"]


def test_bundle_manifest_hashes_every_exported_file(contaminated_root, tmp_path):
    from agentfailuretransfer.hashing import sha256_file

    out = tmp_path / "bundle_claude"
    manifest = do_export(contaminated_root, "claude", out)
    assert manifest["source_commit"] == "0" * 40
    assert manifest["freeze_manifest_sha256"] == sha256_file(contaminated_root.freeze_manifest)
    for entry in manifest["files"]:
        target = out / entry["path"]
        assert target.is_file()
        assert sha256_file(target) == entry["sha256"]
        assert target.stat().st_size == entry["bytes"]


# ---------------------------------------------------------------------------
# the scanners, exercised directly on crafted trees
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "relative",
    [
        "data/hidden/sample_metadata.csv",
        "analysis/odc_agreement.json",
        "sources/aidev_source.json",
        "docs/phase1_notes.md",
        "reviews/claude/COMPLETE",
        "taxonomy/pattern_families.yaml",
        "taxonomy/frozen_failure_taxonomy_v1.md",
        "data/generation_notes.txt",
        "analysis/robustness.json",
        "reports/headline_results.md",
    ],
)
def test_scan_paths_catches_each_forbidden_path(tmp_path, relative):
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x\n", encoding="utf-8")
    assert scan_paths(tmp_path, "claude")


def test_scan_paths_catches_the_other_reviewers_directory(tmp_path):
    (tmp_path / "reviews" / "codex" / "cases").mkdir(parents=True)
    (tmp_path / "reviews" / "codex" / "cases" / "TOY_001.json").write_text("{}", encoding="utf-8")
    problems = scan_paths(tmp_path, "claude")
    assert any("other reviewer's directory" in problem for problem in problems)
    assert scan_paths(tmp_path, "codex") == []


@pytest.mark.parametrize(
    "token",
    ["generation_method", "method_family", "func_pm_", "failure_pattern", "aidev_failure_taxonomy"],
)
def test_scan_contents_is_fatal_for_metadata_shaped_tokens(tmp_path, token):
    (tmp_path / "notes.md").write_text(f"see the {token} column\n", encoding="utf-8")
    assert scan_contents(tmp_path).fatal


def test_ambiguous_tokens_are_fatal_outside_the_evidence_but_noted_inside(tmp_path):
    outside = tmp_path / "src" / "helper.py"
    outside.parent.mkdir(parents=True)
    outside.write_text("instance_id = 1\n", encoding="utf-8")
    assert scan_contents(tmp_path).fatal
    outside.unlink()

    inside = tmp_path / "data" / "review_packets" / "TOY_001" / "context" / "01_x.py"
    inside.parent.mkdir(parents=True)
    inside.write_text("def get(instance_id):\n    return instance_id\n", encoding="utf-8")
    result = scan_contents(tmp_path)
    assert result.fatal == []
    assert result.notes and result.notes[0]["token"] == "instance_id"


def test_an_ambiguous_token_inside_packet_json_is_still_fatal(tmp_path):
    target = tmp_path / "data" / "review_packets" / "TOY_001" / "packet.json"
    target.parent.mkdir(parents=True)
    target.write_text('{"instance_id": "x"}\n', encoding="utf-8")
    assert scan_contents(tmp_path).fatal


def test_frozen_prose_may_name_what_it_withholds(tmp_path):
    """The blinding instruction has to be able to say 'no trajectory'."""
    (tmp_path / "protocol").mkdir()
    (tmp_path / "README.md").write_text(
        "You will not see the source model, the trajectory, or the attempt count.\n",
        encoding="utf-8",
    )
    (tmp_path / "protocol" / "reviewer_prompt_claude.md").write_text(
        "No trajectory and no instance mapping are provided.\n", encoding="utf-8"
    )
    result = scan_contents(tmp_path)
    assert result.fatal == []
    assert {note["path"] for note in result.notes} == {
        "README.md",
        "protocol/reviewer_prompt_claude.md",
    }
    assert all("hash-pinned" in note["why_not_fatal"] for note in result.notes)


def test_metadata_shaped_tokens_stay_fatal_even_in_the_frozen_prose(tmp_path):
    (tmp_path / "README.md").write_text(
        "This case's generation" + "_method was procedural.\n", encoding="utf-8"
    )
    assert scan_contents(tmp_path).fatal
