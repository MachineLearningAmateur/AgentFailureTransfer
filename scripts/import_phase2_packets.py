#!/usr/bin/env python3
"""Import the 100 frozen SWE-smith evidence packets for the Phase 2 ODC control.

    python scripts/import_phase2_packets.py [--swesmith-path P]

Phase 2 re-measures the *same* cases with a different instrument. The evidence
must therefore be the Phase 1 evidence -- not a rebuild, not a regeneration,
the identical bytes. This script copies it and proves that it did.

The pinned SWE-smith repository is READ-ONLY scientific provenance. Nothing
here writes, checks out or commits in it; it runs ``git rev-parse`` /
``git status --porcelain`` and reads files.

It stops, with a ``STOP:``-prefixed message and exit 1, if:

* the source is not a clean git repository at the pinned commit;
* ``data/review_snapshot_manifest.json`` or ``data/review_manifest.csv`` does
  not have its known-good SHA-256;
* those two files differ from the copies already imported under
  ``data/swesmith/``, or from the values recorded in
  ``sources/swesmith_source.json``;
* any packet file, or any packet digest, does not reproduce after the copy;
* a forbidden token appears in a packet's own metadata or in either manifest.

Everything is staged in a temporary directory and only swapped into place once
every check has passed, so a failed run leaves the previous state untouched.
Re-running it on an unchanged source is a no-op that re-verifies.

Output: experiments/phase2_odc_control/data/review_packets/**,
data/review_manifest.csv, data/review_snapshot_manifest.json, and
IMPORT_PROVENANCE.json beside them.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from agentfailuretransfer import paths as repo_paths  # noqa: E402
from agentfailuretransfer.hashing import sha256_file  # noqa: E402
from agentfailuretransfer.phase2 import Phase2Error  # noqa: E402
from agentfailuretransfer.phase2.packets import (  # noqa: E402
    digest_from_file_hashes,
    load_snapshot_manifest,
    packet_file_hashes,
    study_case_ids,
)
from agentfailuretransfer.phase2.paths import Phase2Paths  # noqa: E402

DEFAULT_SWESMITH_PATH = Path("/home/disgustingtest/research/SWE-Smith-Bug-Analysis")

PINNED_SWESMITH_COMMIT = "0345139bf449f1fe9401f2a708d0d3b5961d14b2"

# Verification pins, stated in the Phase 2 handoff and in the Phase 1 source
# provenance. They are checked, never assumed: the script compares them against
# the pinned source, against the already-imported Phase 1 copies, and against
# sources/swesmith_source.json, and all four must agree.
KNOWN_SNAPSHOT_SHA256 = (
    "981694c07ffcc9ee9bcf00527d71a0c94b15884ebfc7d8aa537363b3f646a6de"
)
KNOWN_REVIEW_MANIFEST_SHA256 = (
    "64e607800de2a08e4321b371d616841bbd4fbe6deaddb1321dfd355333caebfa"
)

SOURCE_PACKETS_REL = "data/review_packets"
SOURCE_SNAPSHOT_REL = "data/review_snapshot_manifest.json"
SOURCE_REVIEW_MANIFEST_REL = "data/review_manifest.csv"

EXPECTED_PACKET_COUNT = 100

# ---------------------------------------------------------------------------
# The leakage scan.
#
# Two tiers, because the two kinds of file are not comparable.
#
# A packet's own ``packet.json`` and the two manifests were written by the
# source study's harness. Every token below is metadata-shaped there, so a hit
# is fatal.
#
# The evidence bodies -- diffs, code context, specification, test evidence --
# are real third-party source code. ``instance_id`` is an ordinary parameter
# name in one sampled project, ``mirror`` appears in a download-URL comment in
# another, and ``codex`` appears in a pluralisation word list in a third. None
# of that says anything about how a bug was made. Refusing them would refuse a
# correct import, and editing the evidence to avoid them would destroy the
# byte-equivalence with Phase 1 that this whole phase rests on.
#
# So for evidence bodies the scan is a *report*, and only the tokens that are
# unmistakably SWE-smith harness vocabulary are fatal. The real guarantee that
# no foreign content entered is the per-file SHA-256 and the per-packet digest,
# both re-verified after the copy: a corpus that is not Phase 1's cannot pass
# those, whatever words it does or does not contain.
# ---------------------------------------------------------------------------
SCAN_TOKENS = (
    "generation_method",
    "method_family",
    "instance_id",
    "trajectory",
    "failure_pattern",
    "aidev",
    "codex",
    "claude",
    "procedural",
    "mirror",
    "func_pm_",
    "lm_rewrite",
    "lm_modify",
)

#: Fatal even in an evidence body: harness vocabulary, not English or code.
EVIDENCE_FATAL_TOKENS = (
    "generation_method",
    "method_family",
    "func_pm_",
    "lm_rewrite",
    "lm_modify",
    "trajectory",
)

#: Reported, never fatal, in an evidence body. See the note above.
EVIDENCE_ADVISORY_TOKENS = tuple(
    token for token in SCAN_TOKENS if token not in EVIDENCE_FATAL_TOKENS
)

METADATA_FILES = ("packet.json",)


class Stop(SystemExit):
    pass


def fail(message: str) -> None:
    raise Stop(f"STOP: {message}")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    )
    if result.returncode != 0:
        fail(f"git {' '.join(args)} failed in {repo}: {result.stderr.strip()}")
    return result.stdout.strip()


def inspect_source(path: Path) -> dict:
    if not path.is_dir():
        fail(f"the SWE-smith source path does not exist: {path}")
    if not (path / ".git").exists():
        fail(f"the SWE-smith source path is not a git repository: {path}")
    porcelain = git(path, "status", "--porcelain")
    if porcelain:
        fail(
            f"the SWE-smith source repository {path} has uncommitted changes; the "
            f"frozen state is ambiguous. Refusing to import.\n{porcelain}"
        )
    head = git(path, "rev-parse", "HEAD")
    if head != PINNED_SWESMITH_COMMIT:
        fail(
            f"SWE-smith HEAD {head} != pinned commit {PINNED_SWESMITH_COMMIT}. The "
            "Phase 2 evidence must come from the same commit Phase 1 used. "
            "Investigate the HEAD; do not re-pin to get past this."
        )
    return {
        "head": head,
        "branch": git(path, "rev-parse", "--abbrev-ref", "HEAD"),
        "clean": True,
    }


def verify_pinned_hashes(source_root: Path) -> dict:
    """Four independent statements of the same two hashes must agree."""
    source_snapshot = source_root / SOURCE_SNAPSHOT_REL
    source_manifest = source_root / SOURCE_REVIEW_MANIFEST_REL
    for path in (source_snapshot, source_manifest):
        if not path.is_file():
            fail(f"the pinned source is missing {path}")

    observed = {
        "snapshot": sha256_file(source_snapshot),
        "review_manifest": sha256_file(source_manifest),
    }
    expected = {
        "snapshot": KNOWN_SNAPSHOT_SHA256,
        "review_manifest": KNOWN_REVIEW_MANIFEST_SHA256,
    }
    for key, value in observed.items():
        if value != expected[key]:
            fail(
                f"the pinned source {key} hashes to {value}, but the known-good value "
                f"is {expected[key]}. The Phase 2 evidence would not be Phase 1's."
            )

    # The Phase 1 import already copied both files into this repository.
    phase1_copies = {
        "snapshot": repo_paths.SWESMITH_SNAPSHOT_MANIFEST,
        "review_manifest": repo_paths.SWESMITH_REVIEW_MANIFEST,
    }
    for key, path in phase1_copies.items():
        if not path.is_file():
            fail(
                f"the Phase 1 copy of the {key} is missing at {path}. Run "
                "scripts/import_sources.py first; Phase 2 verifies against it."
            )
        actual = sha256_file(path)
        if actual != expected[key]:
            fail(
                f"the already-imported Phase 1 {key} ({path}) hashes to {actual}, "
                f"not {expected[key]}."
            )

    # ... and recorded the same hashes in the source manifest.
    if not repo_paths.SWESMITH_MANIFEST.is_file():
        fail(f"missing {repo_paths.SWESMITH_MANIFEST}; run scripts/import_sources.py first")
    recorded = json.loads(repo_paths.SWESMITH_MANIFEST.read_text(encoding="utf-8"))
    pairs = {
        "snapshot": recorded.get("snapshot_sha256"),
        "review_manifest": recorded.get("review_manifest_sha256"),
    }
    for key, value in pairs.items():
        if value != expected[key]:
            fail(
                f"sources/swesmith_source.json records {key} as {value}, not "
                f"{expected[key]}."
            )
    if recorded.get("commit_sha") != PINNED_SWESMITH_COMMIT:
        fail(
            "sources/swesmith_source.json records commit "
            f"{recorded.get('commit_sha')}, not the pinned {PINNED_SWESMITH_COMMIT}."
        )
    return expected


def scan_file(relative: str, text: str, tokens) -> list[dict]:
    lowered = text.lower()
    return [
        {"path": relative, "token": token, "occurrences": lowered.count(token)}
        for token in tokens
        if token in lowered
    ]


def scan_tree(staging: Path) -> tuple[list[dict], list[dict]]:
    """Returns ``(fatal_hits, advisory_hits)`` over everything just copied."""
    fatal: list[dict] = []
    advisory: list[dict] = []
    for path in sorted(staging.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(staging).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        is_metadata = path.name in METADATA_FILES or path.parent == staging
        if is_metadata:
            fatal.extend(scan_file(relative, text, SCAN_TOKENS))
        else:
            fatal.extend(scan_file(relative, text, EVIDENCE_FATAL_TOKENS))
            advisory.extend(scan_file(relative, text, EVIDENCE_ADVISORY_TOKENS))
    return fatal, advisory


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--swesmith-path", type=Path, default=DEFAULT_SWESMITH_PATH)
    args = parser.parse_args()

    source_root = args.swesmith_path.resolve()
    phase2 = Phase2Paths(repo_paths.PHASE2_DIR)

    print("== inspecting the SWE-smith source repository (read-only) ==")
    source_git = inspect_source(source_root)
    print(f"   {source_root} @ {source_git['head']} ({source_git['branch']}) clean")

    print("== verifying the two pinned hashes, four ways ==")
    pinned = verify_pinned_hashes(source_root)
    print(f"   snapshot manifest  {pinned['snapshot']}")
    print(f"   review manifest    {pinned['review_manifest']}")
    print("   source == known-good == Phase 1 import == sources/swesmith_source.json")

    snapshot = load_snapshot_manifest(source_root / SOURCE_SNAPSHOT_REL)
    manifest_case_ids = sorted(entry["case_id"] for entry in snapshot["packets"])
    expected_case_ids = study_case_ids()
    if manifest_case_ids != expected_case_ids:
        missing = sorted(set(expected_case_ids) - set(manifest_case_ids))
        extra = sorted(set(manifest_case_ids) - set(expected_case_ids))
        fail(
            "the frozen snapshot manifest does not list exactly "
            f"{EXPECTED_PACKET_COUNT} cases SWESMITH_001..100 "
            f"(missing={missing[:5]} unexpected={extra[:5]})"
        )
    print(f"   {len(manifest_case_ids)} case ids, SWESMITH_001..SWESMITH_100")

    print("== verifying every packet at the source before copying ==")
    problems: list[str] = []
    source_packets = source_root / SOURCE_PACKETS_REL
    for entry in snapshot["packets"]:
        directory = source_packets / entry["case_id"]
        if not directory.is_dir():
            problems.append(f"{entry['case_id']}: absent at the source ({directory})")
            continue
        actual = packet_file_hashes(directory)
        if actual != entry["files"]:
            problems.append(f"{entry['case_id']}: source file hashes differ from the manifest")
        if digest_from_file_hashes(actual) != entry["digest"]:
            problems.append(f"{entry['case_id']}: source digest does not reproduce")
    if problems:
        fail(
            "the pinned source packets do not match their own frozen manifest:\n  "
            + "\n  ".join(problems[:20])
        )
    print(f"   {len(snapshot['packets'])} packets verify at the source")

    # -- stage, verify, then swap --------------------------------------------
    data_dir = phase2.data_dir
    staging = data_dir / ".import_staging"
    if staging.exists():
        shutil.rmtree(staging)
    data_dir.mkdir(parents=True, exist_ok=True)
    staging.mkdir()

    try:
        print("== staging a byte-for-byte copy ==")
        copied_files = 0
        for entry in snapshot["packets"]:
            source_dir = source_packets / entry["case_id"]
            target_dir = staging / "review_packets" / entry["case_id"]
            for path in sorted(source_dir.rglob("*")):
                if not path.is_file():
                    continue
                destination = target_dir / path.relative_to(source_dir)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination)
                copied_files += 1
        shutil.copyfile(
            source_root / SOURCE_SNAPSHOT_REL, staging / "review_snapshot_manifest.json"
        )
        shutil.copyfile(
            source_root / SOURCE_REVIEW_MANIFEST_REL, staging / "review_manifest.csv"
        )
        print(f"   {copied_files} packet files + 2 manifests")

        print("== re-verifying every hash and digest after the copy ==")
        after: list[str] = []
        verified_files = 0
        for entry in snapshot["packets"]:
            directory = staging / "review_packets" / entry["case_id"]
            actual = packet_file_hashes(directory)
            for relative, expected in sorted(entry["files"].items()):
                got = actual.get(relative)
                if got != expected:
                    after.append(f"{entry['case_id']}/{relative}: {got} != {expected}")
                else:
                    verified_files += 1
            for relative in sorted(set(actual) - set(entry["files"])):
                after.append(f"{entry['case_id']}/{relative}: unexpected extra file")
            if digest_from_file_hashes(actual) != entry["digest"]:
                after.append(f"{entry['case_id']}: digest does not reproduce after copy")
        for name, expected in (
            ("review_snapshot_manifest.json", pinned["snapshot"]),
            ("review_manifest.csv", pinned["review_manifest"]),
        ):
            got = sha256_file(staging / name)
            if got != expected:
                after.append(f"{name}: {got} != {expected}")
        if after:
            fail(
                "the copy does not reproduce the frozen hashes:\n  "
                + "\n  ".join(after[:20])
            )
        print(f"   {verified_files} files and {len(snapshot['packets'])} digests verified")

        print("== leakage scan over every copied file ==")
        fatal_hits, advisory_hits = scan_tree(staging)
        if fatal_hits:
            fail(
                "forbidden content in the copied evidence:\n  "
                + "\n  ".join(
                    f"{hit['path']}: {hit['token']!r} x{hit['occurrences']}"
                    for hit in fatal_hits[:20]
                )
            )
        print(
            f"   0 fatal hits; {len(advisory_hits)} advisory hit(s) recorded in "
            "IMPORT_PROVENANCE.json"
        )
        for hit in advisory_hits:
            print(f"     note {hit['path']}: {hit['token']!r} x{hit['occurrences']}")

        print("== swapping the verified copy into place ==")
        final_packets = data_dir / "review_packets"
        if final_packets.exists():
            shutil.rmtree(final_packets)
        shutil.move(str(staging / "review_packets"), str(final_packets))
        for name in ("review_snapshot_manifest.json", "review_manifest.csv"):
            shutil.move(str(staging / name), str(data_dir / name))
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    provenance = {
        "phase": "phase2_odc_control",
        "what": (
            "The 100 frozen SWE-smith evidence packets used in Phase 1, copied "
            "byte for byte for re-measurement under the ODC Defect Type taxonomy. "
            "No packet was rebuilt, resampled, regenerated or edited."
        ),
        "source_repository": "https://github.com/MachineLearningAmateur/SWE-Smith-Bug-Analysis",
        "source_path_at_import": str(source_root),
        "source_commit": source_git["head"],
        "source_pinned_commit": PINNED_SWESMITH_COMMIT,
        "source_branch": source_git["branch"],
        "source_worktree_clean": True,
        "snapshot_manifest_sha256": pinned["snapshot"],
        "review_manifest_sha256": pinned["review_manifest"],
        "verified_against": [
            "the pinned source working tree",
            "the known-good hashes in the Phase 2 handoff",
            "the Phase 1 copies under data/swesmith/",
            "sources/swesmith_source.json",
        ],
        "packet_count": len(snapshot["packets"]),
        "packet_file_count": copied_files,
        "case_ids": expected_case_ids,
        "packet_digest_algorithm": (
            "sha256(utf8('\\n'.join(f'{relative_path}:{sha256}' for relative_path in "
            "sorted(files)))) over every file in the packet directory, recursively"
        ),
        "digest_reproduced_at_source": True,
        "digest_reproduced_after_copy": True,
        "leakage_scan": {
            "tokens": list(SCAN_TOKENS),
            "fatal_in_packet_metadata_and_manifests": list(SCAN_TOKENS),
            "fatal_in_evidence_bodies": list(EVIDENCE_FATAL_TOKENS),
            "advisory_in_evidence_bodies": list(EVIDENCE_ADVISORY_TOKENS),
            "advisory_rationale": (
                "Evidence bodies are real third-party source code. These tokens "
                "occur there as ordinary identifiers and English words and say "
                "nothing about how a bug was generated. The byte-level guarantee "
                "is the per-file sha256 and per-packet digest, both re-verified "
                "after the copy."
            ),
            "fatal_hits": [],
            "advisory_hits": advisory_hits,
        },
        "imported_at_utc": utc_now(),
        "identity_note": (
            "Identity is source_commit plus the per-file sha256 values in "
            "review_snapshot_manifest.json. imported_at_utc is informational."
        ),
    }
    phase2.import_provenance.write_text(
        json.dumps(provenance, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"== wrote {phase2.import_provenance.relative_to(REPO_ROOT)} ==")

    print("== confirming the source repository is untouched ==")
    porcelain = git(source_root, "status", "--porcelain")
    if porcelain:
        fail(f"the SWE-smith source became dirty during import:\n{porcelain}")
    head_after = git(source_root, "rev-parse", "HEAD")
    if head_after != source_git["head"]:
        fail(f"the SWE-smith source HEAD moved during import: {head_after}")
    print(f"   clean, HEAD unchanged at {head_after}")

    print(
        f"import complete: {len(snapshot['packets'])}/{EXPECTED_PACKET_COUNT} packets "
        f"verified ({verified_files} files)."
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Stop as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    except Phase2Error as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        sys.exit(1)
