#!/usr/bin/env python3
"""Freeze the Phase 2 ODC protocol, or check an existing freeze for drift.

    python scripts/freeze_phase2.py            # write FREEZE_MANIFEST.json
    python scripts/freeze_phase2.py --check    # verify it, exit 1 on any drift

Handoff section 19: before either reviewer begins, every protocol-critical
artifact is hashed -- the protocol prose, both reviewer prompts, the ODC rubric
in both forms, the review-result schema, the review manifest, the snapshot
manifest, and all 100 packets, file by file.

``--check`` re-hashes each of them and additionally compares the *set* of
frozen files with the set on disk, so a file added under a frozen directory is
drift too. Every field of the manifest except ``frozen_at_utc`` is deterministic,
so rebuilding it from an unchanged tree reproduces it byte for byte.

This script does not create the git tag. Freezing is a scientific act with a
commit attached to it, and a script that tagged silently would make that act
invisible; the recommended command is printed instead.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from agentfailuretransfer.hashing import sha256_file  # noqa: E402
from agentfailuretransfer.phase2 import Phase2Error  # noqa: E402
from agentfailuretransfer.phase2.freeze import (  # noqa: E402
    build_manifest,
    check_drift,
    recommended_tag_command,
    write_manifest,
)
from agentfailuretransfer.phase2.paths import resolve_paths  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--root", default=None, help="the Phase 2 root to freeze")
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the existing manifest instead of writing one",
    )
    args = parser.parse_args()

    paths = resolve_paths(args.root, script_file=__file__)

    if args.check:
        problems = check_drift(paths)
        if problems:
            print("STOP: the Phase 2 freeze has drifted:", file=sys.stderr)
            for problem in problems[:40]:
                print(f"  {problem}", file=sys.stderr)
            if len(problems) > 40:
                print(f"  ... and {len(problems) - 40} more", file=sys.stderr)
            print(
                "\nDo not re-freeze over drift. Establish what changed and why "
                "first: if a reviewer has begun, the review is void.",
                file=sys.stderr,
            )
            return 1
        manifest_sha = sha256_file(paths.freeze_manifest)
        print(f"freeze verified: {paths.freeze_manifest}")
        print(f"  freeze manifest sha256   {manifest_sha}")
        return 0

    if paths.freeze_manifest.is_file():
        problems = check_drift(paths)
        if not problems:
            print(f"already frozen and unchanged: {paths.freeze_manifest}")
            print(f"  freeze manifest sha256   {sha256_file(paths.freeze_manifest)}")
            print()
            print(recommended_tag_command())
            return 0
        print("STOP: a freeze manifest already exists and the tree has drifted:", file=sys.stderr)
        for problem in problems[:40]:
            print(f"  {problem}", file=sys.stderr)
        print(
            "\nRe-freezing would silently redefine the frozen protocol. Resolve the "
            "drift deliberately, or record a protocol amendment, before freezing again.",
            file=sys.stderr,
        )
        return 1

    manifest = build_manifest(paths)
    path = write_manifest(paths, manifest)
    print(f"wrote {path}")
    print(f"  files frozen             {manifest['file_count']}")
    print(f"  packets                  {manifest['packet_count']}")
    print(f"  taxonomy fingerprint     {manifest['taxonomy_fingerprint']}")
    print(f"  schema sha256            {manifest['schema_sha256']}")
    print(f"  snapshot manifest sha256 {manifest['snapshot_manifest_sha256']}")
    print(f"  review manifest sha256   {manifest['review_manifest_sha256']}")
    for reviewer, digest in sorted(manifest["reviewer_prompt_sha256"].items()):
        print(f"  prompt {reviewer:<18} {digest}")
    print(f"  freeze manifest sha256   {sha256_file(path)}")
    print()
    print(recommended_tag_command())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Phase2Error as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        raise SystemExit(1)
