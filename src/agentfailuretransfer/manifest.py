"""Source-manifest schema, loading and hash verification.

A manifest is the reproducibility identity of one imported source study:
its pinned commit SHA plus a SHA-256 for every imported file. Timestamps are
recorded for information only and are never used as identity.
"""

from __future__ import annotations

import json
from pathlib import Path

from agentfailuretransfer.hashing import sha256_file

MANIFEST_REQUIRED_KEYS = (
    "name",
    "repository",
    "commit_sha",
    "source_branch",
    "source_path_at_import",
    "role",
    "taxonomy_version",
    "review_completion",
    "taxonomy_sha256",
    "family_mapping_sha256",
    "review_result_sha256",
    "reference_scripts",
    "files",
)

MANIFEST_FILE_ENTRY_KEYS = ("source_path", "imported_path", "sha256", "bytes")

_HEX40 = 40
_HEX64 = 64


def _is_hex(value: str, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(c in "0123456789abcdef" for c in value)
    )


def load_manifest(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_manifest_schema(manifest: dict) -> list[str]:
    """Return a list of schema problems. Empty list means the manifest is valid."""
    problems: list[str] = []

    for key in MANIFEST_REQUIRED_KEYS:
        if key not in manifest:
            problems.append(f"missing top-level key: {key}")

    commit = manifest.get("commit_sha")
    if not _is_hex(commit or "", _HEX40):
        problems.append(f"commit_sha is not a 40-hex git SHA: {commit!r}")

    for key in ("taxonomy_sha256", "family_mapping_sha256"):
        value = manifest.get(key)
        if not _is_hex(value or "", _HEX64):
            problems.append(f"{key} is not a 64-hex sha256: {value!r}")

    review_result_sha256 = manifest.get("review_result_sha256")
    if not isinstance(review_result_sha256, dict) or not review_result_sha256:
        problems.append("review_result_sha256 must be a non-empty object")
    else:
        for reviewer, value in review_result_sha256.items():
            if not _is_hex(value or "", _HEX64):
                problems.append(
                    f"review_result_sha256[{reviewer}] is not a 64-hex sha256"
                )

    review_completion = manifest.get("review_completion")
    if not isinstance(review_completion, dict) or not review_completion:
        problems.append("review_completion must be a non-empty object")
    else:
        for reviewer, entry in review_completion.items():
            if not isinstance(entry, dict):
                problems.append(f"review_completion[{reviewer}] must be an object")
                continue
            for key in ("complete_marker_present", "reviewed_cases"):
                if key not in entry:
                    problems.append(
                        f"review_completion[{reviewer}] missing key: {key}"
                    )

    reference_scripts = manifest.get("reference_scripts")
    if not isinstance(reference_scripts, list):
        problems.append("reference_scripts must be a list")
    else:
        for index, entry in enumerate(reference_scripts):
            if not isinstance(entry, dict):
                problems.append(f"reference_scripts[{index}] must be an object")
                continue
            for key in ("source_path", "sha256", "bytes", "imported"):
                if key not in entry:
                    problems.append(f"reference_scripts[{index}] missing key: {key}")
            if entry.get("imported") is not False:
                problems.append(
                    f"reference_scripts[{index}].imported must be false "
                    "(reference scripts are cited by hash, never copied)"
                )

    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        problems.append("files must be a non-empty list")
        return problems

    seen_imported: set[str] = set()
    for index, entry in enumerate(files):
        if not isinstance(entry, dict):
            problems.append(f"files[{index}] must be an object")
            continue
        for key in MANIFEST_FILE_ENTRY_KEYS:
            if key not in entry:
                problems.append(f"files[{index}] missing key: {key}")
        sha = entry.get("sha256")
        if not _is_hex(sha or "", _HEX64):
            problems.append(f"files[{index}].sha256 is not a 64-hex sha256: {sha!r}")
        size = entry.get("bytes")
        if not isinstance(size, int) or size < 0:
            problems.append(f"files[{index}].bytes must be a non-negative int")
        imported_path = entry.get("imported_path")
        if imported_path in seen_imported:
            problems.append(f"duplicate imported_path: {imported_path}")
        seen_imported.add(imported_path)

    return problems


def verify_manifest_hashes(manifest: dict, repo_root: str | Path) -> list[str]:
    """Recompute every imported file's SHA-256. Returns a list of problems."""
    root = Path(repo_root)
    problems: list[str] = []
    for entry in manifest.get("files", []):
        target = root / entry["imported_path"]
        if not target.is_file():
            problems.append(f"missing imported file: {entry['imported_path']}")
            continue
        actual_size = target.stat().st_size
        if actual_size != entry["bytes"]:
            problems.append(
                f"size mismatch for {entry['imported_path']}: "
                f"manifest={entry['bytes']} actual={actual_size}"
            )
        actual = sha256_file(target)
        if actual != entry["sha256"]:
            problems.append(
                f"sha256 mismatch for {entry['imported_path']}: "
                f"manifest={entry['sha256']} actual={actual}"
            )
    return problems
