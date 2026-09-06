#!/usr/bin/env python3
"""Validate one reviewer's ODC records, and seal the review when it is complete.

    python scripts/validate_phase2_review.py --reviewer claude --case SWESMITH_007
    python scripts/validate_phase2_review.py --reviewer claude --all
    python scripts/validate_phase2_review.py --reviewer claude --finalize

Runs unchanged in this repository and inside an exported reviewer bundle: the
Phase 2 root is found from the script's own location, or from ``--root``.

Each record is checked against ``schemas/odc_review_result.schema.json`` --
exactly six fields, the frozen enums, the two-way rule that ``UNCLASSIFIABLE``
and ``OUT_OF_SCOPE`` imply each other, a non-empty unique evidence list and a
10..2000 character reason -- and then cross-checked against the frozen packet:
every cited evidence id must exist in it, and the ``case_id`` must equal the
file name.

``--finalize`` refuses unless every expected case is present, valid, unique and
expected. It then writes ``review_results.jsonl`` (sorted by case id, one
canonical JSON object per line), ``review_metadata.json`` binding that file by
SHA-256, and the ``COMPLETE`` marker recording the snapshot manifest hash, the
taxonomy fingerprint, the freeze manifest hash, the case count and the UTC
time. After that the review is locked: this script will not modify it again.

Every write goes through the reviewer write boundary, so nothing outside
``reviews/<reviewer>/`` can be touched from here.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if (_SRC / "agentfailuretransfer").is_dir():
    sys.path.insert(0, str(_SRC))

from agentfailuretransfer.hashing import sha256_file  # noqa: E402
from agentfailuretransfer.phase2 import Phase2Error  # noqa: E402
from agentfailuretransfer.phase2.freeze import freeze_manifest_sha256  # noqa: E402
from agentfailuretransfer.phase2.packets import expected_case_ids  # noqa: E402
from agentfailuretransfer.phase2.paths import REVIEWERS, resolve_paths  # noqa: E402
from agentfailuretransfer.phase2.review_records import (  # noqa: E402
    NON_STUDY_CASE_ID_PATTERN,
    STUDY_CASE_ID_PATTERN,
    duplicate_case_ids,
    extension_for_reviewer,
    validate_case_file,
)
from agentfailuretransfer.phase2.state import (  # noqa: E402
    assert_not_finalized,
    finalize,
    is_finalized,
    progress,
)
from agentfailuretransfer.phase2.taxonomy import taxonomy_fingerprint  # noqa: E402

import re  # noqa: E402


def case_id_universe(case_ids: list[str]) -> tuple[str, str]:
    """``(universe, pattern)``: the study corpus, or a rehearsal corpus.

    The 100 study cases are ``SWESMITH_001..100``. Any other id set is a
    rehearsal: the tooling still runs end to end on it -- that is the point of
    a dry run -- but it says so, and stamps the seal, so a rehearsal can never
    be mistaken for a research result.
    """
    study = re.compile(STUDY_CASE_ID_PATTERN)
    if case_ids and all(study.fullmatch(case_id) for case_id in case_ids):
        return "STUDY", STUDY_CASE_ID_PATTERN
    return "NON_STUDY", NON_STUDY_CASE_ID_PATTERN


def collect(paths, reviewer: str, expected: list[str], pattern: str, only: list[str] | None):
    """Load and validate case files. Returns ``(records, problems)``."""
    cases_dir = paths.reviewer_cases(reviewer)
    if not cases_dir.is_dir():
        return [], [f"{reviewer}: no cases directory at {cases_dir}"]
    extension = extension_for_reviewer(reviewer)
    files = sorted(path for path in cases_dir.iterdir() if path.is_file() and path.suffix == extension)
    if only is not None:
        wanted = set(only)
        files = [path for path in files if path.stem in wanted]
        absent = sorted(wanted - {path.stem for path in files})
        if absent:
            return [], [
                f"{reviewer}: no record file for {case_id} "
                f"(expected {cases_dir / (case_id + extension)})"
                for case_id in absent
            ]

    stray = sorted(
        path.name
        for path in cases_dir.iterdir()
        if path.is_file() and path.suffix not in {extension, ""} and path.name != ".gitkeep"
    )

    records = []
    problems: list[str] = [
        f"{reviewer}: unexpected file in cases/: {name} (this reviewer writes "
        f"{extension} only)"
        for name in stray
    ]
    for path in files:
        try:
            record, issues = validate_case_file(
                paths,
                reviewer,
                path,
                case_id_pattern=pattern,
                expected_case_ids=expected,
            )
        except Phase2Error as exc:
            problems.append(f"{path.name}: {exc}")
            continue
        records.append(record)
        problems.extend(f"{path.name}: {issue}" for issue in issues)

    for case_id in duplicate_case_ids(records):
        problems.append(f"duplicate review record for {case_id}")
    return records, problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--reviewer", required=True, choices=list(REVIEWERS))
    parser.add_argument("--root", default=None, help="the Phase 2 root to validate in")
    parser.add_argument(
        "--case", action="append", default=[], help="validate one case id; repeatable"
    )
    parser.add_argument("--all", action="store_true", help="validate every saved case")
    parser.add_argument(
        "--finalize",
        action="store_true",
        help="seal the review: write review_results.jsonl, review_metadata.json "
        "and COMPLETE, then lock",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not (args.case or args.all or args.finalize):
        parser.error("choose one of --case ID, --all, or --finalize")

    paths = resolve_paths(args.root, script_file=__file__)
    reviewer = args.reviewer

    expected = expected_case_ids(paths)
    universe, pattern = case_id_universe(expected)
    if universe == "NON_STUDY":
        print(
            "!!! REHEARSAL CORPUS: this root's frozen manifest does not list the "
            "100 study cases. The workflow runs, but nothing produced here is a "
            "research result, and the seal will say so.",
            file=sys.stderr,
        )

    only = args.case or None
    records, problems = collect(paths, reviewer, expected, pattern, only)

    if args.finalize:
        assert_not_finalized(paths, reviewer)
        found = {record["case_id"] for record in records if isinstance(record.get("case_id"), str)}
        missing = sorted(set(expected) - found)
        unexpected = sorted(found - set(expected))
        if missing:
            problems.append(
                f"cannot finalize: {len(missing)} case(s) missing, first {missing[:5]}"
            )
        if unexpected:
            problems.append(f"cannot finalize: unexpected case ids {unexpected[:5]}")

    if problems:
        print("STOP: the review does not validate:", file=sys.stderr)
        for problem in problems[:40]:
            print(f"  {problem}", file=sys.stderr)
        if len(problems) > 40:
            print(f"  ... and {len(problems) - 40} more", file=sys.stderr)
        return 1

    if args.finalize:
        metadata = finalize(
            paths,
            reviewer,
            records,
            taxonomy_fingerprint=taxonomy_fingerprint(paths.taxonomy_yaml, paths.schema),
            snapshot_manifest_sha256=sha256_file(paths.snapshot_manifest),
            freeze_manifest_sha256=freeze_manifest_sha256(paths),
            case_id_universe=universe,
        )
        summary = {
            "reviewer": reviewer,
            "finalized": True,
            "locked": is_finalized(paths, reviewer),
            "cases": metadata["result_count"],
            "case_id_universe": universe,
            "results_sha256": metadata["results_sha256"],
            "complete_marker": str(paths.reviewer_complete(reviewer)),
        }
        print(json.dumps(summary, indent=2))
        return 0

    counter = progress(paths, reviewer, expected)
    summary = {
        "reviewer": reviewer,
        "validated_cases": len(records),
        "expected": len(expected),
        "missing": counter["remaining_count"],
        "next_case_id": counter["next_case_id"],
        "case_id_universe": universe,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Phase2Error as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        raise SystemExit(1)
