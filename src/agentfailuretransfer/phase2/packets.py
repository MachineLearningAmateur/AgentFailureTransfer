"""The 100 frozen evidence packets, and the manifest that pins them.

Phase 2 shows reviewers the *same* evidence Phase 1 showed them. Not a rebuild,
not a regeneration: the identical bytes, verified against the identical frozen
snapshot manifest. This module is the verification side of that promise.

The packet digest
-----------------

Each entry of ``review_snapshot_manifest.json`` carries a per-file ``sha256``
map and a per-packet ``digest``. The digest is::

    sha256( utf8( "\\n".join(f"{relative_path}:{sha256}"
                             for relative_path, sha256 in sorted(files.items())) ) )

where ``files`` covers every regular file under the packet directory,
recursively, keyed by its POSIX-style path relative to that directory, and
``sorted`` is a plain lexicographic sort of those keys. There is no trailing
newline and no separator other than the single ``:`` inside each line.

That algorithm was not assumed. It was read off the pinned source study's own
packet builder and then *reproduced*: recomputing it over all 100 packet
directories in the pinned source reproduces all 100 recorded digests exactly,
and the recomputed per-file hash maps equal the recorded ones for all 615
files. :func:`verify_packets` re-runs both checks against whichever copy of the
packets it is pointed at, so a copy that drifted by one byte cannot pass.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from agentfailuretransfer.hashing import sha256_bytes, sha256_file
from agentfailuretransfer.phase2 import Phase2Error
from agentfailuretransfer.phase2.paths import (
    STUDY_CASE_COUNT,
    STUDY_CASE_PREFIX,
    Phase2Paths,
)


def study_case_ids(count: int = STUDY_CASE_COUNT) -> list[str]:
    """``['SWESMITH_001', ..., 'SWESMITH_100']`` -- the frozen Phase 1 sample."""
    return [f"{STUDY_CASE_PREFIX}{index:03d}" for index in range(1, count + 1)]


def packet_file_hashes(directory: Path | str) -> dict[str, str]:
    """Every regular file under ``directory``, POSIX-relative path -> sha256."""
    directory = Path(directory)
    return {
        path.relative_to(directory).as_posix(): sha256_file(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def digest_from_file_hashes(file_hashes: dict[str, str]) -> str:
    """The packet digest, computed from an already-known hash map."""
    joined = "\n".join(f"{name}:{digest}" for name, digest in sorted(file_hashes.items()))
    return sha256_bytes(joined.encode("utf-8"))


def packet_digest(directory: Path | str) -> str:
    """The packet digest, recomputed from what is on disk right now."""
    return digest_from_file_hashes(packet_file_hashes(directory))


def load_snapshot_manifest(path: Path | str) -> dict[str, Any]:
    """Read the frozen snapshot manifest and check the shape we rely on."""
    path = Path(path)
    if not path.is_file():
        raise Phase2Error(
            f"the frozen snapshot manifest is missing: {path}. Without it there is "
            "no frozen evidence for a review to be tied to."
        )
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase2Error(f"{path}: not valid JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise Phase2Error(f"{path}: the snapshot manifest must be a JSON object")
    packets = manifest.get("packets")
    if not isinstance(packets, list) or not packets:
        raise Phase2Error(f"{path}: `packets` must be a non-empty list")
    for index, entry in enumerate(packets):
        if not isinstance(entry, dict):
            raise Phase2Error(f"{path}: packets[{index}] must be an object")
        for key in ("case_id", "digest", "files"):
            if key not in entry:
                raise Phase2Error(f"{path}: packets[{index}] is missing {key!r}")
        if not isinstance(entry["files"], dict) or not entry["files"]:
            raise Phase2Error(f"{path}: packets[{index}].files must be a non-empty object")
    declared = manifest.get("packet_count")
    if isinstance(declared, int) and declared != len(packets):
        raise Phase2Error(
            f"{path}: packet_count is {declared} but {len(packets)} packets are listed"
        )
    return manifest


def manifest_case_ids(manifest: dict[str, Any]) -> list[str]:
    return sorted(entry["case_id"] for entry in manifest["packets"])


def expected_case_ids(paths: Phase2Paths) -> list[str]:
    """The case ids this root's frozen manifest commits to."""
    return manifest_case_ids(load_snapshot_manifest(paths.snapshot_manifest))


@dataclass(frozen=True)
class PacketVerification:
    checked_packets: int
    checked_files: int
    problems: list[str]

    @property
    def ok(self) -> bool:
        return not self.problems


def verify_packets(
    paths: Phase2Paths,
    *,
    manifest: dict[str, Any] | None = None,
    case_ids: Iterable[str] | None = None,
) -> PacketVerification:
    """Re-hash every packet file and recompute every packet digest.

    Reports, rather than raises, so a preflight can print the whole picture.
    An extra file inside a packet directory is a problem too: it would change
    the digest, and a reviewer bundle must not carry anything the freeze did
    not commit to.
    """
    manifest = manifest or load_snapshot_manifest(paths.snapshot_manifest)
    wanted = set(case_ids) if case_ids is not None else None
    problems: list[str] = []
    checked_packets = 0
    checked_files = 0

    for entry in manifest["packets"]:
        case_id = entry["case_id"]
        if wanted is not None and case_id not in wanted:
            continue
        directory = paths.packet_dir(case_id)
        if not directory.is_dir():
            problems.append(f"{case_id}: packet directory is absent ({directory})")
            continue
        checked_packets += 1
        expected_files: dict[str, str] = entry["files"]
        actual_files = packet_file_hashes(directory)

        for relative, expected in sorted(expected_files.items()):
            actual = actual_files.get(relative)
            if actual is None:
                problems.append(f"{case_id}/{relative}: file is absent")
            elif actual != expected:
                problems.append(
                    f"{case_id}/{relative}: sha256 {actual} != frozen {expected}"
                )
            else:
                checked_files += 1
        for relative in sorted(set(actual_files) - set(expected_files)):
            problems.append(
                f"{case_id}/{relative}: file is present but not in the frozen manifest"
            )

        actual_digest = digest_from_file_hashes(actual_files)
        if actual_digest != entry["digest"]:
            problems.append(
                f"{case_id}: packet digest {actual_digest} != frozen {entry['digest']}"
            )

    if wanted is None:
        listed = {entry["case_id"] for entry in manifest["packets"]}
        if paths.review_packets.is_dir():
            on_disk = {
                child.name for child in paths.review_packets.iterdir() if child.is_dir()
            }
            for extra in sorted(on_disk - listed):
                problems.append(
                    f"{extra}: packet directory is present but not in the frozen manifest"
                )

    return PacketVerification(checked_packets, checked_files, problems)


def load_packet(paths: Phase2Paths, case_id: str) -> dict[str, Any]:
    packet_path = paths.packet_dir(case_id) / "packet.json"
    if not packet_path.is_file():
        raise Phase2Error(f"no frozen packet for {case_id}: {packet_path} does not exist")
    try:
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase2Error(f"{packet_path}: not valid JSON: {exc}") from exc
    if not isinstance(packet, dict):
        raise Phase2Error(f"{packet_path}: a packet must be a JSON object")
    return packet


def packet_evidence_ids(paths: Phase2Paths, case_id: str) -> set[str]:
    """The evidence ids a reviewer may cite for this case."""
    ids = load_packet(paths, case_id).get("evidence_ids")
    if not isinstance(ids, list) or not ids:
        raise Phase2Error(f"{case_id}: the packet declares no evidence_ids")
    return {str(value) for value in ids}
