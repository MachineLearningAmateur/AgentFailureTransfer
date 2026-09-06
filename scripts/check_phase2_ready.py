#!/usr/bin/env python3
"""Phase 2 preflight. The first command a reviewer runs, wherever they run it.

    python scripts/check_phase2_ready.py --reviewer claude
    python scripts/check_phase2_ready.py --json

It works unchanged in this repository and inside an exported reviewer bundle:
the Phase 2 root is found from the script's own location, or from ``--root``.
No network, no API key, no container. It checks, in order:

1. the Python version and the one package the review path needs;
2. the workflow state, which must be FROZEN_PRE_REVIEW or later;
3. the frozen ODC rubric, and the fingerprint recorded in the freeze manifest;
4. the review-result schema hash;
5. every packet named by the snapshot manifest, re-hashed file by file and
   digest by digest;
6. this reviewer's prompt hash and output directory;
7. isolation: the other reviewer must not be here, and neither must any
   withheld material.

Exit 0 means a review may start. Exit 1 means something must be fixed first,
and each failing line says what. It prints the hashes the reviewer records in
their own notes, so a review can always be tied back to the evidence it saw.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if (_SRC / "agentfailuretransfer").is_dir():
    sys.path.insert(0, str(_SRC))

OK, WARN, FAIL = "OK", "WARN", "FAIL"
MIN_PYTHON = (3, 10)

#: Directory or file names that must never be present beside a reviewer.
WITHHELD_NAMES = (
    "hidden",
    "sources",
    "sample_metadata.csv",
    "pattern_families.yaml",
)


class Report:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.facts: dict[str, str] = {}

    def add(self, check: str, status: str, detail: str, remedy: str = "") -> None:
        self.rows.append(
            {"check": check, "status": status, "detail": detail, "remedy": remedy}
        )

    def fact(self, name: str, value: str) -> None:
        self.facts[name] = value

    @property
    def failures(self) -> list[dict]:
        return [row for row in self.rows if row["status"] == FAIL]

    def render(self) -> str:
        width = max((len(row["check"]) for row in self.rows), default=10)
        lines: list[str] = []
        for row in self.rows:
            lines.append(f"{row['status']:<5} {row['check']:<{width}}  {row['detail']}")
            if row["remedy"] and row["status"] != OK:
                lines.append(f"{'':<5} {'':<{width}}  -> {row['remedy']}")
        return "\n".join(lines)


def check_python(report: Report) -> bool:
    if sys.version_info >= MIN_PYTHON:
        report.add(
            "python",
            OK,
            f"{platform.python_version()} on {platform.system()} ({platform.machine()})",
        )
        return True
    report.add(
        "python",
        FAIL,
        f"{platform.python_version()}; {'.'.join(map(str, MIN_PYTHON))} or later is required",
        "install a newer Python, then re-run this check",
    )
    return False


def check_packages(report: Report) -> bool:
    try:
        import yaml  # noqa: F401

        report.add("package pyyaml", OK, "importable")
        return True
    except ImportError:
        report.add(
            "package pyyaml",
            FAIL,
            "not importable",
            "python -m pip install pyyaml",
        )
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--reviewer", default=None, help="claude or codex")
    parser.add_argument("--root", default=None, help="the Phase 2 root to check")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--allow-setup",
        action="store_true",
        help="accept the SETUP state (tooling rehearsal only; a real review "
        "requires FROZEN_PRE_REVIEW)",
    )
    parser.add_argument(
        "--skip-packet-hashes",
        action="store_true",
        help="skip the per-file re-hash of every packet (faster, weaker)",
    )
    args = parser.parse_args()

    report = Report()
    if not check_python(report) or not check_packages(report):
        print(report.render())
        print("\nFix the above first; the rest of the check needs it.")
        return 1

    from agentfailuretransfer.phase2 import Phase2Error
    from agentfailuretransfer.phase2.freeze import load_manifest as load_freeze
    from agentfailuretransfer.phase2.packets import (
        expected_case_ids,
        load_snapshot_manifest,
        verify_packets,
    )
    from agentfailuretransfer.phase2.paths import REVIEWERS, other_reviewer, resolve_paths
    from agentfailuretransfer.phase2.review_records import extension_for_reviewer
    from agentfailuretransfer.phase2.state import (
        FROZEN_PRE_REVIEW,
        SETUP,
        compute_status,
    )
    from agentfailuretransfer.phase2.taxonomy import load_taxonomy, taxonomy_fingerprint
    from agentfailuretransfer.hashing import sha256_file

    try:
        paths = resolve_paths(args.root, script_file=__file__)
    except Phase2Error as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 1

    report.add("phase 2 root", OK, str(paths.root) + (" (bundle)" if paths.is_bundle else ""))

    # -- 1. workflow state ---------------------------------------------------
    status = compute_status(paths)
    required = SETUP if args.allow_setup else FROZEN_PRE_REVIEW
    state_ok = status.state != SETUP or args.allow_setup
    report.add(
        "workflow state",
        OK if state_ok else FAIL,
        f"{status.state} (need {required} or later)"
        + ("  [--allow-setup: rehearsal only]" if args.allow_setup else ""),
        "freeze the protocol first: python scripts/freeze_phase2.py",
    )
    # The "there is no manifest" case is reported once, below, with the right
    # severity for --allow-setup; here we only surface genuine drift.
    drift = [
        problem
        for problem in status.freeze_problems
        if not problem.startswith("no freeze manifest at")
    ]
    for problem in drift[:10]:
        report.add(
            "freeze drift",
            FAIL,
            problem,
            "establish what changed and why; do not re-freeze over drift",
        )
    for note in status.notes[:10]:
        report.add("workflow note", WARN, note)
    report.fact("workflow_state", status.state)

    # -- 2. the frozen rubric -------------------------------------------------
    fingerprint = None
    try:
        taxonomy = load_taxonomy(paths.taxonomy_yaml)
        fingerprint = taxonomy_fingerprint(paths.taxonomy_yaml, paths.schema)
        report.add(
            "frozen ODC rubric",
            OK,
            f"{taxonomy.taxonomy_id}, {len(taxonomy.canonical_ids)} canonical types "
            f"+ sentinel {taxonomy.sentinel_id}",
        )
        report.fact("taxonomy_fingerprint", fingerprint)
    except Phase2Error as exc:
        report.add(
            "frozen ODC rubric",
            FAIL,
            str(exc).splitlines()[0],
            "the rubric has been altered; restore it before reviewing",
        )

    schema_sha = sha256_file(paths.schema) if paths.schema.is_file() else None
    if schema_sha:
        report.add("review schema", OK, f"sha256 {schema_sha}")
        report.fact("schema_sha256", schema_sha)
    else:
        report.add("review schema", FAIL, f"missing {paths.schema}")

    # -- 3. the freeze manifest's own record ----------------------------------
    if paths.freeze_manifest.is_file():
        try:
            freeze = load_freeze(paths)
            report.fact("freeze_manifest_sha256", sha256_file(paths.freeze_manifest))
            if fingerprint and freeze.get("taxonomy_fingerprint") != fingerprint:
                report.add(
                    "taxonomy fingerprint",
                    FAIL,
                    f"recomputed {fingerprint} != frozen "
                    f"{freeze.get('taxonomy_fingerprint')}",
                    "the rubric or the schema changed after the freeze; a review "
                    "against the changed files would not be the frozen protocol",
                )
            elif fingerprint:
                report.add("taxonomy fingerprint", OK, "matches the freeze manifest")
            if schema_sha and freeze.get("schema_sha256") != schema_sha:
                report.add(
                    "schema hash",
                    FAIL,
                    f"recomputed {schema_sha} != frozen {freeze.get('schema_sha256')}",
                )
        except Phase2Error as exc:
            report.add("freeze manifest", FAIL, str(exc))
    else:
        report.add(
            "freeze manifest",
            WARN if args.allow_setup else FAIL,
            f"absent ({paths.freeze_manifest.name})",
            "run python scripts/freeze_phase2.py before any review",
        )

    # -- 4. the frozen evidence ----------------------------------------------
    try:
        snapshot = load_snapshot_manifest(paths.snapshot_manifest)
        snapshot_sha = sha256_file(paths.snapshot_manifest)
        report.add(
            "snapshot manifest",
            OK,
            f"{len(snapshot['packets'])} packet(s), sha256 {snapshot_sha}",
        )
        report.fact("snapshot_manifest_sha256", snapshot_sha)
        case_ids = expected_case_ids(paths)
        if args.skip_packet_hashes:
            report.add("packet integrity", WARN, "skipped by request")
        else:
            verification = verify_packets(paths, manifest=snapshot)
            if verification.ok:
                report.add(
                    "packet integrity",
                    OK,
                    f"{verification.checked_packets} packet(s), "
                    f"{verification.checked_files} file(s) and every digest match "
                    "the frozen manifest",
                )
            else:
                report.add(
                    "packet integrity",
                    FAIL,
                    f"{len(verification.problems)} problem(s), first: "
                    f"{verification.problems[:3]}",
                    "the evidence changed since it was frozen; a review of it "
                    "would be void",
                )
        if paths.review_manifest.is_file():
            report.fact("review_manifest_sha256", sha256_file(paths.review_manifest))
        else:
            report.add("review manifest", FAIL, f"missing {paths.review_manifest}")
    except Phase2Error as exc:
        report.add("frozen evidence", FAIL, str(exc).splitlines()[0])
        case_ids = []

    # -- 5. this reviewer -----------------------------------------------------
    reviewers = [args.reviewer] if args.reviewer else list(REVIEWERS)
    for reviewer in reviewers:
        if reviewer not in REVIEWERS:
            report.add(f"reviewer {reviewer}", FAIL, f"unknown reviewer; expected {list(REVIEWERS)}")
            continue
        prompt = paths.reviewer_prompt(reviewer)
        if prompt.is_file():
            prompt_sha = sha256_file(prompt)
            report.add(f"prompt {reviewer}", OK, f"sha256 {prompt_sha}")
            report.fact(f"reviewer_prompt_sha256[{reviewer}]", prompt_sha)
            if paths.freeze_manifest.is_file():
                try:
                    frozen_prompt = load_freeze(paths).get("reviewer_prompt_sha256", {})
                except Phase2Error:
                    frozen_prompt = {}
                if frozen_prompt.get(reviewer) not in (None, prompt_sha):
                    report.add(
                        f"prompt {reviewer}",
                        FAIL,
                        f"{prompt_sha} != frozen {frozen_prompt.get(reviewer)}",
                        "the reviewer instructions changed after the freeze",
                    )
        else:
            report.add(
                f"prompt {reviewer}",
                FAIL,
                f"missing {prompt}",
                "a review cannot start without its frozen instructions",
            )

        cases = paths.reviewer_cases(reviewer)
        if not cases.is_dir():
            report.add(
                f"reviewer {reviewer}",
                FAIL,
                f"output directory is absent: {cases}",
                f"mkdir -p {cases}",
            )
        elif not os.access(cases, os.W_OK):
            report.add(f"reviewer {reviewer}", FAIL, f"output directory is not writable: {cases}")
        else:
            done = sorted(
                path.stem for path in cases.iterdir() if path.is_file() and path.suffix != ""
            )
            remaining = [case_id for case_id in case_ids if case_id not in set(done)]
            sealed = paths.reviewer_complete(reviewer).is_file()
            report.add(
                f"reviewer {reviewer}",
                OK,
                (
                    f"SEALED, {len(done)} case(s) recorded"
                    if sealed
                    else f"{len(done)} of {len(case_ids)} done, next "
                    f"{remaining[0] if remaining else '(none)'}"
                    f"{extension_for_reviewer(reviewer)}"
                ),
            )

    # -- 6. isolation ----------------------------------------------------------
    if args.reviewer and args.reviewer in REVIEWERS:
        excluded = other_reviewer(args.reviewer)
        present = paths.reviewer_dir(excluded).exists()
        if paths.is_bundle:
            report.add(
                "reviewer isolation",
                FAIL if present else OK,
                f"the other reviewer ({excluded}) is "
                + ("PRESENT in this bundle" if present else "absent, as required"),
                "this bundle is contaminated; do not review from it",
            )
        else:
            report.add(
                "reviewer isolation",
                WARN if present else OK,
                (
                    f"{excluded}/ exists in this checkout. That is expected in the "
                    "repository, and is exactly why a review must be run from an "
                    "exported bundle rather than here."
                    if present
                    else f"{excluded}/ is absent"
                ),
                "export a bundle: python scripts/make_phase2_review_bundle.py "
                f"--reviewer {args.reviewer} --out <path outside the repo>",
            )

    if paths.is_bundle:
        found = [
            path.relative_to(paths.root).as_posix()
            for path in paths.root.rglob("*")
            if path.name in WITHHELD_NAMES
        ]
        if paths.analysis_dir.exists():
            found.append("analysis/")
        report.add(
            "withheld material",
            FAIL if found else OK,
            ", ".join(found) if found else "none present",
            "this bundle is contaminated; do not review from it",
        )

    # -- output ------------------------------------------------------------------
    if args.json:
        print(
            json.dumps(
                {
                    "root": str(paths.root),
                    "is_bundle": paths.is_bundle,
                    "state": status.state,
                    "checks": report.rows,
                    "record_these": report.facts,
                    "ready": not report.failures,
                },
                indent=2,
            )
        )
        return 1 if report.failures else 0

    print(report.render())
    print()
    print("Record these hashes with your review:")
    for name, value in report.facts.items():
        print(f"  {name:<34} {value}")
    print()
    if report.failures:
        print(f"{len(report.failures)} problem(s) must be fixed before a review can start.")
        return 1
    who = args.reviewer or "<claude|codex>"
    print("This checkout is ready for review.")
    print("  1. Read README.md (your frozen instructions) and taxonomy/odc_defect_type_v1.md in full.")
    print(f"  2. Save one file per case under reviews/{who}/cases/, immediately, never batched.")
    print(f"  3. Validate as you go:  python scripts/validate_phase2_review.py --reviewer {who} --case <CASE_ID>")
    print(f"  4. Finish:              python scripts/validate_phase2_review.py --reviewer {who} --finalize")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
