"""The Phase 2 workflow state, the write boundary, and the finalization lock.

The state is *computed from the filesystem*, never stored in a variable that
could be set by hand:

``SETUP``               there is no verified freeze manifest yet.
``FROZEN_PRE_REVIEW``   the freeze manifest exists and every artifact it lists
                        still hashes to the recorded value.
``CLAUDE_COMPLETE`` /
``CODEX_COMPLETE``      frozen, and exactly one reviewer has sealed: a COMPLETE
                        marker exists and ``review_results.jsonl`` hashes to the
                        ``results_sha256`` recorded in ``review_metadata.json``.
``BOTH_COMPLETE``       frozen and both reviewers have sealed.
``ANALYZED``            both sealed and the analysis outputs exist.

The two single-reviewer states share a rank: neither is "further along" than
the other, and :func:`assert_state_at_least` treats them as equal. That is what
lets the analysis be gated on ``BOTH_COMPLETE`` without caring who finished
first.

Two mechanical guards live here as well:

:func:`assert_write_boundary` -- every writer path calls it, and it refuses any
target outside ``reviews/<reviewer>/``. A reviewer's tooling cannot touch the
evidence, the rubric, the other reviewer, or the analysis.

:func:`assert_not_finalized` -- once a reviewer's ``COMPLETE`` marker exists,
that reviewer's cases are sealed. Re-saving a case, or re-finalizing, is
refused. A seal that can be quietly amended is not a seal.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from agentfailuretransfer.hashing import sha256_file
from agentfailuretransfer.phase2 import Phase2Error
from agentfailuretransfer.phase2.paths import (
    REVIEWERS,
    Phase2Paths,
    require_reviewer,
)

SETUP = "SETUP"
FROZEN_PRE_REVIEW = "FROZEN_PRE_REVIEW"
CLAUDE_COMPLETE = "CLAUDE_COMPLETE"
CODEX_COMPLETE = "CODEX_COMPLETE"
BOTH_COMPLETE = "BOTH_COMPLETE"
ANALYZED = "ANALYZED"

STATES: tuple[str, ...] = (
    SETUP,
    FROZEN_PRE_REVIEW,
    CLAUDE_COMPLETE,
    CODEX_COMPLETE,
    BOTH_COMPLETE,
    ANALYZED,
)

#: Rank, not order: the two single-reviewer states are equally far along.
STATE_RANK: dict[str, int] = {
    SETUP: 0,
    FROZEN_PRE_REVIEW: 1,
    CLAUDE_COMPLETE: 2,
    CODEX_COMPLETE: 2,
    BOTH_COMPLETE: 3,
    ANALYZED: 4,
}

COMPLETE_STATE_FOR = {"claude": CLAUDE_COMPLETE, "codex": CODEX_COMPLETE}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class ReviewerStatus:
    reviewer: str
    cases_saved: int
    complete_marker: bool
    results_present: bool
    results_sha256: str | None
    metadata_results_sha256: str | None
    sealed: bool
    problems: tuple[str, ...] = ()


@dataclass
class Phase2Status:
    state: str
    frozen: bool
    freeze_problems: list[str] = field(default_factory=list)
    reviewers: dict[str, ReviewerStatus] = field(default_factory=dict)
    analysis_outputs_present: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def rank(self) -> int:
        return STATE_RANK[self.state]


def reviewer_status(paths: Phase2Paths, reviewer: str) -> ReviewerStatus:
    """Whether this reviewer has genuinely sealed, checked against the hashes."""
    require_reviewer(reviewer)
    cases_dir = paths.reviewer_cases(reviewer)
    cases = (
        len([p for p in cases_dir.iterdir() if p.is_file() and p.suffix in {".json", ".yaml"}])
        if cases_dir.is_dir()
        else 0
    )
    complete = paths.reviewer_complete(reviewer).is_file()
    results = paths.reviewer_results(reviewer)
    metadata_path = paths.reviewer_metadata(reviewer)

    results_sha = sha256_file(results) if results.is_file() else None
    metadata_sha: str | None = None
    problems: list[str] = []
    if metadata_path.is_file():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata_sha = metadata.get("results_sha256")
        except json.JSONDecodeError as exc:
            problems.append(f"{reviewer}: review_metadata.json is not valid JSON: {exc}")

    sealed = False
    if complete:
        if results_sha is None:
            problems.append(
                f"{reviewer}: a COMPLETE marker exists but review_results.jsonl does not"
            )
        elif metadata_sha is None:
            problems.append(
                f"{reviewer}: a COMPLETE marker exists but review_metadata.json records "
                "no results_sha256 to bind it to"
            )
        elif metadata_sha != results_sha:
            problems.append(
                f"{reviewer}: review_results.jsonl hashes to {results_sha} but "
                f"review_metadata.json records {metadata_sha}. The sealed results "
                "changed after finalization; this review is void."
            )
        else:
            sealed = True

    return ReviewerStatus(
        reviewer=reviewer,
        cases_saved=cases,
        complete_marker=complete,
        results_present=results is not None and results.is_file(),
        results_sha256=results_sha,
        metadata_results_sha256=metadata_sha,
        sealed=sealed,
        problems=tuple(problems),
    )


def compute_status(paths: Phase2Paths) -> Phase2Status:
    """Derive the workflow state from what is actually on disk."""
    from agentfailuretransfer.phase2.freeze import verify_freeze_manifest

    freeze_problems = verify_freeze_manifest(paths, allow_missing=paths.is_bundle)
    frozen = paths.freeze_manifest.is_file() and not freeze_problems

    reviewers = {name: reviewer_status(paths, name) for name in REVIEWERS}
    sealed = [name for name in REVIEWERS if reviewers[name].sealed]
    analysis_present = all(path.is_file() for path in paths.analysis_outputs)

    notes: list[str] = []
    for status in reviewers.values():
        notes.extend(status.problems)

    if not frozen:
        if sealed:
            notes.append(
                "ANOMALY: "
                + ", ".join(sorted(sealed))
                + " sealed a review, but this root has no verified freeze manifest. "
                "A review that is not tied to a freeze cannot be reported."
            )
        state = SETUP
    elif len(sealed) == len(REVIEWERS):
        state = ANALYZED if analysis_present else BOTH_COMPLETE
    elif len(sealed) == 1:
        state = COMPLETE_STATE_FOR[sealed[0]]
    else:
        state = FROZEN_PRE_REVIEW

    if analysis_present and len(sealed) < len(REVIEWERS):
        notes.append(
            "ANOMALY: analysis outputs exist but not both reviewers have sealed."
        )

    return Phase2Status(
        state=state,
        frozen=frozen,
        freeze_problems=freeze_problems,
        reviewers=reviewers,
        analysis_outputs_present=analysis_present,
        notes=notes,
    )


def compute_state(paths: Phase2Paths) -> str:
    return compute_status(paths).state


def assert_state_at_least(paths: Phase2Paths, required: str) -> Phase2Status:
    """Refuse to continue below ``required``. The analysis gate.

    ``BOTH_COMPLETE`` is the gate the Phase 2 analysis must pass: generation
    metadata and Phase 1 labels may only be joined to ODC labels once both
    reviews are sealed.
    """
    if required not in STATE_RANK:
        raise Phase2Error(f"unknown workflow state {required!r}; expected one of {list(STATES)}")
    status = compute_status(paths)
    if status.rank < STATE_RANK[required]:
        detail = ""
        if status.freeze_problems:
            detail = "\n  " + "\n  ".join(status.freeze_problems[:10])
        raise Phase2Error(
            f"Phase 2 is in state {status.state}; {required} or later is required "
            f"for this operation.{detail}"
        )
    return status


# ---------------------------------------------------------------------------
# the two mechanical guards
# ---------------------------------------------------------------------------
def assert_write_boundary(paths: Phase2Paths, reviewer: str, target: Path | str) -> Path:
    """Refuse any write outside ``reviews/<reviewer>/``. Returns the target."""
    require_reviewer(reviewer)
    allowed = paths.reviewer_dir(reviewer)
    resolved = Path(target).resolve()
    # Resolve the allowed root without requiring it to exist yet.
    allowed_resolved = Path(allowed).resolve()
    try:
        resolved.relative_to(allowed_resolved)
    except ValueError as exc:
        raise Phase2Error(
            f"write boundary: reviewer {reviewer!r} may only write under "
            f"{allowed_resolved}; refused {resolved}"
        ) from exc
    return resolved


def is_finalized(paths: Phase2Paths, reviewer: str) -> bool:
    return paths.reviewer_complete(require_reviewer(reviewer)).is_file()


def assert_not_finalized(paths: Phase2Paths, reviewer: str) -> None:
    """Refuse to modify a reviewer's cases once that reviewer has sealed."""
    if is_finalized(paths, reviewer):
        raise Phase2Error(
            f"finalization lock: {reviewer} is COMPLETE "
            f"({paths.reviewer_complete(reviewer)}). Sealed review output is not "
            "editable. If it genuinely must change, that is a new, explicitly "
            "versioned review, not an edit to this one."
        )


# ---------------------------------------------------------------------------
# writing, all of it through the boundary
# ---------------------------------------------------------------------------
def _write_text(paths: Phase2Paths, reviewer: str, target: Path, text: str) -> Path:
    assert_write_boundary(paths, reviewer, target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")
    return target


def ensure_reviewer_dirs(paths: Phase2Paths, reviewer: str) -> Path:
    cases = paths.reviewer_cases(reviewer)
    assert_write_boundary(paths, reviewer, cases)
    cases.mkdir(parents=True, exist_ok=True)
    return cases


def save_case(paths: Phase2Paths, reviewer: str, record: dict[str, Any]) -> Path:
    """Write one case record immediately, in that reviewer's own format."""
    from agentfailuretransfer.phase2.review_records import dump_record, format_for_reviewer

    assert_not_finalized(paths, reviewer)
    case_id = record.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise Phase2Error("a review record needs a string case_id")
    ensure_reviewer_dirs(paths, reviewer)
    target = paths.reviewer_case_file(reviewer, case_id)
    return _write_text(
        paths, reviewer, target, dump_record(record, format_for_reviewer(reviewer))
    )


def canonical_json_line(record: dict[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def write_metadata(paths: Phase2Paths, reviewer: str, metadata: dict[str, Any]) -> Path:
    return _write_text(
        paths,
        reviewer,
        paths.reviewer_metadata(reviewer),
        json.dumps(metadata, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )


def finalize(
    paths: Phase2Paths,
    reviewer: str,
    records: Iterable[dict[str, Any]],
    *,
    taxonomy_fingerprint: str,
    snapshot_manifest_sha256: str,
    freeze_manifest_sha256: str | None,
    case_id_universe: str = "STUDY",
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Seal one reviewer: write the JSONL, the metadata and the COMPLETE marker.

    The caller has already validated every record. This function only makes the
    seal, and it makes it in an order that cannot leave a half-seal behind: the
    results first, then the metadata that binds them by hash, then the marker.
    """
    from agentfailuretransfer.phase2.review_records import REVIEW_FIELDS

    assert_not_finalized(paths, reviewer)
    ordered = sorted(records, key=lambda record: record["case_id"])
    if not ordered:
        raise Phase2Error(f"{reviewer}: nothing to finalize")

    results_path = paths.reviewer_results(reviewer)
    _write_text(
        paths,
        reviewer,
        results_path,
        "".join(
            canonical_json_line({key: record[key] for key in REVIEW_FIELDS}) + "\n"
            for record in ordered
        ),
    )
    results_sha256 = sha256_file(results_path)
    completed_at = utc_now()

    metadata: dict[str, Any] = {
        "reviewer": reviewer,
        "phase": "phase2_odc_control",
        "taxonomy_id": "odc_defect_type_v1",
        "case_format": "yaml" if reviewer == "claude" else "json",
        "case_id_universe": case_id_universe,
        "completed_at_utc": completed_at,
        "result_count": len(ordered),
        "results_sha256": results_sha256,
        "snapshot_manifest_sha256": snapshot_manifest_sha256,
        "taxonomy_fingerprint": taxonomy_fingerprint,
        "freeze_manifest_sha256": freeze_manifest_sha256,
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    write_metadata(paths, reviewer, metadata)

    marker_lines = [
        f"reviewer {reviewer}",
        f"phase phase2_odc_control",
        f"completed_at_utc {completed_at}",
        f"case_count {len(ordered)}",
        f"case_id_universe {case_id_universe}",
        f"results_sha256 {results_sha256}",
        f"snapshot_manifest_sha256 {snapshot_manifest_sha256}",
        f"taxonomy_fingerprint {taxonomy_fingerprint}",
        f"freeze_manifest_sha256 {freeze_manifest_sha256 or '(none)'}",
    ]
    _write_text(
        paths,
        reviewer,
        paths.reviewer_complete(reviewer),
        "\n".join(marker_lines) + "\n",
    )
    return metadata


def progress(paths: Phase2Paths, reviewer: str, expected_case_ids: Iterable[str]) -> dict[str, Any]:
    """A small counter for the reviewer's own use. Written inside the boundary."""
    from agentfailuretransfer.phase2.review_records import case_id_of_filename

    cases_dir = paths.reviewer_cases(reviewer)
    done = (
        sorted(case_id_of_filename(path.name) for path in cases_dir.iterdir() if path.is_file())
        if cases_dir.is_dir()
        else []
    )
    expected = list(expected_case_ids)
    remaining = [case_id for case_id in expected if case_id not in set(done)]
    record = {
        "reviewer": reviewer,
        "completed": len(done),
        "expected": len(expected),
        "remaining_count": len(remaining),
        "next_case_id": remaining[0] if remaining else None,
        "finalized": is_finalized(paths, reviewer),
        "updated_at_utc": utc_now(),
    }
    if not is_finalized(paths, reviewer):
        _write_text(
            paths,
            reviewer,
            paths.reviewer_progress(reviewer),
            json.dumps(record, indent=2, sort_keys=True) + "\n",
        )
    return record
