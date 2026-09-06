#!/usr/bin/env python3
"""Import the frozen artifacts of the two source studies into this repository.

    python scripts/import_sources.py [--aidev-path P] [--swesmith-path P]

The two source repositories are READ-ONLY scientific provenance. This script
never writes, checks out, or commits anything in them; it only runs
``git rev-parse`` / ``git status --porcelain`` and reads files.

It stops with a non-zero exit if:

* a source path is not a git repository;
* a source working tree is dirty (the frozen state would be ambiguous);
* a source HEAD does not equal the pinned commit (unless ``--allow-unpinned``);
* an expected frozen artifact is missing;
* a review COMPLETE marker is missing;
* a known-good SHA-256 does not match;
* the AIDev and SWE-smith taxonomy / family-mapping files are not byte-identical.

Outputs: data/aidev/**, data/swesmith/**, sources/aidev_source.json,
sources/swesmith_source.json.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from agentfailuretransfer.hashing import sha256_file  # noqa: E402

DEFAULT_AIDEV_PATH = Path("/home/disgustingtest/research/AIBugAnalysis")
DEFAULT_SWESMITH_PATH = Path("/home/disgustingtest/research/SWE-Smith-Bug-Analysis")

# Pinned source revisions. A moving `main` must never silently change the
# import; these are the commits that carry the sealed reviews we analyse.
PINNED_AIDEV_COMMIT = "85e4bf9caf0a63436a1a305592d82294536ccd8e"
PINNED_SWESMITH_COMMIT = "0345139bf449f1fe9401f2a708d0d3b5961d14b2"

# Known-good hashes stated in the study brief and in the source provenance
# records. Verified BEFORE anything is copied.
KNOWN_FAMILY_MAPPING_SHA256 = (
    "1ce7232047437f87e7116d84b369e4f820e854481cbc744faf3b1d4c1af60985"
)
KNOWN_TAXONOMY_SHA256 = (
    "ecf76f0d752afd2632d4a2825b648a36cce4c16926782aec18fd4e2637fe4cc7"
)
KNOWN_SNAPSHOT_SHA256 = (
    "981694c07ffcc9ee9bcf00527d71a0c94b15884ebfc7d8aa537363b3f646a6de"
)
KNOWN_REVIEW_MANIFEST_SHA256 = (
    "64e607800de2a08e4321b371d616841bbd4fbe6deaddb1321dfd355333caebfa"
)

TAXONOMY_VERSION = "aidev_failure_taxonomy_v1"


@dataclass(frozen=True)
class ImportItem:
    source_path: str
    imported_path: str
    note: str


# --------------------------------------------------------------------------
# Approved import lists. Nothing outside these lists is ever copied.
# Deliberately excluded: evidence/review packets, reviews/*/cases/** (verified
# byte-duplicates of the JSONL), trajectories, the 1 MB population CSV, the
# 7.9 MB PDF, archive/, runs/, and every source script (their output strings
# carry an obsolete sampling description; they are cited by hash instead).
# --------------------------------------------------------------------------

AIDEV_ITEMS: tuple[ImportItem, ...] = (
    ImportItem(
        "reviews/codex/review_results.jsonl",
        "data/aidev/reviews/codex/review_results.jsonl",
        "sealed Codex fine-grained labels (100 cases)",
    ),
    ImportItem(
        "reviews/codex/COMPLETE",
        "data/aidev/reviews/codex/COMPLETE",
        "Codex seal marker (rubric + manifest + evidence snapshot hashes)",
    ),
    ImportItem(
        "reviews/codex/review_metadata.json",
        "data/aidev/reviews/codex/review_metadata.json",
        "Codex reviewer model identity and protocol version",
    ),
    ImportItem(
        "reviews/claude/review_results.jsonl",
        "data/aidev/reviews/claude/review_results.jsonl",
        "sealed Claude fine-grained labels (100 cases)",
    ),
    ImportItem(
        "reviews/claude/COMPLETE",
        "data/aidev/reviews/claude/COMPLETE",
        "Claude seal marker",
    ),
    ImportItem(
        "reviews/claude/review_metadata.json",
        "data/aidev/reviews/claude/review_metadata.json",
        "Claude reviewer model identity and protocol version",
    ),
    ImportItem(
        "analysis/taxonomy/frozen_failure_taxonomy_v1.md",
        "data/aidev/taxonomy/frozen_failure_taxonomy_v1.md",
        "frozen fine-grained taxonomy of record",
    ),
    ImportItem(
        "analysis/taxonomy/proposed_pattern_families.yaml",
        "data/aidev/taxonomy/proposed_pattern_families.yaml",
        "frozen fine -> broad-family mapping",
    ),
    ImportItem(
        "analysis/taxonomy/family_mapping_analysis.md",
        "data/aidev/taxonomy/family_mapping_analysis.md",
        "how the family mapping was selected from AIDev disagreement data",
    ),
    ImportItem(
        "analysis/dual_review/agreement_metrics.json",
        "data/aidev/dual_review/agreement_metrics.json",
        "published AIDev agreement metrics (diff target for recomputation)",
    ),
    ImportItem(
        "analysis/dual_review/calibration_report.md",
        "data/aidev/dual_review/calibration_report.md",
        "prose of record for 31/49 and 36/49, incl. the in-sample caveat",
    ),
    ImportItem(
        "analysis/dual_review/pattern_confusion.csv",
        "data/aidev/dual_review/pattern_confusion.csv",
        "fine confusion matrix; cells sum to the 49-case population",
    ),
    ImportItem(
        "analysis/dual_review/pattern_family_confusion.csv",
        "data/aidev/dual_review/pattern_family_confusion.csv",
        "family confusion matrix; cells sum to the 49-case population",
    ),
    ImportItem(
        "analysis/dual_review/pattern_disagreements.csv",
        "data/aidev/dual_review/pattern_disagreements.csv",
        "the 18 fine-label disagreements with both reviewers' reasoning",
    ),
    ImportItem(
        "analysis/dual_review/pattern_family_disagreements.csv",
        "data/aidev/dual_review/pattern_family_disagreements.csv",
        "the 13 disagreements the family mapping does not absorb",
    ),
    ImportItem(
        "data/derived/DERIVATION_METADATA.json",
        "data/aidev/derived/DERIVATION_METADATA.json",
        "hash bundle tying every sealed input to the source study's derived data",
    ),
    ImportItem(
        "data/derived/aidev_rq1_primary_cases.parquet",
        "data/aidev/derived/aidev_rq1_primary_cases.parquet",
        "OPAQUE hashed artifact: pins the 35-case strict corpus identity. "
        "Never parsed by this repository (no parquet reader is required).",
    ),
    ImportItem(
        "docs/aidev_review_rubric.md",
        "data/aidev/docs/aidev_review_rubric.md",
        "the rubric both AIDev reviews were sealed against",
    ),
    ImportItem(
        "schemas/review_result.schema.json",
        "data/aidev/schemas/review_result.schema.json",
        "field/enum contract for the AIDev reviewer records",
    ),
    ImportItem(
        "data/pr_manifest.csv",
        "data/aidev/data/pr_manifest.csv",
        "case_id -> repo/pr_number/pr_url/source_agent; the source analysis "
        "joins onto it one-to-one",
    ),
)

SWESMITH_ITEMS: tuple[ImportItem, ...] = (
    ImportItem(
        "reviews/codex/review_results.jsonl",
        "data/swesmith/reviews/codex/review_results.jsonl",
        "sealed Codex fine-grained labels (100 cases)",
    ),
    ImportItem(
        "reviews/codex/COMPLETE",
        "data/swesmith/reviews/codex/COMPLETE",
        "Codex seal marker (snapshot manifest hash + taxonomy fingerprint)",
    ),
    ImportItem(
        "reviews/codex/review_metadata.json",
        "data/swesmith/reviews/codex/review_metadata.json",
        "binds the Codex JSONL by results_sha256",
    ),
    ImportItem(
        "reviews/claude/review_results.jsonl",
        "data/swesmith/reviews/claude/review_results.jsonl",
        "sealed Claude fine-grained labels (100 cases)",
    ),
    ImportItem(
        "reviews/claude/COMPLETE",
        "data/swesmith/reviews/claude/COMPLETE",
        "Claude seal marker",
    ),
    ImportItem(
        "reviews/claude/review_metadata.json",
        "data/swesmith/reviews/claude/review_metadata.json",
        "binds the Claude JSONL by results_sha256",
    ),
    ImportItem(
        "taxonomy/frozen_failure_taxonomy_v1.md",
        "data/swesmith/taxonomy/frozen_failure_taxonomy_v1.md",
        "byte-identical copy of the AIDev frozen taxonomy",
    ),
    ImportItem(
        "taxonomy/pattern_families.yaml",
        "data/swesmith/taxonomy/pattern_families.yaml",
        "byte-identical copy of the AIDev family mapping (renamed on import)",
    ),
    ImportItem(
        "taxonomy/TAXONOMY_PROVENANCE.json",
        "data/swesmith/taxonomy/TAXONOMY_PROVENANCE.json",
        "records the byte-for-byte taxonomy handoff from AIDev",
    ),
    ImportItem(
        "data/hidden/sample_metadata.csv",
        "data/swesmith/hidden/sample_metadata.csv",
        "hidden crosswalk: case_id -> generation_method / method_family. "
        "Withheld from reviewers; joined only after labels are loaded.",
    ),
    ImportItem(
        "data/hidden/selection_record.json",
        "data/swesmith/hidden/selection_record.json",
        "sample selection record (population 4207, 100 selected, 52 repos)",
    ),
    ImportItem(
        "data/review_manifest.csv",
        "data/swesmith/review_manifest.csv",
        "the neutral manifest both COMPLETE markers commit to",
    ),
    ImportItem(
        "data/review_snapshot_manifest.json",
        "data/swesmith/review_snapshot_manifest.json",
        "frozen packet snapshot; completes the seal chain end to end",
    ),
    ImportItem(
        "configs/sampling.yaml",
        "data/swesmith/configs/sampling.yaml",
        "seed 20260830, target_n 100, max_per_repo 5, forbidden inputs",
    ),
    ImportItem(
        "data/population/POPULATION_PROVENANCE.json",
        "data/swesmith/population/POPULATION_PROVENANCE.json",
        "pinned dataset revisions and the 4207-instance population accounting",
    ),
    ImportItem(
        "analysis/sample_balance.md",
        "data/swesmith/analysis/sample_balance.md",
        "human-readable sample balance table",
    ),
    ImportItem(
        "analysis/aidev_strict_language_profile.json",
        "data/swesmith/analysis/aidev_strict_language_profile.json",
        "language attribution for the 35 AIDev strict cases (cross-repo artifact)",
    ),
    ImportItem(
        "schemas/review_result.schema.json",
        "data/swesmith/schemas/review_result.schema.json",
        "8-field contract; documents why UNASSIGNED is absent here",
    ),
)

# Reference implementations. Cited by hash, never copied.
AIDEV_REFERENCE_SCRIPTS = (
    ("scripts/analyze_dual_reviews.py", "canonical 49-case inclusion rule and fine kappa"),
    ("scripts/apply_pattern_families.py", "canonical family mapping application and family kappa"),
    ("scripts/build_rq1_aidev_dataset.py", "canonical 35-case strict corpus rule"),
)
SWESMITH_REFERENCE_SCRIPTS = (
    ("scripts/apply_frozen_families.py", "pooled fine/family agreement and the hand-rolled kappa"),
    ("scripts/compare_reviews.py", "per-generation-family breakdown"),
    ("ssr/swesmith.py", "authoritative generation_method -> method_family mapping"),
)


class ImportError_(SystemExit):
    """Raised (as a non-zero exit) when the import cannot proceed safely."""


def fail(message: str) -> None:
    raise ImportError_(f"STOP: {message}")


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        fail(f"git {' '.join(args)} failed in {repo}: {result.stderr.strip()}")
    return result.stdout.strip()


def inspect_source(path: Path, pinned: str, allow_unpinned: bool, label: str) -> dict:
    if not path.is_dir():
        fail(f"{label} source path does not exist: {path}")
    if not (path / ".git").exists():
        fail(f"{label} source path is not a git repository: {path}")

    head = git(path, "rev-parse", "HEAD")
    branch = git(path, "rev-parse", "--abbrev-ref", "HEAD")
    porcelain = git(path, "status", "--porcelain")
    if porcelain:
        fail(
            f"{label} source repository {path} has uncommitted changes; the frozen "
            f"state is ambiguous. Refusing to import.\n{porcelain}"
        )
    if head != pinned:
        if not allow_unpinned:
            fail(
                f"{label} HEAD {head} != pinned commit {pinned}. The import is "
                "pinned so a moving `main` cannot silently change it. Re-run "
                "with --allow-unpinned only if you intend to re-pin."
            )
        print(
            f"!!! WARNING: {label} HEAD {head} does NOT match the pinned commit "
            f"{pinned}. --allow-unpinned was given, so the import proceeds with "
            "an UNPINNED source revision. The resulting manifest is not the "
            "frozen study identity.",
            file=sys.stderr,
        )
    return {
        "head": head,
        "branch": branch,
        "clean": True,
        "pinned_commit": pinned,
        "matches_pin": head == pinned,
    }


def check_exists(root: Path, items: tuple[ImportItem, ...], label: str) -> None:
    missing = [item.source_path for item in items if not (root / item.source_path).is_file()]
    if missing:
        fail(f"{label}: expected frozen artifacts are missing:\n  " + "\n  ".join(missing))


def check_complete_markers(root: Path, label: str) -> dict:
    completion: dict[str, dict] = {}
    for reviewer in ("codex", "claude"):
        marker = root / "reviews" / reviewer / "COMPLETE"
        results = root / "reviews" / reviewer / "review_results.jsonl"
        if not marker.is_file():
            fail(f"{label}: missing review completion marker {marker}")
        if not results.is_file():
            fail(f"{label}: missing sealed results {results}")
        count = sum(
            1 for line in results.read_text(encoding="utf-8").splitlines() if line.strip()
        )
        completion[reviewer] = {
            "complete_marker_present": True,
            "complete_marker_sha256": sha256_file(marker),
            "reviewed_cases": count,
        }
    return completion


def verify_known_hash(path: Path, expected: str, what: str) -> str:
    actual = sha256_file(path)
    if actual != expected:
        fail(
            f"known-hash verification failed for {what} ({path}): "
            f"expected {expected} actual {actual}"
        )
    return actual


def copy_items(
    source_root: Path, items: tuple[ImportItem, ...], repo_root: Path
) -> list[dict]:
    entries: list[dict] = []
    for item in items:
        src = source_root / item.source_path
        dst = repo_root / item.imported_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)  # copyfile: never copies permissions/metadata back
        digest = sha256_file(dst)
        source_digest = sha256_file(src)
        if digest != source_digest:
            fail(f"copy of {item.source_path} does not hash-match its source")
        entries.append(
            {
                "source_path": item.source_path,
                "imported_path": item.imported_path,
                "sha256": digest,
                "bytes": dst.stat().st_size,
                "note": item.note,
            }
        )
    return entries


def reference_script_entries(
    source_root: Path, specs: tuple[tuple[str, str], ...], label: str
) -> list[dict]:
    entries: list[dict] = []
    for rel, note in specs:
        path = source_root / rel
        if not path.is_file():
            fail(f"{label}: reference script missing: {rel}")
        entries.append(
            {
                "source_path": rel,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "imported": False,
                "note": note,
            }
        )
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--aidev-path", type=Path, default=DEFAULT_AIDEV_PATH)
    parser.add_argument("--swesmith-path", type=Path, default=DEFAULT_SWESMITH_PATH)
    parser.add_argument(
        "--allow-unpinned",
        action="store_true",
        help="proceed even if a source HEAD differs from the pinned commit "
        "(prints a loud warning; the import is then not the frozen identity)",
    )
    args = parser.parse_args()

    aidev_root = args.aidev_path.resolve()
    swesmith_root = args.swesmith_path.resolve()

    print("== inspecting source repositories (read-only) ==")
    aidev_git = inspect_source(aidev_root, PINNED_AIDEV_COMMIT, args.allow_unpinned, "AIDev")
    swesmith_git = inspect_source(
        swesmith_root, PINNED_SWESMITH_COMMIT, args.allow_unpinned, "SWE-smith"
    )
    print(f"   AIDev      {aidev_root} @ {aidev_git['head']} ({aidev_git['branch']}) clean")
    print(f"   SWE-smith  {swesmith_root} @ {swesmith_git['head']} ({swesmith_git['branch']}) clean")

    print("== verifying expected frozen artifacts exist ==")
    check_exists(aidev_root, AIDEV_ITEMS, "AIDev")
    check_exists(swesmith_root, SWESMITH_ITEMS, "SWE-smith")

    print("== verifying review completion markers ==")
    aidev_completion = check_complete_markers(aidev_root, "AIDev")
    swesmith_completion = check_complete_markers(swesmith_root, "SWE-smith")
    for label, completion in (("AIDev", aidev_completion), ("SWE-smith", swesmith_completion)):
        for reviewer, entry in completion.items():
            print(f"   {label:<10} {reviewer:<7} COMPLETE, {entry['reviewed_cases']} cases")

    print("== verifying known hashes BEFORE copying ==")
    aidev_mapping = aidev_root / "analysis/taxonomy/proposed_pattern_families.yaml"
    aidev_taxonomy = aidev_root / "analysis/taxonomy/frozen_failure_taxonomy_v1.md"
    swesmith_mapping = swesmith_root / "taxonomy/pattern_families.yaml"
    swesmith_taxonomy = swesmith_root / "taxonomy/frozen_failure_taxonomy_v1.md"
    snapshot = swesmith_root / "data/review_snapshot_manifest.json"
    review_manifest = swesmith_root / "data/review_manifest.csv"

    verify_known_hash(aidev_mapping, KNOWN_FAMILY_MAPPING_SHA256, "AIDev family mapping")
    verify_known_hash(swesmith_mapping, KNOWN_FAMILY_MAPPING_SHA256, "SWE-smith family mapping")
    verify_known_hash(aidev_taxonomy, KNOWN_TAXONOMY_SHA256, "AIDev frozen taxonomy")
    verify_known_hash(swesmith_taxonomy, KNOWN_TAXONOMY_SHA256, "SWE-smith frozen taxonomy")
    verify_known_hash(snapshot, KNOWN_SNAPSHOT_SHA256, "SWE-smith review snapshot manifest")
    verify_known_hash(review_manifest, KNOWN_REVIEW_MANIFEST_SHA256, "SWE-smith review manifest")
    print("   family mapping   " + KNOWN_FAMILY_MAPPING_SHA256)
    print("   frozen taxonomy  " + KNOWN_TAXONOMY_SHA256)
    print("   snapshot         " + KNOWN_SNAPSHOT_SHA256)
    print("   review manifest  " + KNOWN_REVIEW_MANIFEST_SHA256)

    print("== asserting the two studies share byte-identical taxonomy artifacts ==")
    if aidev_taxonomy.read_bytes() != swesmith_taxonomy.read_bytes():
        fail("the AIDev and SWE-smith frozen taxonomy files are not byte-identical")
    if aidev_mapping.read_bytes() != swesmith_mapping.read_bytes():
        fail("the AIDev and SWE-smith family mapping files are not byte-identical")
    print("   taxonomy and family mapping are byte-identical across both studies")

    for reviewer in ("codex", "claude"):
        for label, root in (("AIDev", aidev_root), ("SWE-smith", swesmith_root)):
            marker_text = (root / "reviews" / reviewer / "COMPLETE").read_text(
                encoding="utf-8"
            )
            if not marker_text.strip():
                fail(f"{label} {reviewer} COMPLETE marker is empty")

    print("== copying approved artifacts ==")
    aidev_files = copy_items(aidev_root, AIDEV_ITEMS, REPO_ROOT)
    swesmith_files = copy_items(swesmith_root, SWESMITH_ITEMS, REPO_ROOT)
    print(f"   AIDev      {len(aidev_files)} files")
    print(f"   SWE-smith  {len(swesmith_files)} files")

    by_imported = {entry["imported_path"]: entry for entry in aidev_files}
    aidev_manifest = {
        "name": "AIBugAnalysis",
        "repository": "https://github.com/MachineLearningAmateur/AIBugAnalysis",
        "commit_sha": aidev_git["head"],
        "pinned_commit_sha": PINNED_AIDEV_COMMIT,
        "commit_matches_pin": aidev_git["matches_pin"],
        "source_branch": aidev_git["branch"],
        "source_path_at_import": str(aidev_root),
        "source_worktree_clean": True,
        "role": "real_agent_failure_source",
        "taxonomy_version": TAXONOMY_VERSION,
        "corpus": {
            "reviewed_cases": 100,
            "note": (
                "100 PRs were reviewed by both reviewers. The canonical "
                "dual-review agreement population is the 49 cases where BOTH "
                "reviewers assigned a technical pattern (failure_pattern != "
                "UNASSIGNED)."
            ),
        },
        "review_completion": aidev_completion,
        "taxonomy_sha256": KNOWN_TAXONOMY_SHA256,
        "family_mapping_sha256": KNOWN_FAMILY_MAPPING_SHA256,
        "review_result_sha256": {
            "codex": by_imported["data/aidev/reviews/codex/review_results.jsonl"]["sha256"],
            "claude": by_imported["data/aidev/reviews/claude/review_results.jsonl"]["sha256"],
        },
        "reference_scripts": reference_script_entries(
            aidev_root, AIDEV_REFERENCE_SCRIPTS, "AIDev"
        ),
        "excluded_from_import": [
            "data/evidence_packets/** (100 evidence packets, not needed to recompute labels)",
            "data/execution_artifacts/** (agent logs)",
            "reviews/*/cases/** (verified byte-duplicates of the JSONL)",
            "data/derived/*.parquet except aidev_rq1_primary_cases.parquet",
            "scripts/** (cited by hash under reference_scripts instead)",
        ],
        "imported_at_utc": datetime.now(timezone.utc).isoformat(),
        "identity_note": (
            "Identity is commit_sha + the per-file sha256 values. Timestamps "
            "are informational only."
        ),
        "files": aidev_files,
    }

    sw_by_imported = {entry["imported_path"]: entry for entry in swesmith_files}
    swesmith_manifest = {
        "name": "SWE-Smith-Bug-Analysis",
        "repository": "https://github.com/MachineLearningAmateur/SWE-Smith-Bug-Analysis",
        "commit_sha": swesmith_git["head"],
        "pinned_commit_sha": PINNED_SWESMITH_COMMIT,
        "commit_matches_pin": swesmith_git["matches_pin"],
        "source_branch": swesmith_git["branch"],
        "source_path_at_import": str(swesmith_root),
        "source_worktree_clean": True,
        "role": "synthetic_training_bug_source",
        "taxonomy_version": TAXONOMY_VERSION,
        "corpus": {
            "reviewed_cases": 100,
            "population_size": 4207,
            "note": (
                "All 100 frozen cases enter the agreement computation: the "
                "SWE-smith review schema has no UNASSIGNED value, so there is "
                "no exclusion rule to apply."
            ),
        },
        "review_completion": swesmith_completion,
        "taxonomy_sha256": KNOWN_TAXONOMY_SHA256,
        "family_mapping_sha256": KNOWN_FAMILY_MAPPING_SHA256,
        "snapshot_sha256": KNOWN_SNAPSHOT_SHA256,
        "review_manifest_sha256": KNOWN_REVIEW_MANIFEST_SHA256,
        "review_result_sha256": {
            "codex": sw_by_imported["data/swesmith/reviews/codex/review_results.jsonl"]["sha256"],
            "claude": sw_by_imported["data/swesmith/reviews/claude/review_results.jsonl"]["sha256"],
        },
        "reference_scripts": reference_script_entries(
            swesmith_root, SWESMITH_REFERENCE_SCRIPTS, "SWE-smith"
        ),
        "excluded_from_import": [
            "data/review_packets/** (100 packet directories)",
            "reviews/*/cases/** (verified duplicates of the JSONL)",
            "data/population/swesmith_training_tasks.csv|.parquet (1.0 MB / 293 KB)",
            "archive/** (parked work, not part of the current design)",
            "runs/, tests/, the review-draft PDF",
            "scripts/** and ssr/** (cited by hash under reference_scripts instead)",
        ],
        "imported_at_utc": datetime.now(timezone.utc).isoformat(),
        "identity_note": (
            "Identity is commit_sha + the per-file sha256 values. Timestamps "
            "are informational only."
        ),
        "files": swesmith_files,
    }

    sources_dir = REPO_ROOT / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    (sources_dir / "aidev_source.json").write_text(
        json.dumps(aidev_manifest, indent=2) + "\n", encoding="utf-8"
    )
    (sources_dir / "swesmith_source.json").write_text(
        json.dumps(swesmith_manifest, indent=2) + "\n", encoding="utf-8"
    )
    print("== wrote sources/aidev_source.json and sources/swesmith_source.json ==")

    print("== confirming both source repositories are still clean ==")
    for label, root in (("AIDev", aidev_root), ("SWE-smith", swesmith_root)):
        porcelain = git(root, "status", "--porcelain")
        if porcelain:
            fail(f"{label} source repository became dirty during import:\n{porcelain}")
        print(f"   {label:<10} clean, HEAD unchanged at {git(root, 'rev-parse', 'HEAD')}")

    print("import complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
