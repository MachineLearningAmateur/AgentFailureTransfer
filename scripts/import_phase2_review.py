#!/usr/bin/env python3
"""Import one reviewer's SEALED Phase 2 review from its bundle, after verifying it.

    python scripts/import_phase2_review.py --reviewer claude
    python scripts/import_phase2_review.py --reviewer codex --bundle <path>

The reviews are run outside this checkout, in the isolated bundles
``scripts/prepare_phase2_bundles.sh`` exports (by default
``../phase2_review_bundles/phase2_<reviewer>``). This is how a finished review
comes back: not a copy, a *verified* copy.

Before a single byte is written the importer establishes that the bundle is a
bundle exported for this reviewer, that its ``FREEZE_MANIFEST.json`` is
byte-identical to this repository's, that the reviewer sealed
(``COMPLETE``), that ``review_results.jsonl`` still hashes to the value both
``review_metadata.json`` and the marker record, that the seal names this
repository's snapshot manifest, taxonomy fingerprint and freeze manifest, that
it carries exactly the frozen case ids once each, that every record still
validates against this repository's packets, that every per-case file parses to
exactly its sealed line, and that this reviewer has not already been imported.
Any failure prints ``STOP:``, exits 1, and leaves the repository untouched.

On success it copies -- byte for byte, through a staging directory swapped in
atomically -- the per-case files, ``review_results.jsonl``,
``review_metadata.json`` and ``COMPLETE`` into
``experiments/phase2_odc_control/reviews/<reviewer>/``, re-hashes every copy,
and prints the workflow state this repository is now in. ``progress.json`` is a
reviewer's own scratch counter, not part of a seal, and is never copied.

Nothing is written to the bundle, and the analysis is never run from here: when
both reviewers are in, the command to run it is printed for a person to run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if (_SRC / "agentfailuretransfer").is_dir():
    sys.path.insert(0, str(_SRC))

from agentfailuretransfer import paths as repo_paths_module  # noqa: E402
from agentfailuretransfer.phase2 import Phase2Error  # noqa: E402
from agentfailuretransfer.phase2.import_review import (  # noqa: E402
    default_bundle_root,
    import_review,
)
from agentfailuretransfer.phase2.paths import (  # noqa: E402
    REVIEWERS,
    Phase2Paths,
    resolve_paths,
)
from agentfailuretransfer.phase2.state import BOTH_COMPLETE, compute_state  # noqa: E402

ANALYSIS_COMMAND = "python scripts/analyze_phase2_odc.py"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--reviewer", required=True, choices=list(REVIEWERS))
    parser.add_argument(
        "--bundle",
        default=None,
        help="the reviewer's bundle (default: "
        "<repo parent>/phase2_review_bundles/phase2_<reviewer>)",
    )
    parser.add_argument(
        "--root", default=None, help="the in-repository Phase 2 root to import into"
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    reviewer = args.reviewer
    repo = resolve_paths(args.root, script_file=__file__)
    if repo.is_bundle:
        raise Phase2Error(
            f"{repo.root} is a reviewer bundle. A review is imported into the "
            "repository, never into another bundle."
        )
    bundle_root = (
        Path(args.bundle).expanduser()
        if args.bundle
        else default_bundle_root(reviewer, repo_paths_module.REPO_ROOT)
    )
    bundle = Phase2Paths(bundle_root)
    if bundle.root == repo.root:
        raise Phase2Error(
            "the bundle and this repository's Phase 2 root are the same directory; "
            "a review is never made, or imported, inside the checkout that holds "
            "the Phase 1 results"
        )

    verified = import_review(repo, bundle, reviewer)
    state = compute_state(repo)

    summary = {
        "reviewer": reviewer,
        "imported_from": str(bundle.root),
        "imported_into": str(repo.reviewer_dir(reviewer)),
        "cases": verified.case_count,
        "case_id_universe": verified.case_id_universe,
        "results_sha256": verified.results_sha256,
        "files_copied": len(verified.copies),
        "checks": list(verified.checks),
        "workflow_state": state,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"imported {reviewer} from {bundle.root}")
        for check in verified.checks:
            print(f"  verified  {check}")
        print(f"  copied    {len(verified.copies)} file(s) into {repo.reviewer_dir(reviewer)}")
        print()
        print(f"workflow state: {state}")

    if state == BOTH_COMPLETE:
        print()
        print("Both reviewers are sealed here. The Phase 2 analysis may now be run:")
        print(f"    {ANALYSIS_COMMAND}")
        print("This script does not run it.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Phase2Error as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        raise SystemExit(1)
