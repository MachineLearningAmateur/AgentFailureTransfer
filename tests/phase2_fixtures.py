"""A toy Phase 2 root, built in a temporary directory.

Everything the Phase 2 tests exercise is built here from scratch: three cases
with ids ``TOY_001``..``TOY_003``, their own snapshot manifest in the same shape
as the frozen one, and a rubric and schema copied from the repository.

The case ids are deliberately **not** ``SWESMITH_001..100``. Handoff section 20
requires the workflow to be rehearsed on synthetic miniature examples, so that
no study case is ever used to debug tooling or to tune the rubric. No test in
this suite writes a review record against study evidence.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from agentfailuretransfer import paths as repo_paths
from agentfailuretransfer.phase2.packets import digest_from_file_hashes, packet_file_hashes

TOY_CASE_IDS = ("TOY_001", "TOY_002", "TOY_003")

TOY_PROMPT = """\
# Phase 2 ODC review instructions ({reviewer}) - toy fixture

Classify each case using the ODC Defect Type dimension only: what kind of
software correction would repair the observed defect? BUG_DIFF introduces the
defect; REFERENCE_REPAIR reverses it. Save one file per case under
reviews/{reviewer}/cases/, validate as you go, and finalize at the end.
"""

TOY_PROTOCOL = "# Toy protocol\n\nA stand-in for the frozen protocol prose.\n"


def _write(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalised = text.replace("\r\n", "\n")
    path.write_text(normalised, encoding="utf-8", newline="\n")
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def _build_packet(packets_dir: Path, case_id: str, index: int) -> dict:
    directory = packets_dir / case_id
    files: dict[str, str] = {}

    bug = (
        f"diff --git a/toybox/widget_{index}.py b/toybox/widget_{index}.py\n"
        "@@ -3,7 +3,7 @@ def total(values):\n"
        "-    return sum(values)\n"
        "+    return sum(values[:-1])\n"
    )
    files["bug_diff.diff"] = _write(directory / "bug_diff.diff", bug)
    files["reference_repair.diff"] = _write(
        directory / "reference_repair.diff",
        bug.replace("-    return sum(values)", "@@KEEP@@")
        .replace("+    return sum(values[:-1])", "-    return sum(values[:-1])")
        .replace("@@KEEP@@", "+    return sum(values)"),
    )
    files[f"context/01_widget_{index}.py"] = _write(
        directory / f"context/01_widget_{index}.py",
        "def total(values):\n    return sum(values[:-1])\n",
    )
    files["specification.md"] = _write(
        directory / "specification.md",
        f"# Toy specification {index}\n\n`total` should add every value it is given.\n",
    )
    files["test_evidence.md"] = _write(
        directory / "test_evidence.md",
        "# Failing test evidence\n\nFailing tests (1):\n\n"
        f"  tests/test_widget.py::test_total_{index}\n",
    )

    packet = {
        "case_id": case_id,
        "packet_version": 2,
        "repository": {"name": "example/toybox", "language": "Python"},
        "bug_diff": {"evidence_id": "BUG_DIFF", "path": "bug_diff.diff", "sha256": files["bug_diff.diff"]},
        "reference_repair": {
            "evidence_id": "REFERENCE_REPAIR",
            "path": "reference_repair.diff",
            "sha256": files["reference_repair.diff"],
        },
        "specification": {
            "evidence_id": "SPECIFICATION",
            "path": "specification.md",
            "sha256": files["specification.md"],
        },
        "code_context": [
            {
                "evidence_id": "CODE_CONTEXT_01",
                "path": f"context/01_widget_{index}.py",
                "repo_path": f"toybox/widget_{index}.py",
                "sha256": files[f"context/01_widget_{index}.py"],
            }
        ],
        "failing_tests": {
            "evidence_id_prefix": "TEST_FAILURE",
            "path": "test_evidence.md",
            "sha256": files["test_evidence.md"],
            "tests": [
                {
                    "evidence_id": "TEST_FAILURE_01",
                    "test_name": f"tests/test_widget.py::test_total_{index}",
                }
            ],
        },
        "evidence_ids": [
            "BUG_DIFF",
            "CODE_CONTEXT_01",
            "REFERENCE_REPAIR",
            "SPECIFICATION",
            "TEST_FAILURE_01",
        ],
        "reviewer_question": (
            "Based only on the frozen evidence in this packet, what kind of "
            "software defect does this buggy repository state represent?"
        ),
    }
    _write(
        directory / "packet.json",
        json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )
    hashes = packet_file_hashes(directory)
    return {
        "case_id": case_id,
        "digest": digest_from_file_hashes(hashes),
        "files": hashes,
        "path": f"data/review_packets/{case_id}",
    }


def build_toy_root(root: Path, *, prompt_extra: dict[str, str] | None = None) -> Path:
    """Create a complete, freezable Phase 2 root at ``root``."""
    root = Path(root)
    (root / "taxonomy").mkdir(parents=True, exist_ok=True)
    for name in ("odc_defect_type_v1.yaml", "odc_defect_type_v1.md", "SOURCE_PROVENANCE.md"):
        source = repo_paths.PHASE2_TAXONOMY_DIR / name
        if source.is_file():
            shutil.copyfile(source, root / "taxonomy" / name)
        else:  # the prose is written by another author; a stub keeps tests honest
            _write(root / "taxonomy" / name, f"# {name} (test stub)\n")
    (root / "schemas").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(repo_paths.PHASE2_SCHEMA, root / "schemas" / "odc_review_result.schema.json")

    _write(root / "protocol" / "toy_protocol.md", TOY_PROTOCOL)
    for reviewer in ("claude", "codex"):
        text = TOY_PROMPT.format(reviewer=reviewer)
        if prompt_extra and reviewer in prompt_extra:
            text += prompt_extra[reviewer]
        _write(root / "protocol" / f"reviewer_prompt_{reviewer}.md", text)

    packets = root / "data" / "review_packets"
    entries = [_build_packet(packets, case_id, index) for index, case_id in enumerate(TOY_CASE_IDS, 1)]
    manifest_sha = _write(
        root / "data" / "review_manifest.csv",
        "case_id,repository,language\n"
        + "".join(f"{case_id},example/toybox,Python\n" for case_id in TOY_CASE_IDS),
    )
    _write(
        root / "data" / "review_snapshot_manifest.json",
        json.dumps(
            {
                "frozen_at_utc": "2026-01-01T00:00:00Z",
                "note": "TOY REHEARSAL CORPUS. Not study evidence.",
                "packet_count": len(entries),
                "packets": entries,
                "review_manifest_sha256": manifest_sha,
                "corpus_kind": "REHEARSAL",
            },
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
    )
    for reviewer in ("claude", "codex"):
        (root / "reviews" / reviewer / "cases").mkdir(parents=True, exist_ok=True)
    return root


def toy_record(case_id: str, **overrides) -> dict:
    """A valid toy record, before any override."""
    record = {
        "case_id": case_id,
        "odc_defect_type": "ALGORITHM",
        "taxonomy_fit": "DIRECT",
        "pattern_confidence": "HIGH",
        "supporting_evidence_ids": ["BUG_DIFF", "REFERENCE_REPAIR"],
        "reasoning_summary": (
            "The diff drops the last element from the sum; the repair restores it, "
            "a local implementation correction."
        ),
    }
    record.update(overrides)
    return record
