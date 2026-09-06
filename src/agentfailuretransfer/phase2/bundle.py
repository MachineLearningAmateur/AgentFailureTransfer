"""Export one physically isolated reviewer bundle, and refuse a leaky one.

This repository holds the Phase 1 results. A Phase 2 reviewer must therefore
never work inside it: the Phase 1 labels, the hidden generation crosswalk, the
analysis and the other reviewer's output are not merely forbidden by
instruction, they are *absent* from what the reviewer receives.

A bundle contains exactly:

    README.md                          this reviewer's prompt, verbatim
    protocol/reviewer_prompt_<r>.md    the same file under its own name
    taxonomy/odc_defect_type_v1.md
    taxonomy/odc_defect_type_v1.yaml
    taxonomy/SOURCE_PROVENANCE.md
    schemas/odc_review_result.schema.json
    src/agentfailuretransfer/...       only the modules the review path imports
    scripts/check_phase2_ready.py
    scripts/validate_phase2_review.py
    data/review_packets/**             the 100 frozen packets, byte for byte
    data/review_manifest.csv
    data/review_snapshot_manifest.json
    FREEZE_MANIFEST.json
    reviews/<reviewer>/cases/          empty
    BUNDLE_MANIFEST.json               written last

Exclusion is done twice, on purpose. The exporter copies an explicit list --
never a directory tree it has not enumerated -- and then *scans what it built*.
If the scan finds anything on the forbidden list, the export is deleted and the
command fails. An exporter that only excluded, without re-checking, would be
one refactor away from shipping the study's own answers.

Two tiers of content scan
-------------------------
``FORBIDDEN_CONTENT_TOKENS`` are metadata-shaped strings that cannot occur by
accident -- field names out of the generation harness and the Phase 1 label
schema. A hit anywhere in a bundle, prose included, is fatal.

``AMBIGUOUS_CONTENT_TOKENS`` -- ``instance_id``, ``trajectory`` -- are ordinary
programming words and ordinary English. Two places in a *correct* bundle
contain them, and in both the byte content is pinned by a hash, so the scan
records the hit in ``BUNDLE_MANIFEST.json`` instead of refusing:

* **the frozen evidence** (``data/review_packets/``) is real third-party source
  code. One sampled project has an ``instance_id`` parameter. Editing the
  evidence to avoid the word would destroy the byte-equivalence with Phase 1
  that the whole experiment rests on. Every packet file is separately re-hashed
  against the frozen snapshot manifest, which is a far stronger guarantee than
  a word search.

* **the frozen protocol prose** (``README.md`` and ``protocol/``) is the
  reviewer's own instructions, and its job includes *naming what is withheld*
  -- "no source model, no trajectory, no attempt count". Refusing there would
  mean the blinding instruction could not state what it blinds. The prompt is
  hash-pinned in the freeze manifest and reviewed by a person before the
  freeze, and the metadata-shaped tokens above stay fatal in it.

Everywhere else -- the library, the scripts, ``packet.json``, the manifests --
a hit on an ambiguous token is fatal.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentfailuretransfer.hashing import sha256_file
from agentfailuretransfer.phase2 import Phase2Error
from agentfailuretransfer.phase2.paths import (
    Phase2Paths,
    other_reviewer,
    require_reviewer,
    reviewer_prompt_name,
)

#: Library modules the review path imports. Listed one by one rather than
#: copying ``src/`` wholesale, so a bundle cannot ship the analysis code, the
#: statistics module, or anything whose text describes a Phase 1 result.
BUNDLE_LIBRARY_MODULES: tuple[str, ...] = (
    "agentfailuretransfer/__init__.py",
    "agentfailuretransfer/hashing.py",
    "agentfailuretransfer/reviews.py",
    "agentfailuretransfer/phase2/__init__.py",
    "agentfailuretransfer/phase2/paths.py",
    "agentfailuretransfer/phase2/taxonomy.py",
    "agentfailuretransfer/phase2/packets.py",
    "agentfailuretransfer/phase2/review_records.py",
    "agentfailuretransfer/phase2/state.py",
    "agentfailuretransfer/phase2/freeze.py",
)

#: Deliberately absent: ``agreement``/``stats`` (numpy, scipy, and Phase 1
#: numbers in their docstrings), ``manifest``/``taxonomy``/``paths`` (Phase 1
#: artifacts by name), ``phase2/bundle.py`` (the exporter itself), and every
#: analysis module.
BUNDLE_EXCLUDED_LIBRARY_MODULES: tuple[str, ...] = (
    "agentfailuretransfer/agreement.py",
    "agentfailuretransfer/stats.py",
    "agentfailuretransfer/manifest.py",
    "agentfailuretransfer/paths.py",
    "agentfailuretransfer/taxonomy.py",
    "agentfailuretransfer/phase2/bundle.py",
    "agentfailuretransfer/phase2/analysis.py",
)

BUNDLE_SCRIPTS: tuple[str, ...] = (
    "check_phase2_ready.py",
    "validate_phase2_review.py",
)

#: Any bundle path containing one of these is a leak. Matched case-sensitively
#: against the POSIX relative path, except ``aidev`` which is matched lowercased.
FORBIDDEN_PATH_TOKENS: tuple[str, ...] = (
    "hidden/",
    "analysis/",
    "sources/",
    "aidev",
    "phase1",
    "robustness",
    "headline",
    "generation",
    "sample_metadata",
    "review_results.jsonl",
    "COMPLETE",
    "pattern_families",
    "frozen_failure_taxonomy",
)

#: Fatal wherever they appear in a text file.
FORBIDDEN_CONTENT_TOKENS: tuple[str, ...] = (
    "generation_method",
    "method_family",
    "func_pm_",
    "failure_pattern",
    "aidev_failure_taxonomy",
    "lm_rewrite",
    "lm_modify",
)

#: Ordinary words. Recorded, not fatal, in the two hash-pinned zones below.
AMBIGUOUS_CONTENT_TOKENS: tuple[str, ...] = ("instance_id", "trajectory")

#: Where the frozen evidence lives inside a bundle.
EVIDENCE_PREFIX = "data/review_packets/"

#: The frozen reviewer prose, which must be able to name what it withholds.
PROSE_PATHS = ("README.md",)
PROSE_PREFIXES = ("protocol/",)

#: File suffixes worth reading as text during the content scan.
_BINARY_SUFFIXES = frozenset({".parquet", ".pdf", ".png", ".jpg", ".zip", ".pyc"})


@dataclass
class ScanResult:
    fatal: list[str] = field(default_factory=list)
    notes: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.fatal


def _read_text(path: Path) -> str | None:
    if path.suffix.lower() in _BINARY_SUFFIXES:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def scan_paths(root: Path, reviewer: str) -> list[str]:
    """Forbidden path components, including the other reviewer's directory."""
    require_reviewer(reviewer)
    forbidden_reviewer = other_reviewer(reviewer)
    problems: list[str] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        haystack = relative if path.is_file() else relative + "/"
        for token in FORBIDDEN_PATH_TOKENS:
            probe = haystack.lower() if token.islower() else haystack
            if token in probe:
                problems.append(f"forbidden path token {token!r}: {relative}")
        if forbidden_reviewer in Path(relative).parts:
            problems.append(
                f"the other reviewer's directory {forbidden_reviewer!r} is present: {relative}"
            )
    return problems


def scan_contents(root: Path) -> ScanResult:
    """The two-tier content scan described in the module docstring."""
    result = ScanResult()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        text = _read_text(path)
        if text is None:
            continue
        lowered = text.lower()
        for token in FORBIDDEN_CONTENT_TOKENS:
            if token in lowered:
                result.fatal.append(f"forbidden content token {token!r} in {relative}")
        reason = _advisory_reason(relative)
        for token in AMBIGUOUS_CONTENT_TOKENS:
            if token not in lowered:
                continue
            if relative == "BUNDLE_MANIFEST.json":
                # The exporter's own audit record names the tokens it recorded.
                continue
            if reason is None:
                result.fatal.append(f"forbidden content token {token!r} in {relative}")
            else:
                result.notes.append(
                    {
                        "path": relative,
                        "token": token,
                        "occurrences": lowered.count(token),
                        "why_not_fatal": reason,
                    }
                )
    return result


def _advisory_reason(relative: str) -> str | None:
    """Why an ambiguous token is tolerated here, or ``None`` if it is not."""
    if relative.startswith(EVIDENCE_PREFIX) and not relative.endswith("/packet.json"):
        return (
            "ordinary identifier in frozen third-party source code; the file is "
            "byte-identical to the Phase 1 evidence and is re-hashed against the "
            "frozen snapshot manifest"
        )
    if relative in PROSE_PATHS or relative.startswith(PROSE_PREFIXES):
        return (
            "frozen reviewer prose, which must be able to name what it withholds; "
            "the file is hash-pinned in the freeze manifest"
        )
    return None


def verify_bundle_packets(bundle_root: Path) -> list[str]:
    """Re-hash every packet inside the bundle against the bundle's own manifest."""
    from agentfailuretransfer.phase2.packets import verify_packets

    verification = verify_packets(Phase2Paths(bundle_root))
    return list(verification.problems)


@dataclass
class BundlePlan:
    """The explicit file list. Nothing outside it is ever copied."""

    copies: list[tuple[Path, str]]
    empty_dirs: tuple[str, ...]


def plan_bundle(
    paths: Phase2Paths, reviewer: str, *, repo_root: Path, freeze_manifest: bool = True
) -> BundlePlan:
    require_reviewer(reviewer)
    prompt = paths.reviewer_prompt(reviewer)
    if not prompt.is_file():
        raise Phase2Error(
            f"the reviewer prompt for {reviewer} is missing: {prompt}. A bundle "
            "without the reviewer's instructions cannot be exported."
        )

    copies: list[tuple[Path, str]] = [
        # The prompt is the bundle's README so it is the first thing opened,
        # and keeps its own name so its hash matches the freeze manifest entry.
        (prompt, "README.md"),
        (prompt, f"protocol/{reviewer_prompt_name(reviewer)}"),
        (paths.taxonomy_yaml, "taxonomy/odc_defect_type_v1.yaml"),
        (paths.taxonomy_md, "taxonomy/odc_defect_type_v1.md"),
        (paths.taxonomy_provenance, "taxonomy/SOURCE_PROVENANCE.md"),
        (paths.schema, "schemas/odc_review_result.schema.json"),
        (paths.review_manifest, "data/review_manifest.csv"),
        (paths.snapshot_manifest, "data/review_snapshot_manifest.json"),
    ]
    if freeze_manifest:
        copies.append((paths.freeze_manifest, "FREEZE_MANIFEST.json"))

    for module in BUNDLE_LIBRARY_MODULES:
        copies.append((repo_root / "src" / module, f"src/{module}"))
    for script in BUNDLE_SCRIPTS:
        copies.append((repo_root / "scripts" / script, f"scripts/{script}"))

    if not paths.review_packets.is_dir():
        raise Phase2Error(f"no frozen evidence packets at {paths.review_packets}")
    for path in sorted(paths.review_packets.rglob("*")):
        if path.is_file():
            relative = path.relative_to(paths.review_packets).as_posix()
            copies.append((path, f"{EVIDENCE_PREFIX}{relative}"))

    missing = [str(source) for source, _ in copies if not source.is_file()]
    if missing:
        raise Phase2Error(
            "cannot export: these bundle inputs do not exist:\n  " + "\n  ".join(missing)
        )
    return BundlePlan(copies=copies, empty_dirs=(f"reviews/{reviewer}/cases",))


def export(
    paths: Phase2Paths,
    reviewer: str,
    out: Path,
    *,
    repo_root: Path,
    source_commit: str | None,
    dry_run: bool = False,
    freeze_manifest: bool = True,
    exported_at_utc: str | None = None,
) -> dict[str, Any]:
    """Build the bundle, scan it, and delete it if the scan finds anything.

    Returns the bundle manifest. Raises :class:`Phase2Error` -- after removing
    the partial export -- on any leak.
    """
    from agentfailuretransfer.phase2.freeze import freeze_manifest_sha256
    from agentfailuretransfer.phase2.state import utc_now

    require_reviewer(reviewer)
    out = Path(out).resolve()
    if out.exists():
        raise Phase2Error(f"{out} already exists; choose a fresh --out path")
    for enclosing, what in (
        (Path(repo_root).resolve(), "repository"),
        (paths.root, "Phase 2 tree"),
    ):
        try:
            out.relative_to(enclosing)
        except ValueError:
            continue
        raise Phase2Error(
            f"refusing to export inside the {what} ({out}); a bundle must live "
            "outside it, so a reviewer cannot wander back into the Phase 1 results"
        )

    plan = plan_bundle(paths, reviewer, repo_root=repo_root, freeze_manifest=freeze_manifest)

    out.mkdir(parents=True)
    try:
        for source, relative in plan.copies:
            target = out / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        for relative in plan.empty_dirs:
            (out / relative).mkdir(parents=True, exist_ok=True)
            (out / relative / ".gitkeep").write_text("", encoding="utf-8")

        problems = scan_paths(out, reviewer)
        content = scan_contents(out)
        problems.extend(content.fatal)
        problems.extend(verify_bundle_packets(out))
        if problems:
            raise Phase2Error(
                "the bundle would have leaked and was discarded:\n  "
                + "\n  ".join(problems[:25])
                + (f"\n  ... and {len(problems) - 25} more" if len(problems) > 25 else "")
            )

        exported = sorted(
            path for path in out.rglob("*") if path.is_file() and path.name != "BUNDLE_MANIFEST.json"
        )
        manifest: dict[str, Any] = {
            "bundle_manifest_version": 1,
            "phase": "phase2_odc_control",
            "reviewer": reviewer,
            "dry_run": bool(dry_run),
            "exported_at_utc": exported_at_utc or utc_now(),
            "source_commit": source_commit,
            "freeze_manifest_sha256": freeze_manifest_sha256(paths),
            "snapshot_manifest_sha256": sha256_file(paths.snapshot_manifest),
            "review_manifest_sha256": sha256_file(paths.review_manifest),
            "reviewer_prompt_sha256": sha256_file(paths.reviewer_prompt(reviewer)),
            "excluded_reviewer": other_reviewer(reviewer),
            "library_modules": list(BUNDLE_LIBRARY_MODULES),
            "library_modules_excluded": list(BUNDLE_EXCLUDED_LIBRARY_MODULES),
            "file_count": len(exported),
            "evidence_token_notes": content.notes,
            "evidence_token_note_explanation": (
                "Ordinary programming words found inside the frozen third-party "
                "evidence. Recorded, not removed: the evidence must stay "
                "byte-identical to Phase 1, and every packet file below is "
                "re-hashed against the frozen snapshot manifest."
            ),
            "files": [
                {
                    "path": path.relative_to(out).as_posix(),
                    "sha256": sha256_file(path),
                    "bytes": path.stat().st_size,
                }
                for path in exported
            ],
        }
        if dry_run:
            manifest["dry_run_note"] = (
                "Exported before the Phase 2 protocol freeze (--allow-setup). This "
                "bundle is a tooling rehearsal. It must not be handed to a reviewer "
                "and no review of it is a research result."
            )
        (out / "BUNDLE_MANIFEST.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except BaseException:
        shutil.rmtree(out, ignore_errors=True)
        raise
    return manifest


def audit(bundle_root: Path, reviewer: str) -> list[str]:
    """Re-run every leak check against an already-exported bundle."""
    bundle_root = Path(bundle_root)
    problems = scan_paths(bundle_root, reviewer)
    problems.extend(scan_contents(bundle_root).fatal)
    problems.extend(verify_bundle_packets(bundle_root))
    return problems
