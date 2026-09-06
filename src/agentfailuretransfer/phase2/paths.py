"""Where everything lives, in the repository and inside a reviewer bundle.

A Phase 2 *root* is any directory with the frozen evidence and the frozen
rubric directly under it::

    <root>/data/review_snapshot_manifest.json
    <root>/taxonomy/

In the repository that root is ``experiments/phase2_odc_control``. Inside an
exported reviewer bundle it is the bundle directory itself, which carries the
same internal layout minus everything a blinded reviewer must not see. The
tooling therefore never hard-codes the repository root: it is handed a
:class:`Phase2Paths`, or it finds one by walking up from the working directory.

A toy root built in a temporary directory is a Phase 2 root too, which is what
lets the workflow be rehearsed end to end without touching a study case.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentfailuretransfer.phase2 import Phase2Error

#: The two reviewer families, in a fixed order. Directory names only; no claim
#: is made about which model produced a review (the Phase 1 SWE-smith
#: ``review_metadata.json`` did not name one either).
REVIEWERS: tuple[str, ...] = ("claude", "codex")

#: reviewer -> the serialization it writes one case at a time. The semantics
#: are identical; only the bytes on disk differ, so an accidental shared edit
#: between the two reviewers is visible at a glance.
REVIEWER_FORMATS: dict[str, str] = {"claude": "yaml", "codex": "json"}

#: Study case ids: SWESMITH_001 .. SWESMITH_100.
STUDY_CASE_PREFIX = "SWESMITH_"
STUDY_CASE_COUNT = 100

TAXONOMY_YAML_NAME = "odc_defect_type_v1.yaml"
TAXONOMY_MD_NAME = "odc_defect_type_v1.md"
TAXONOMY_PROVENANCE_NAME = "SOURCE_PROVENANCE.md"
SCHEMA_NAME = "odc_review_result.schema.json"
SNAPSHOT_MANIFEST_NAME = "review_snapshot_manifest.json"
REVIEW_MANIFEST_NAME = "review_manifest.csv"
FREEZE_MANIFEST_NAME = "FREEZE_MANIFEST.json"
BUNDLE_MANIFEST_NAME = "BUNDLE_MANIFEST.json"
IMPORT_PROVENANCE_NAME = "IMPORT_PROVENANCE.json"
COMPLETE_NAME = "COMPLETE"


def reviewer_prompt_name(reviewer: str) -> str:
    return f"reviewer_prompt_{reviewer}.md"


def require_reviewer(reviewer: str) -> str:
    if reviewer not in REVIEWERS:
        raise Phase2Error(
            f"unknown reviewer {reviewer!r}; expected one of {list(REVIEWERS)}"
        )
    return reviewer


def other_reviewer(reviewer: str) -> str:
    require_reviewer(reviewer)
    return next(name for name in REVIEWERS if name != reviewer)


@dataclass(frozen=True)
class Phase2Paths:
    """Every path of one Phase 2 root. Purely nominal: nothing is created."""

    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root).resolve())

    # -- frozen inputs -------------------------------------------------
    @property
    def protocol_dir(self) -> Path:
        return self.root / "protocol"

    @property
    def taxonomy_dir(self) -> Path:
        return self.root / "taxonomy"

    @property
    def taxonomy_yaml(self) -> Path:
        return self.taxonomy_dir / TAXONOMY_YAML_NAME

    @property
    def taxonomy_md(self) -> Path:
        return self.taxonomy_dir / TAXONOMY_MD_NAME

    @property
    def taxonomy_provenance(self) -> Path:
        return self.taxonomy_dir / TAXONOMY_PROVENANCE_NAME

    @property
    def schemas_dir(self) -> Path:
        return self.root / "schemas"

    @property
    def schema(self) -> Path:
        return self.schemas_dir / SCHEMA_NAME

    def reviewer_prompt(self, reviewer: str) -> Path:
        return self.protocol_dir / reviewer_prompt_name(require_reviewer(reviewer))

    # -- evidence ------------------------------------------------------
    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def review_packets(self) -> Path:
        return self.data_dir / "review_packets"

    def packet_dir(self, case_id: str) -> Path:
        return self.review_packets / case_id

    @property
    def snapshot_manifest(self) -> Path:
        return self.data_dir / SNAPSHOT_MANIFEST_NAME

    @property
    def review_manifest(self) -> Path:
        return self.data_dir / REVIEW_MANIFEST_NAME

    @property
    def import_provenance(self) -> Path:
        return self.data_dir / IMPORT_PROVENANCE_NAME

    # -- reviewer output ------------------------------------------------
    @property
    def reviews_dir(self) -> Path:
        return self.root / "reviews"

    def reviewer_dir(self, reviewer: str) -> Path:
        return self.reviews_dir / require_reviewer(reviewer)

    def reviewer_cases(self, reviewer: str) -> Path:
        return self.reviewer_dir(reviewer) / "cases"

    def reviewer_case_file(self, reviewer: str, case_id: str) -> Path:
        extension = ".yaml" if REVIEWER_FORMATS[require_reviewer(reviewer)] == "yaml" else ".json"
        return self.reviewer_cases(reviewer) / f"{case_id}{extension}"

    def reviewer_results(self, reviewer: str) -> Path:
        return self.reviewer_dir(reviewer) / "review_results.jsonl"

    def reviewer_metadata(self, reviewer: str) -> Path:
        return self.reviewer_dir(reviewer) / "review_metadata.json"

    def reviewer_complete(self, reviewer: str) -> Path:
        return self.reviewer_dir(reviewer) / COMPLETE_NAME

    def reviewer_progress(self, reviewer: str) -> Path:
        return self.reviewer_dir(reviewer) / "progress.json"

    # -- seals and outputs ----------------------------------------------
    @property
    def freeze_manifest(self) -> Path:
        return self.root / FREEZE_MANIFEST_NAME

    @property
    def bundle_manifest(self) -> Path:
        return self.root / BUNDLE_MANIFEST_NAME

    @property
    def analysis_dir(self) -> Path:
        return self.root / "analysis"

    @property
    def bundles_dir(self) -> Path:
        return self.root / "bundles"

    #: Analysis artifacts whose presence marks the ANALYZED state.
    @property
    def analysis_outputs(self) -> tuple[Path, ...]:
        return (
            self.analysis_dir / "odc_agreement.json",
            self.analysis_dir / "taxonomy_comparison.json",
        )

    @property
    def is_bundle(self) -> bool:
        """True inside an exported reviewer bundle.

        A bundle is identified by its own manifest, written by the exporter.
        Nothing branches on this for *validation*; it only relaxes checks that
        cannot hold in a bundle by construction (the protocol prose and the
        other reviewer's prompt are deliberately absent).
        """
        return self.bundle_manifest.is_file()

    def bundled_reviewer(self) -> str | None:
        """The single reviewer a bundle was exported for, if this is a bundle."""
        present = [name for name in REVIEWERS if self.reviewer_dir(name).exists()]
        return present[0] if len(present) == 1 else None


def is_phase2_root(candidate: Path) -> bool:
    candidate = Path(candidate)
    return (
        (candidate / "data" / SNAPSHOT_MANIFEST_NAME).is_file()
        and (candidate / "taxonomy").is_dir()
    )


def find_root(start: Path | str | None = None) -> Phase2Paths:
    """Walk up from ``start`` to the nearest Phase 2 root.

    This is what makes one validator work unchanged in the repository and
    inside a bundle handed to a reviewer on another machine.
    """
    current = Path(start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if is_phase2_root(candidate):
            return Phase2Paths(candidate)
    raise Phase2Error(
        f"no Phase 2 root at or above {current}: looked for "
        f"data/{SNAPSHOT_MANIFEST_NAME} beside a taxonomy/ directory. Run this "
        "from inside experiments/phase2_odc_control (or from inside a reviewer "
        "bundle), or pass --root."
    )


def repo_paths() -> Phase2Paths | None:
    """The in-repository Phase 2 root, or ``None`` when there is no repository.

    A reviewer bundle ships this module but *not* ``agentfailuretransfer.paths``
    (whose text names Phase 1 artifacts a blinded reviewer must not see), so the
    import is deliberately optional.
    """
    try:
        from agentfailuretransfer import paths as repo_paths_module
    except ImportError:
        return None
    return Phase2Paths(repo_paths_module.PHASE2_DIR)


def resolve_paths(
    root: Path | str | None = None, *, script_file: Path | str | None = None
) -> Phase2Paths:
    """``--root`` if given, else the root this script sits in, else upwards.

    ``script_file`` is ``__file__`` of the calling entry point. It is what makes
    one script work unchanged in both places: in the repository a script lives
    at ``<repo>/scripts/x.py`` and the Phase 2 root is elsewhere, while in a
    bundle it lives at ``<bundle>/scripts/x.py`` and the bundle *is* the root.
    """
    if root is not None:
        candidate = Phase2Paths(root)
        if not is_phase2_root(candidate.root):
            raise Phase2Error(
                f"{candidate.root} is not a Phase 2 root (no "
                f"data/{SNAPSHOT_MANIFEST_NAME} beside a taxonomy/ directory)"
            )
        return candidate
    if script_file is not None:
        beside = Path(script_file).resolve().parent.parent
        if is_phase2_root(beside):
            return Phase2Paths(beside)
    repo = repo_paths()
    if repo is not None and is_phase2_root(repo.root):
        return repo
    return find_root()
