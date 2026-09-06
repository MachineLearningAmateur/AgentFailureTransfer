"""Bring one reviewer's sealed review back from its bundle into the repository.

The reviews happen outside this checkout, in physically isolated bundles (see
``phase2/bundle.py``). When a reviewer has finalised, its seal has to come home
so that the analysis can be run against it. Copying a directory by hand would
be enough to *move* the bytes; it would not establish that what arrived is the
same sealed review that was produced against the frozen protocol.

This module is the verification. It refuses unless every one of these holds:

1.  the bundle root really is a bundle (``BUNDLE_MANIFEST.json``), exported for
    *this* reviewer, and not a pre-freeze rehearsal export;
2.  the bundle's ``FREEZE_MANIFEST.json`` is byte-identical to the repository's
    -- the reviewer saw the frozen instrument, not a drifted copy;
3.  the reviewer's ``COMPLETE`` marker exists: an unfinalised review is not
    importable, and no partial review is ever brought back;
4.  ``review_results.jsonl`` hashes to the ``results_sha256`` recorded in *both*
    ``review_metadata.json`` and the ``COMPLETE`` marker;
5.  the seal's ``snapshot_manifest_sha256``, ``taxonomy_fingerprint`` and
    ``freeze_manifest_sha256`` equal the repository's own values;
6.  the seal's ``case_id_universe`` is the universe this root's frozen manifest
    actually commits to (``STUDY`` for the 100 study cases);
7.  the results carry exactly the expected case ids, once each;
8.  every record still validates -- against the **repository's** packets, so a
    cited evidence id is checked against evidence this repository holds;
9.  every per-case file in the bundle parses to exactly the record its JSONL
    line carries, so the two halves of the seal cannot disagree;
10. this repository does not already hold a ``COMPLETE`` marker for that
    reviewer. A second import is a stop condition, never an overwrite.

Only then is anything written, and then only into
``reviews/<reviewer>/``: the four kinds of file a seal consists of (the per-case
files, ``review_results.jsonl``, ``review_metadata.json`` and ``COMPLETE``),
byte for byte. ``progress.json`` -- a reviewer's own scratch counter -- is
deliberately not part of a seal and is never copied.

The copy is staged in a sibling directory and swapped in with :func:`os.replace`,
so a failure part-way through cannot leave a half-imported review behind, and
every copied byte is re-hashed afterwards.

Nothing here reads, reports or depends on the other reviewer's state. The only
thing said about it is the workflow state name the repository ends up in, which
is computed the same way it always is.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from agentfailuretransfer.hashing import sha256_file
from agentfailuretransfer.phase2 import Phase2Error
from agentfailuretransfer.phase2.packets import expected_case_ids
from agentfailuretransfer.phase2.paths import (
    COMPLETE_NAME,
    Phase2Paths,
    require_reviewer,
)
from agentfailuretransfer.phase2.review_records import (
    NON_STUDY_CASE_ID_PATTERN,
    REVIEW_FIELDS,
    STUDY_CASE_ID_PATTERN,
    duplicate_case_ids,
    extension_for_reviewer,
    validate_case_file,
    validate_record,
)
from agentfailuretransfer.phase2.taxonomy import taxonomy_fingerprint

#: Where ``scripts/prepare_phase2_bundles.sh`` puts the exported bundles.
DEFAULT_BUNDLE_PARENT_NAME = "phase2_review_bundles"

#: The four kinds of file a seal consists of. Everything else in a reviewer's
#: bundle directory -- ``progress.json`` above all -- stays in the bundle.
RESULTS_NAME = "review_results.jsonl"
METADATA_NAME = "review_metadata.json"

#: Never copied, and named here so the exclusion is a stated rule rather than
#: an accident of the copy list.
NEVER_COPIED = ("progress.json",)

#: Preserved across the directory swap if the repository already had them, so
#: that importing a review does not silently delete a placeholder.
_PLACEHOLDERS = (".gitkeep", "cases/.gitkeep")

_STAGING_SUFFIX = ".import-staging"
_REPLACED_SUFFIX = ".import-replaced"


def default_bundle_root(reviewer: str, repo_root: Path | str) -> Path:
    """``<repo parent>/phase2_review_bundles/phase2_<reviewer>``."""
    require_reviewer(reviewer)
    return (
        Path(repo_root).resolve().parent
        / DEFAULT_BUNDLE_PARENT_NAME
        / f"phase2_{reviewer}"
    )


def case_id_universe(case_ids: Iterable[str]) -> tuple[str, str]:
    """``(universe, pattern)`` for a corpus: the study cases, or a rehearsal.

    Identical in meaning to the same-named helper in
    ``scripts/validate_phase2_review.py``: the 100 study cases are
    ``SWESMITH_001..100`` and anything else is a rehearsal corpus. The seal
    records which one it was, and an import insists the two agree, so a
    rehearsal seal can never be imported over a study root or the reverse.
    """
    ids = list(case_ids)
    study = re.compile(STUDY_CASE_ID_PATTERN)
    if ids and all(study.fullmatch(case_id) for case_id in ids):
        return "STUDY", STUDY_CASE_ID_PATTERN
    return "NON_STUDY", NON_STUDY_CASE_ID_PATTERN


def parse_complete_marker(text: str) -> dict[str, str]:
    """The ``COMPLETE`` marker's ``key value`` lines, as a mapping."""
    marker: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        key, _, value = stripped.partition(" ")
        marker[key] = value.strip()
    return marker


@dataclass(frozen=True)
class VerifiedImport:
    """A verified, not-yet-applied import. Produced only by :func:`verify`."""

    reviewer: str
    repo: Phase2Paths
    bundle: Phase2Paths
    case_ids: tuple[str, ...]
    case_id_universe: str
    results_sha256: str
    #: ``(source in the bundle, path relative to reviews/<reviewer>/)``.
    copies: tuple[tuple[Path, str], ...] = field(default=())
    checks: tuple[str, ...] = field(default=())

    @property
    def case_count(self) -> int:
        return len(self.case_ids)


def _stop(problems: list[str]) -> None:
    if problems:
        raise Phase2Error(
            "this review cannot be imported:\n  " + "\n  ".join(problems[:40])
            + (f"\n  ... and {len(problems) - 40} more" if len(problems) > 40 else "")
        )


def _load_json(path: Path, what: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase2Error(f"{what} ({path}) is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise Phase2Error(f"{what} ({path}) must be a JSON object")
    return value


def verify(repo: Phase2Paths, bundle: Phase2Paths, reviewer: str) -> VerifiedImport:
    """Run every check, in order. Raises :class:`Phase2Error`; writes nothing."""
    require_reviewer(reviewer)
    checks: list[str] = []

    # -- 1. the bundle is a bundle, for this reviewer --------------------------
    if not bundle.root.is_dir():
        raise Phase2Error(f"no bundle at {bundle.root}")
    if not bundle.bundle_manifest.is_file():
        raise Phase2Error(
            f"{bundle.root} is not a reviewer bundle: no "
            f"{bundle.bundle_manifest.name}. Only a bundle exported by "
            "scripts/make_phase2_review_bundle.py carries a seal that can be "
            "verified against the freeze."
        )
    bundle_manifest = _load_json(bundle.bundle_manifest, "the bundle manifest")
    declared = bundle_manifest.get("reviewer")
    if declared != reviewer:
        raise Phase2Error(
            f"{bundle.root} was exported for reviewer {declared!r}, not {reviewer!r}. "
            "One reviewer's output is never imported through the other's bundle."
        )
    if bundle_manifest.get("dry_run"):
        raise Phase2Error(
            f"{bundle.root} is a rehearsal export (dry_run), made before the "
            "protocol freeze. No review of it is a research result and none is "
            "importable."
        )
    checks.append(f"bundle manifest: exported for {reviewer}, not a rehearsal export")

    # -- 2. the same freeze, byte for byte -------------------------------------
    if not repo.freeze_manifest.is_file():
        raise Phase2Error(f"this repository has no freeze manifest at {repo.freeze_manifest}")
    if not bundle.freeze_manifest.is_file():
        raise Phase2Error(
            f"the bundle has no {bundle.freeze_manifest.name}; it cannot be shown "
            "to be a review of the frozen protocol"
        )
    repo_freeze_sha = sha256_file(repo.freeze_manifest)
    bundle_freeze_sha = sha256_file(bundle.freeze_manifest)
    if bundle_freeze_sha != repo_freeze_sha:
        raise Phase2Error(
            f"freeze mismatch: the bundle's FREEZE_MANIFEST.json hashes to "
            f"{bundle_freeze_sha}, this repository's to {repo_freeze_sha}. The "
            "review was made against a different instrument; importing it would "
            "silently mix two protocols."
        )
    checks.append(f"freeze manifest identical: sha256 {repo_freeze_sha}")

    # -- 3. the reviewer sealed -------------------------------------------------
    complete_path = bundle.reviewer_complete(reviewer)
    if not complete_path.is_file():
        raise Phase2Error(
            f"{reviewer} has not sealed this review: no {COMPLETE_NAME} at "
            f"{complete_path}. An unfinalised review is not importable; finish it "
            f"with scripts/validate_phase2_review.py --reviewer {reviewer} --finalize."
        )
    results_path = bundle.reviewer_results(reviewer)
    metadata_path = bundle.reviewer_metadata(reviewer)
    missing = [str(path) for path in (results_path, metadata_path) if not path.is_file()]
    if missing:
        raise Phase2Error(
            f"{reviewer}: a {COMPLETE_NAME} marker exists but the seal is "
            "incomplete; missing:\n  " + "\n  ".join(missing)
        )
    checks.append(f"COMPLETE marker present: {complete_path}")

    # -- 4. the results hash to what the seal says ------------------------------
    metadata = _load_json(metadata_path, f"{reviewer}: review_metadata.json")
    marker = parse_complete_marker(complete_path.read_text(encoding="utf-8"))
    results_sha = sha256_file(results_path)
    problems: list[str] = []
    if metadata.get("results_sha256") != results_sha:
        problems.append(
            f"review_results.jsonl hashes to {results_sha} but review_metadata.json "
            f"records {metadata.get('results_sha256')}; the results changed after "
            "finalization, so this review is void"
        )
    if marker.get("results_sha256") != results_sha:
        problems.append(
            f"review_results.jsonl hashes to {results_sha} but the {COMPLETE_NAME} "
            f"marker records {marker.get('results_sha256')}"
        )
    if marker.get("reviewer") not in (None, reviewer):
        problems.append(
            f"the {COMPLETE_NAME} marker names reviewer {marker.get('reviewer')!r}"
        )
    _stop(problems)
    checks.append(f"results_sha256 agrees with metadata and marker: {results_sha}")

    # -- 5. the seal is tied to this repository's frozen inputs -----------------
    repo_snapshot_sha = sha256_file(repo.snapshot_manifest)
    repo_fingerprint = taxonomy_fingerprint(repo.taxonomy_yaml, repo.schema)
    for key, actual in (
        ("snapshot_manifest_sha256", repo_snapshot_sha),
        ("taxonomy_fingerprint", repo_fingerprint),
        ("freeze_manifest_sha256", repo_freeze_sha),
    ):
        if metadata.get(key) != actual:
            problems.append(
                f"review_metadata.json records {key} {metadata.get(key)!r}; this "
                f"repository's value is {actual!r}"
            )
    _stop(problems)
    checks.append(
        "seal is bound to this repository's snapshot manifest, taxonomy "
        "fingerprint and freeze manifest"
    )

    # -- 6. the right corpus ----------------------------------------------------
    expected = expected_case_ids(repo)
    universe, pattern = case_id_universe(expected)
    if metadata.get("case_id_universe") != universe:
        raise Phase2Error(
            f"review_metadata.json records case_id_universe "
            f"{metadata.get('case_id_universe')!r}, but this root's frozen manifest "
            f"is the {universe} corpus. A rehearsal seal and a study root are never "
            "the same review."
        )
    checks.append(f"case_id_universe {universe}, {len(expected)} expected case(s)")

    # -- 7. exactly the expected cases, once each --------------------------------
    records: list[dict[str, Any]] = []
    for number, line in enumerate(
        results_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"review_results.jsonl line {number}: not valid JSON: {exc}")
            continue
        if not isinstance(record, dict):
            problems.append(f"review_results.jsonl line {number}: not a JSON object")
            continue
        records.append(record)
    _stop(problems)

    if len(records) != len(expected):
        problems.append(
            f"review_results.jsonl holds {len(records)} record(s); this root's "
            f"frozen manifest commits to {len(expected)}"
        )
    for case_id in duplicate_case_ids(records):
        problems.append(f"duplicate review record for {case_id}")
    found = {record.get("case_id") for record in records}
    for case_id in sorted(set(expected) - found):
        problems.append(f"no review record for {case_id}")
    for case_id in sorted(
        value for value in found - set(expected) if isinstance(value, str)
    ):
        problems.append(f"review record for {case_id}, which is not a frozen case")
    declared_count = metadata.get("result_count")
    if isinstance(declared_count, int) and declared_count != len(records):
        problems.append(
            f"review_metadata.json records result_count {declared_count} but "
            f"review_results.jsonl holds {len(records)}"
        )
    _stop(problems)
    checks.append(f"{len(records)} record(s), the expected case ids, no duplicates")

    # -- 8. every record still validates, against THIS repository's packets ------
    for record in sorted(records, key=lambda item: str(item.get("case_id"))):
        case_id = record.get("case_id")
        evidence: set[str] | None = None
        if isinstance(case_id, str):
            from agentfailuretransfer.phase2.packets import packet_evidence_ids

            try:
                evidence = packet_evidence_ids(repo, case_id)
            except Phase2Error as exc:
                problems.append(f"{case_id}: {exc}")
                continue
        for issue in validate_record(
            record,
            case_id_pattern=pattern,
            evidence_ids=evidence,
            expected_case_ids=expected,
        ):
            problems.append(f"review_results.jsonl [{case_id}]: {issue}")
    _stop(problems)
    checks.append("every record validates against this repository's frozen packets")

    # -- 9. the per-case files say the same thing as the JSONL --------------------
    cases_dir = bundle.reviewer_cases(reviewer)
    extension = extension_for_reviewer(reviewer)
    if not cases_dir.is_dir():
        raise Phase2Error(f"{reviewer}: no cases directory at {cases_dir}")
    on_disk = sorted(
        path for path in cases_dir.iterdir() if path.is_file() and path.suffix == extension
    )
    stray = sorted(
        path.name
        for path in cases_dir.iterdir()
        if path.is_file() and path.suffix != extension and path.name != ".gitkeep"
    )
    for name in stray:
        problems.append(
            f"unexpected file in {reviewer} cases/: {name} (this reviewer writes "
            f"{extension} only)"
        )
    by_case = {str(record.get("case_id")): record for record in records}
    seen: set[str] = set()
    for path in on_disk:
        try:
            record, issues = validate_case_file(
                repo,
                reviewer,
                path,
                case_id_pattern=pattern,
                expected_case_ids=expected,
            )
        except Phase2Error as exc:
            problems.append(f"{path.name}: {exc}")
            continue
        problems.extend(f"{path.name}: {issue}" for issue in issues)
        case_id = record.get("case_id")
        if not isinstance(case_id, str):
            continue
        seen.add(case_id)
        sealed = by_case.get(case_id)
        if sealed is None:
            problems.append(f"{path.name}: no line in review_results.jsonl for {case_id}")
        elif {key: record.get(key) for key in REVIEW_FIELDS} != {
            key: sealed.get(key) for key in REVIEW_FIELDS
        }:
            problems.append(
                f"{path.name}: the per-case file and the sealed "
                "review_results.jsonl line are different records"
            )
    for case_id in sorted(set(expected) - seen):
        problems.append(
            f"no per-case file for {case_id} (expected {cases_dir / (case_id + extension)})"
        )
    _stop(problems)
    checks.append(f"{len(on_disk)} per-case file(s) parse to the sealed records")

    # -- 10. this repository has not already imported this reviewer ---------------
    repo_complete = repo.reviewer_complete(reviewer)
    if repo_complete.is_file():
        raise Phase2Error(
            f"{reviewer} is already sealed in this repository ({repo_complete}). "
            "A second import would overwrite an imported seal, which is never "
            "done: establish which of the two is the review of record instead."
        )
    checks.append(f"{reviewer} is not already imported here")

    copies: list[tuple[Path, str]] = [
        (path, f"cases/{path.name}") for path in on_disk
    ]
    copies.append((results_path, RESULTS_NAME))
    copies.append((metadata_path, METADATA_NAME))
    copies.append((complete_path, COMPLETE_NAME))

    return VerifiedImport(
        reviewer=reviewer,
        repo=repo,
        bundle=bundle,
        case_ids=tuple(sorted(str(record["case_id"]) for record in records)),
        case_id_universe=universe,
        results_sha256=results_sha,
        copies=tuple(copies),
        checks=tuple(checks),
    )


def _verify_copies(target: Path, verified: VerifiedImport) -> list[str]:
    """Re-hash everything under ``target`` against the bundle it came from."""
    problems: list[str] = []
    expected_relative = {relative for _, relative in verified.copies}
    for source, relative in verified.copies:
        copied = target / relative
        if not copied.is_file():
            problems.append(f"{relative}: was not copied")
            continue
        actual = sha256_file(copied)
        wanted = sha256_file(source)
        if actual != wanted:
            problems.append(f"{relative}: sha256 {actual} != {wanted} in the bundle")
    results = target / RESULTS_NAME
    if results.is_file() and sha256_file(results) != verified.results_sha256:
        problems.append(
            f"{RESULTS_NAME}: the copy does not hash to the sealed "
            f"{verified.results_sha256}"
        )
    for path in sorted(target.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(target).as_posix()
        if relative in expected_relative or Path(relative).name == ".gitkeep":
            continue
        problems.append(f"{relative}: present but not part of the seal")
    return problems


def apply(verified: VerifiedImport) -> Path:
    """Copy the seal in, via a staging directory swapped in atomically.

    Returns the repository directory the seal now lives in. On any failure the
    repository is left exactly as it was.
    """
    repo = verified.repo
    reviewer = verified.reviewer
    target = repo.reviewer_dir(reviewer)
    staging = repo.reviews_dir / f".{reviewer}{_STAGING_SUFFIX}"
    replaced = repo.reviews_dir / f".{reviewer}{_REPLACED_SUFFIX}"

    for leftover in (staging, replaced):
        if leftover.exists():
            raise Phase2Error(
                f"a leftover import directory is in the way: {leftover}. An earlier "
                "import did not finish; establish why before removing it."
            )

    repo.reviews_dir.mkdir(parents=True, exist_ok=True)
    try:
        (staging / "cases").mkdir(parents=True)
        for source, relative in verified.copies:
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        # Keep a placeholder the repository already tracked; importing a review
        # adds files, it does not remove what was there.
        for placeholder in _PLACEHOLDERS:
            existing = target / placeholder
            if existing.is_file():
                (staging / placeholder).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(existing, staging / placeholder)
        problems = _verify_copies(staging, verified)
        if problems:
            raise Phase2Error(
                "the staged copy does not match the bundle and was discarded:\n  "
                + "\n  ".join(problems[:20])
            )
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    swapped = False
    try:
        if target.exists():
            os.replace(target, replaced)
            swapped = True
        os.replace(staging, target)
    except BaseException:
        if swapped and not target.exists():
            os.replace(replaced, target)
        shutil.rmtree(staging, ignore_errors=True)
        raise
    if swapped:
        shutil.rmtree(replaced, ignore_errors=True)

    problems = _verify_copies(target, verified)
    if problems:
        raise Phase2Error(
            "the imported seal does not re-hash to the bundle it came from:\n  "
            + "\n  ".join(problems[:20])
        )
    return target


def import_review(repo: Phase2Paths, bundle: Phase2Paths, reviewer: str) -> VerifiedImport:
    """Verify, then apply. The whole operation, in that order."""
    verified = verify(repo, bundle, reviewer)
    apply(verified)
    return verified
