#!/usr/bin/env python3
"""Export a physically isolated Phase 2 review bundle for one reviewer.

    python scripts/make_phase2_review_bundle.py --reviewer claude --out ../claude_odc
    python scripts/make_phase2_review_bundle.py --reviewer codex  --out ../codex_odc --zip

This repository contains the Phase 1 results, so a Phase 2 reviewer must never
work inside it. The bundle is the mechanical form of that rule: the Phase 1
labels, the hidden generation crosswalk, the analysis, and the other reviewer's
directory are not merely forbidden, they are absent.

The exporter copies an explicit file list -- never a directory tree it has not
enumerated -- and then scans what it built. If any forbidden path or content
token survives, or any packet hash fails inside the bundle, the export is
deleted and the command exits 1.

It refuses to export when:

* the repository working tree is dirty (the bundle would not correspond to any
  commit, so two reviewers could not be shown to have received the same thing);
* the Phase 2 state is below FROZEN_PRE_REVIEW, unless ``--allow-setup``;
* the reviewer's frozen prompt is missing;
* ``--out`` already exists, or lies inside the repository.

``--allow-setup`` is for rehearsing the tooling before the protocol freeze. It
stamps ``"dry_run": true`` into ``BUNDLE_MANIFEST.json``; such a bundle must not
be handed to a reviewer.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from agentfailuretransfer.phase2 import Phase2Error  # noqa: E402
from agentfailuretransfer.phase2.bundle import export  # noqa: E402
from agentfailuretransfer.phase2.paths import REVIEWERS, resolve_paths  # noqa: E402
from agentfailuretransfer.phase2.state import (  # noqa: E402
    FROZEN_PRE_REVIEW,
    SETUP,
    compute_status,
)


def git(*args: str) -> tuple[int, str]:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True
    )
    return result.returncode, result.stdout.strip()


def repository_state(allow_dirty: bool) -> str | None:
    """Returns the source commit, or ``None`` when this is not a git checkout."""
    code, _ = git("rev-parse", "--is-inside-work-tree")
    if code != 0:
        return None
    code, porcelain = git("status", "--porcelain")
    if code == 0 and porcelain and not allow_dirty:
        raise Phase2Error(
            "the repository working tree is dirty, so this bundle would not "
            "correspond to any commit and two reviewers could not be shown to "
            "have received the same frozen protocol. Commit first.\n"
            + porcelain
        )
    code, commit = git("rev-parse", "HEAD")
    return commit if code == 0 else None


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--reviewer", required=True, choices=list(REVIEWERS))
    parser.add_argument("--out", required=True, help="bundle directory to create, outside the repo")
    parser.add_argument("--root", default=None, help="the Phase 2 root to export from")
    parser.add_argument("--zip", action="store_true", help="also write <out>.zip")
    parser.add_argument(
        "--allow-setup",
        action="store_true",
        help="export before the protocol freeze; stamps dry_run: true. Tooling "
        "rehearsal only -- never hand such a bundle to a reviewer.",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="export from a dirty working tree (rehearsal only; recorded in the "
        "bundle manifest)",
    )
    args = parser.parse_args()

    paths = resolve_paths(args.root, script_file=__file__)
    status = compute_status(paths)
    if status.state == SETUP and not args.allow_setup:
        detail = ""
        if status.freeze_problems:
            detail = "\n  " + "\n  ".join(status.freeze_problems[:10])
        raise Phase2Error(
            f"Phase 2 is in state {status.state}; {FROZEN_PRE_REVIEW} is required "
            "before a reviewer bundle may be exported. Freeze the protocol first "
            "(python scripts/freeze_phase2.py), or pass --allow-setup for a "
            f"tooling rehearsal.{detail}"
        )

    source_commit = repository_state(args.allow_dirty)
    dry_run = args.allow_setup or status.state == SETUP

    manifest = export(
        paths,
        args.reviewer,
        Path(args.out),
        repo_root=REPO_ROOT,
        source_commit=source_commit,
        dry_run=dry_run,
        freeze_manifest=paths.freeze_manifest.is_file(),
    )

    out = Path(args.out).resolve()
    archive = None
    if args.zip:
        archive = out.with_suffix(".zip")
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as handle:
            for path in sorted(out.rglob("*")):
                if path.is_file():
                    handle.write(path, path.relative_to(out.parent).as_posix())

    summary = {
        "reviewer": manifest["reviewer"],
        "bundle": str(out),
        "zip": str(archive) if archive else None,
        "dry_run": manifest["dry_run"],
        "state_at_export": status.state,
        "source_commit": manifest["source_commit"],
        "freeze_manifest_sha256": manifest["freeze_manifest_sha256"],
        "snapshot_manifest_sha256": manifest["snapshot_manifest_sha256"],
        "files": manifest["file_count"],
        "excluded_reviewer": manifest["excluded_reviewer"],
        "leak_scan": "passed (paths, content, packet hashes)",
    }
    print(json.dumps(summary, indent=2))
    if manifest["dry_run"]:
        print(
            "\n!!! DRY RUN: this bundle was exported before the protocol freeze. It "
            "is a tooling rehearsal and must not be handed to a reviewer.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Phase2Error as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        raise SystemExit(1)
