#!/usr/bin/env python3
"""Validate the imported source artifacts. Runs entirely inside this repository.

    python scripts/validate_sources.py

Checks:

* both source manifests load and satisfy the manifest schema;
* every imported file exists and its SHA-256 (and size) matches the manifest;
* both manifests declare taxonomy version ``aidev_failure_taxonomy_v1``;
* the imported taxonomy and family-mapping files are byte-identical across the
  two corpora, and their hashes match the manifests;
* every fine label in every sealed reviewer record is either a mapped fine
  label or (AIDev only) the ``UNASSIGNED`` sentinel;
* required reviewer results are present with the expected case counts;
* no duplicate reviewer case ids, and the two reviewers of each corpus reviewed
  the same case ids;
* the SWE-smith hidden crosswalk has 100 rows matching the reviewed case ids
  exactly, and its method_family values are the four expected ones.

Nothing is repaired. Any failure is reported and exits non-zero.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from agentfailuretransfer import paths  # noqa: E402
from agentfailuretransfer.hashing import sha256_file  # noqa: E402
from agentfailuretransfer.manifest import (  # noqa: E402
    load_manifest,
    validate_manifest_schema,
    verify_manifest_hashes,
)
from agentfailuretransfer.reviews import (  # noqa: E402
    duplicate_case_ids,
    load_review_jsonl,
)
from agentfailuretransfer.taxonomy import (  # noqa: E402
    TAXONOMY_VERSION,
    UNASSIGNED,
    load_family_mapping,
)

EXPECTED_REVIEWED_CASES = {
    "aidev": {"codex": 100, "claude": 100},
    "swesmith": {"codex": 100, "claude": 100},
}

EXPECTED_GENERATION_FAMILIES = {"llm", "mirror", "procedural", "combine"}

# AIDev: 100 cases were reviewed by each reviewer; the canonical dual-review
# agreement population is the 49 where both reviewers assigned a pattern.
AIDEV_EXPECTED_BOTH_ASSIGNED = 49


class Validator:
    def __init__(self) -> None:
        self.problems: list[str] = []
        self.checks = 0

    def check(self, condition: bool, message: str) -> bool:
        self.checks += 1
        if not condition:
            self.problems.append(message)
        return condition

    def report(self, message: str) -> None:
        print(f"   {message}")


def main() -> int:
    v = Validator()

    print("== loading source manifests ==")
    manifests = {}
    for key, path in (("aidev", paths.AIDEV_MANIFEST), ("swesmith", paths.SWESMITH_MANIFEST)):
        if not path.is_file():
            print(f"FAIL: missing manifest {path}", file=sys.stderr)
            return 1
        manifests[key] = load_manifest(path)
        v.report(f"{key:<9} {path.name} loaded ({len(manifests[key]['files'])} files)")

    print("== manifest schema ==")
    for key, manifest in manifests.items():
        problems = validate_manifest_schema(manifest)
        v.check(not problems, f"{key} manifest schema: " + "; ".join(problems))
        v.report(f"{key:<9} schema ok" if not problems else f"{key:<9} SCHEMA PROBLEMS")

    print("== recomputing every imported SHA-256 ==")
    for key, manifest in manifests.items():
        problems = verify_manifest_hashes(manifest, REPO_ROOT)
        v.check(not problems, f"{key} hash verification: " + "; ".join(problems))
        v.report(
            f"{key:<9} {len(manifest['files'])} files verified"
            if not problems
            else f"{key:<9} HASH PROBLEMS: {problems}"
        )

    print("== taxonomy version and pinned commit ==")
    for key, manifest in manifests.items():
        v.check(
            manifest["taxonomy_version"] == TAXONOMY_VERSION,
            f"{key} manifest taxonomy_version is "
            f"{manifest['taxonomy_version']!r}, expected {TAXONOMY_VERSION!r}",
        )
        v.check(
            manifest.get("commit_matches_pin") is True,
            f"{key} manifest records commit {manifest['commit_sha']} which does "
            f"not match its pinned commit {manifest.get('pinned_commit_sha')}",
        )
        v.report(f"{key:<9} {manifest['taxonomy_version']} @ {manifest['commit_sha'][:12]}")

    print("== family mapping identical across the two studies ==")
    aidev_map_bytes = paths.AIDEV_FAMILY_MAPPING.read_bytes()
    swesmith_map_bytes = paths.SWESMITH_FAMILY_MAPPING.read_bytes()
    v.check(
        aidev_map_bytes == swesmith_map_bytes,
        "the imported AIDev and SWE-smith family mappings are not byte-identical",
    )
    v.check(
        paths.AIDEV_TAXONOMY.read_bytes() == paths.SWESMITH_TAXONOMY.read_bytes(),
        "the imported AIDev and SWE-smith frozen taxonomy files are not byte-identical",
    )
    mapping_sha = sha256_file(paths.AIDEV_FAMILY_MAPPING)
    taxonomy_sha = sha256_file(paths.AIDEV_TAXONOMY)
    for key, manifest in manifests.items():
        v.check(
            manifest["family_mapping_sha256"] == mapping_sha,
            f"{key} manifest family_mapping_sha256 does not match the imported file",
        )
        v.check(
            manifest["taxonomy_sha256"] == taxonomy_sha,
            f"{key} manifest taxonomy_sha256 does not match the imported file",
        )
    v.report(f"family mapping {mapping_sha}")
    v.report(f"frozen taxonomy {taxonomy_sha}")

    mapping = load_family_mapping(paths.AIDEV_FAMILY_MAPPING)
    v.report(f"mapping covers {len(mapping)} fine labels -> {len(set(mapping.values()))} families")

    print("== reviewer results ==")
    reviewer_files = {
        "aidev": {
            "codex": paths.AIDEV_CODEX_RESULTS,
            "claude": paths.AIDEV_CLAUDE_RESULTS,
        },
        "swesmith": {
            "codex": paths.SWESMITH_CODEX_RESULTS,
            "claude": paths.SWESMITH_CLAUDE_RESULTS,
        },
    }
    case_id_sets: dict[str, dict[str, set[str]]] = {}
    all_records: dict[str, dict[str, list[dict]]] = {}
    for corpus, reviewers in reviewer_files.items():
        case_id_sets[corpus] = {}
        all_records[corpus] = {}
        for reviewer, path in reviewers.items():
            if not v.check(path.is_file(), f"missing reviewer results: {path}"):
                continue
            records = load_review_jsonl(path)
            all_records[corpus][reviewer] = records
            dupes = duplicate_case_ids(records)
            v.check(
                not dupes,
                f"{corpus}/{reviewer} has duplicate case_ids: {dupes}",
            )
            expected = EXPECTED_REVIEWED_CASES[corpus][reviewer]
            v.check(
                len(records) == expected,
                f"{corpus}/{reviewer} has {len(records)} records, expected {expected}",
            )
            case_id_sets[corpus][reviewer] = {r["case_id"] for r in records}
            marker = path.parent / "COMPLETE"
            v.check(
                marker.is_file() and marker.read_text(encoding="utf-8").strip() != "",
                f"{corpus}/{reviewer} COMPLETE marker missing or empty",
            )
            v.report(f"{corpus:<9} {reviewer:<7} {len(records)} records, no duplicates, COMPLETE")

        ids = case_id_sets[corpus]
        if len(ids) == 2:
            v.check(
                ids["codex"] == ids["claude"],
                f"{corpus}: the two reviewers did not review the same case ids "
                f"(codex-only={sorted(ids['codex'] - ids['claude'])}, "
                f"claude-only={sorted(ids['claude'] - ids['codex'])})",
            )

    print("== fine labels are all mappable ==")
    for corpus, reviewers in all_records.items():
        allow_unassigned = corpus == "aidev"
        for reviewer, records in reviewers.items():
            bad = sorted(
                {
                    r["failure_pattern"]
                    for r in records
                    if r["failure_pattern"] not in mapping
                    and not (allow_unassigned and r["failure_pattern"] == UNASSIGNED)
                }
            )
            v.check(
                not bad,
                f"{corpus}/{reviewer} contains fine labels absent from the frozen "
                f"mapping: {bad}",
            )
        if not allow_unassigned:
            for reviewer, records in reviewers.items():
                offenders = sorted(
                    r["case_id"] for r in records if r["failure_pattern"] == UNASSIGNED
                )
                v.check(
                    not offenders,
                    f"{corpus}/{reviewer} contains UNASSIGNED, which its schema forbids: "
                    f"{offenders}",
                )
        v.report(f"{corpus:<9} every fine label maps to a frozen family")

    print("== AIDev canonical dual-review population ==")
    if all_records.get("aidev", {}).get("codex") and all_records["aidev"].get("claude"):
        codex = {r["case_id"]: r for r in all_records["aidev"]["codex"]}
        claude = {r["case_id"]: r for r in all_records["aidev"]["claude"]}
        both = [
            c
            for c in sorted(codex)
            if codex[c]["failure_pattern"] != UNASSIGNED
            and claude[c]["failure_pattern"] != UNASSIGNED
        ]
        v.check(
            len(both) == AIDEV_EXPECTED_BOTH_ASSIGNED,
            f"AIDev both-assigned population is {len(both)}, expected "
            f"{AIDEV_EXPECTED_BOTH_ASSIGNED}",
        )
        v.report(
            f"100 cases reviewed by each reviewer; {len(both)} have a technical "
            "pattern from both"
        )

    print("== SWE-smith hidden crosswalk ==")
    if paths.SWESMITH_SAMPLE_METADATA.is_file():
        with paths.SWESMITH_SAMPLE_METADATA.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        v.check(len(rows) == 100, f"hidden sample_metadata.csv has {len(rows)} rows, expected 100")
        meta_ids = [row["case_id"] for row in rows]
        v.check(
            len(set(meta_ids)) == len(meta_ids),
            "hidden sample_metadata.csv has duplicate case_ids",
        )
        reviewed = case_id_sets.get("swesmith", {}).get("codex", set())
        v.check(
            set(meta_ids) == reviewed,
            "hidden sample_metadata.csv case ids do not match the reviewed case ids "
            f"(metadata-only={sorted(set(meta_ids) - reviewed)}, "
            f"reviewed-only={sorted(reviewed - set(meta_ids))})",
        )
        families = {row["method_family"] for row in rows}
        v.check(
            families <= EXPECTED_GENERATION_FAMILIES,
            f"unexpected method_family values: {sorted(families - EXPECTED_GENERATION_FAMILIES)}",
        )
        v.report(f"100 rows, ids match the reviewed cases, families = {sorted(families)}")
    else:
        v.check(False, f"missing {paths.SWESMITH_SAMPLE_METADATA}")

    print()
    if v.problems:
        print(f"VALIDATION FAILED ({len(v.problems)} problem(s)):", file=sys.stderr)
        for problem in v.problems:
            print(f"  - {problem}", file=sys.stderr)
        print("Nothing was repaired. Investigate the import.", file=sys.stderr)
        return 1
    print(f"validation passed: {v.checks} checks, 0 problems")
    return 0


if __name__ == "__main__":
    sys.exit(main())
