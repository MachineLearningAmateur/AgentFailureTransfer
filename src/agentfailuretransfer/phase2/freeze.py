"""The Phase 2 pre-review freeze manifest.

Handoff section 19 lists what must be hashed before either reviewer begins::

    protocol/*.md            (the protocol, the taxonomy-selection rationale,
                              the blinding protocol, and both reviewer prompts)
    taxonomy/*.md, *.yaml
    schemas/odc_review_result.schema.json
    data/review_manifest.csv
    data/review_snapshot_manifest.json
    data/review_packets/**    every file of all 100 packets

:func:`build_manifest` hashes exactly that set and returns a manifest whose
only non-deterministic field is ``frozen_at_utc``. Rebuilding it from an
unchanged tree reproduces every other byte, which is what makes
:func:`verify_freeze_manifest` a drift detector rather than a formality.

This module does not create the git tag. Freezing is a scientific act with a
commit attached to it; a script that silently tags would make that act
invisible. :func:`recommended_tag_command` prints the command instead.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentfailuretransfer.hashing import sha256_file
from agentfailuretransfer.phase2 import Phase2Error
from agentfailuretransfer.phase2.paths import REVIEWERS, Phase2Paths

FREEZE_MANIFEST_VERSION = 1

RECOMMENDED_TAG = "phase2-odc-pre-review-frozen"


def _relative(paths: Phase2Paths, path: Path) -> str:
    return path.resolve().relative_to(paths.root).as_posix()


def freeze_targets(paths: Phase2Paths) -> list[Path]:
    """Every protocol-critical artifact, in a deterministic order.

    Raises if a required artifact is absent: an incomplete freeze is worse than
    no freeze, because it looks like one.
    """
    missing: list[str] = []
    targets: list[Path] = []

    def require(path: Path, what: str) -> None:
        if path.is_file():
            targets.append(path)
        else:
            missing.append(f"{what}: {path}")

    def markdown_in(directory: Path) -> list[Path]:
        return sorted(directory.glob("*.md")) if directory.is_dir() else []

    targets.extend(markdown_in(paths.protocol_dir))
    for reviewer in REVIEWERS:
        prompt = paths.reviewer_prompt(reviewer)
        if not prompt.is_file():
            missing.append(f"reviewer prompt for {reviewer}: {prompt}")

    targets.extend(markdown_in(paths.taxonomy_dir))
    require(paths.taxonomy_md, "frozen ODC rubric (prose)")
    require(paths.taxonomy_provenance, "ODC source provenance")
    require(paths.taxonomy_yaml, "frozen ODC rubric (YAML)")
    require(paths.schema, "review-result schema")
    require(paths.review_manifest, "review manifest")
    require(paths.snapshot_manifest, "review snapshot manifest")

    if not paths.review_packets.is_dir():
        missing.append(f"evidence packets: {paths.review_packets}")
    else:
        targets.extend(
            path for path in sorted(paths.review_packets.rglob("*")) if path.is_file()
        )

    if missing:
        raise Phase2Error(
            "cannot freeze: protocol-critical artifacts are missing:\n  "
            + "\n  ".join(missing)
        )

    # De-duplicate (a prompt is both a protocol/*.md and a required prompt)
    # while keeping a stable, path-sorted order.
    unique = sorted({path.resolve() for path in targets}, key=lambda p: _relative(paths, p))
    return unique


def build_manifest(paths: Phase2Paths, *, frozen_at_utc: str | None = None) -> dict[str, Any]:
    """Hash every protocol-critical artifact. Deterministic but for the time."""
    from agentfailuretransfer.phase2.packets import load_snapshot_manifest
    from agentfailuretransfer.phase2.state import utc_now
    from agentfailuretransfer.phase2.taxonomy import (
        FINGERPRINT_ALGORITHM,
        taxonomy_fingerprint,
    )

    targets = freeze_targets(paths)
    entries = [
        {
            "path": _relative(paths, path),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
        for path in targets
    ]
    snapshot = load_snapshot_manifest(paths.snapshot_manifest)

    return {
        "freeze_manifest_version": FREEZE_MANIFEST_VERSION,
        "phase": "phase2_odc_control",
        "frozen_at_utc": frozen_at_utc if frozen_at_utc is not None else utc_now(),
        "identity_note": (
            "Identity is the per-file sha256 values below. frozen_at_utc is "
            "informational and is excluded from every comparison."
        ),
        "taxonomy_fingerprint": taxonomy_fingerprint(paths.taxonomy_yaml, paths.schema),
        "taxonomy_fingerprint_algorithm": FINGERPRINT_ALGORITHM,
        "schema_sha256": sha256_file(paths.schema),
        "review_manifest_sha256": sha256_file(paths.review_manifest),
        "snapshot_manifest_sha256": sha256_file(paths.snapshot_manifest),
        "reviewer_prompt_sha256": {
            reviewer: sha256_file(paths.reviewer_prompt(reviewer)) for reviewer in REVIEWERS
        },
        "packet_count": len(snapshot["packets"]),
        "file_count": len(entries),
        "recommended_tag": RECOMMENDED_TAG,
        "files": entries,
    }


def serialize(manifest: dict[str, Any]) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_manifest(paths: Phase2Paths, manifest: dict[str, Any]) -> Path:
    paths.freeze_manifest.parent.mkdir(parents=True, exist_ok=True)
    paths.freeze_manifest.write_text(serialize(manifest), encoding="utf-8", newline="\n")
    return paths.freeze_manifest


def load_manifest(paths: Phase2Paths) -> dict[str, Any]:
    path = paths.freeze_manifest
    if not path.is_file():
        raise Phase2Error(f"no freeze manifest at {path}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase2Error(f"{path}: not valid JSON: {exc}") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
        raise Phase2Error(f"{path}: a freeze manifest needs a `files` list")
    return manifest


def comparable(manifest: dict[str, Any]) -> dict[str, Any]:
    """The manifest minus the one field that is allowed to differ."""
    return {key: value for key, value in manifest.items() if key != "frozen_at_utc"}


def verify_freeze_manifest(
    paths: Phase2Paths,
    *,
    allow_missing: bool = False,
    manifest: dict[str, Any] | None = None,
) -> list[str]:
    """Re-hash everything the manifest lists. Returns problem strings.

    ``allow_missing`` is for a reviewer bundle, which by construction ships
    only a subset of the frozen artifacts: the protocol prose and the other
    reviewer's prompt are absent on purpose. Every file that *is* present must
    still hash to the frozen value.
    """
    if manifest is None:
        if not paths.freeze_manifest.is_file():
            return [f"no freeze manifest at {paths.freeze_manifest}"]
        try:
            manifest = load_manifest(paths)
        except Phase2Error as exc:
            return [str(exc)]

    problems: list[str] = []
    for entry in manifest["files"]:
        if not isinstance(entry, dict) or "path" not in entry or "sha256" not in entry:
            problems.append(f"malformed freeze entry: {entry!r}")
            continue
        target = paths.root / entry["path"]
        if not target.is_file():
            if not allow_missing:
                problems.append(f"frozen artifact is missing: {entry['path']}")
            continue
        actual = sha256_file(target)
        if actual != entry["sha256"]:
            problems.append(
                f"freeze drift: {entry['path']} hashes to {actual}, frozen as "
                f"{entry['sha256']}"
            )
    return problems


def check_drift(paths: Phase2Paths) -> list[str]:
    """``--check``: verify the recorded hashes *and* the recorded file set.

    A file added under a frozen directory is drift too: it would be in a bundle
    and in no reviewer's seal.
    """
    problems = verify_freeze_manifest(paths)
    if problems and not paths.freeze_manifest.is_file():
        return problems
    try:
        manifest = load_manifest(paths)
        recorded = {entry["path"] for entry in manifest["files"] if isinstance(entry, dict)}
        current = {_relative(paths, path) for path in freeze_targets(paths)}
    except Phase2Error as exc:
        problems.append(str(exc))
        return problems
    for extra in sorted(current - recorded):
        problems.append(f"freeze drift: {extra} exists but is not in the freeze manifest")
    for gone in sorted(recorded - current):
        problems.append(f"freeze drift: {gone} is in the freeze manifest but not on disk")
    return problems


def freeze_manifest_sha256(paths: Phase2Paths) -> str | None:
    return sha256_file(paths.freeze_manifest) if paths.freeze_manifest.is_file() else None


def recommended_tag_command(tag: str = RECOMMENDED_TAG) -> str:
    return (
        "This script does not create the git tag. After committing the freeze, run:\n"
        f"    git tag -a {tag} -m 'Freeze Phase 2 ODC pre-review protocol'\n"
        "and do not move it afterwards."
    )
