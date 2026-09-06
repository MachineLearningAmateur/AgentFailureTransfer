#!/usr/bin/env python3
"""Phase 2: the ODC external-taxonomy control analysis.

    python scripts/analyze_phase2_odc.py [--check-phase1 | --no-check-phase1]

Runs the analysis pre-registered in
``experiments/phase2_odc_control/protocol/phase2_protocol.md`` sections 9-13
and writes ``experiments/phase2_odc_control/analysis/``.

It refuses, with a ``STOP:`` message and exit 1, unless the Phase 2 workflow
state is ``BOTH_COMPLETE`` or later. The state is computed from the filesystem
by ``agentfailuretransfer.phase2.state`` -- a freeze that verifies, two sealed
reviews, each bound to its own results by hash -- and this script asks that
state machine rather than deciding for itself. Nothing is written when it
refuses.

What it computes
----------------

1. the ODC primary endpoints over all reviewed cases: exact agreement, Cohen's
   kappa, the 9x9 confusion matrix in the frozen label order, taxonomy-fit
   agreement, and the ``UNCLASSIFIABLE`` / ``AMBIGUOUS`` rates per reviewer;
2. the paired McNemar comparison against the Phase 1 broad-family result on the
   same cases, with the fine-label comparison as a secondary;
3. the paired case-level bootstrap of the agreement and kappa differences
   (seed 20260906, 10,000 replicates, undefined kappa replicates counted and
   excluded rather than zeroed);
4. the generation-family breakdown, joined to the hidden crosswalk only after
   ``BOTH_COMPLETE``, and the procedural vs nonprocedural contrast with its
   ``llm + mirror`` sensitivity, under BOTH taxonomies through one code path;
5. the reading of all of that through the pre-registered interpretation matrix,
   under thresholds stated in the output as the rule that was applied.

Phase 1 is an input and never an edit. The sealed Phase 1 labels are read
through the Phase 1 loaders and the frozen family mapping; the frozen Phase 1
aggregate file is opened only to cross-check that the recomputation still
reproduces it (``--check-phase1``, on by default), and none of its recorded
numbers is copied into an emitted artifact.

Determinism: no timestamp is written anywhere. Every random draw is seeded and
every collection is emitted in a declared order, so two runs on unchanged input
produce byte-identical artifacts.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import scipy

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from agentfailuretransfer import paths as repo_paths  # noqa: E402
from agentfailuretransfer.agreement import agreement as agreement_block  # noqa: E402
from agentfailuretransfer.hashing import sha256_file  # noqa: E402
from agentfailuretransfer.phase2 import Phase2Error  # noqa: E402
from agentfailuretransfer.phase2 import analysis  # noqa: E402
from agentfailuretransfer.phase2.packets import (  # noqa: E402
    expected_case_ids as manifest_case_ids,
    study_case_ids,
)
from agentfailuretransfer.phase2.paths import (  # noqa: E402
    REVIEWERS,
    STUDY_CASE_COUNT,
    Phase2Paths,
    resolve_paths,
)
from agentfailuretransfer.phase2.state import (  # noqa: E402
    ANALYZED,
    BOTH_COMPLETE,
    assert_state_at_least,
    compute_state,
)
from agentfailuretransfer.phase2.taxonomy import (  # noqa: E402
    CANONICAL_DEFECT_TYPES,
    DEFECT_TYPES,
    FINGERPRINT_ALGORITHM,
    PATTERN_CONFIDENCES,
    SENTINEL_DEFECT_TYPE,
    TAXONOMY_FITS,
    taxonomy_fingerprint,
)

PHASE1_MODIFIED_SENTENCE = (
    "No Phase 1 reviewer classification was modified during Phase 2."
)

#: Handoff section 29: the sixteen sections the reports must carry.
REPORT_SECTIONS: tuple[tuple[int, str], ...] = (
    (1, "Motivation"),
    (2, "Why ODC was selected"),
    (3, "Exact frozen ODC operationalisation"),
    (4, "Packet and evidence equivalence"),
    (5, "Reviewer blinding"),
    (6, "ODC agreement"),
    (7, "Phase 1 vs ODC paired comparison"),
    (8, "McNemar result"),
    (9, "Paired bootstrap intervals"),
    (10, "ODC confusion matrix"),
    (11, "Generation-family analysis"),
    (12, "Procedural vs nonprocedural analysis"),
    (13, "UNCLASSIFIABLE and AMBIGUOUS analysis"),
    (14, "Limitations"),
    (15, "Interpretation using the decision matrix"),
    (16, "Provenance and hashes"),
)

#: Which report expands which section in full. The other report keeps the
#: heading and a one-line pointer, so both documents carry all sixteen.
AGREEMENT_REPORT_FULL = frozenset({3, 4, 5, 6, 10, 13, 14, 16})
COMPARISON_REPORT_FULL = frozenset({1, 2, 7, 8, 9, 11, 12, 14, 15, 16})

AGREEMENT_REPORT = "odc_agreement.md"
COMPARISON_REPORT = "taxonomy_comparison.md"


# ---------------------------------------------------------------------------
# Provenance, entirely from files
# ---------------------------------------------------------------------------
def read_commit_sha(repo_root: Path) -> str | None:
    """The current commit, read out of ``.git`` rather than shelled out for."""
    git_dir = repo_root / ".git"
    if not git_dir.is_dir():
        return None
    head_file = git_dir / "HEAD"
    if not head_file.is_file():
        return None
    head = head_file.read_text(encoding="utf-8").strip()
    if not head.startswith("ref:"):
        return head or None
    ref = head.split(":", 1)[1].strip()
    direct = git_dir / ref
    if direct.is_file():
        return direct.read_text(encoding="utf-8").strip() or None
    packed = git_dir / "packed-refs"
    if packed.is_file():
        for line in packed.read_text(encoding="utf-8").splitlines():
            if line.startswith("#") or not line.strip():
                continue
            parts = line.split()
            if len(parts) == 2 and parts[1] == ref:
                return parts[0]
    return None


def build_provenance(
    paths: Phase2Paths, inputs: analysis.Phase1Inputs
) -> dict[str, Any]:
    """Commit, freeze, seals, fingerprint and Phase 1 hashes -- all from disk."""
    commit_sha = read_commit_sha(REPO_ROOT)
    provenance: dict[str, Any] = {
        "block_label": (
            "PROVENANCE. Every value below is read from a file at run time; "
            "none is hard-coded. No timestamp is recorded anywhere in these "
            "artifacts: identity is the hashes below, never a clock."
        ),
        "repository_commit_sha": commit_sha or "(unavailable: no .git in this tree)",
        "repository_commit_source": ".git/HEAD, resolved through refs/packed-refs",
        "phase2_root": paths.root.name,
        "freeze_manifest_sha256": (
            sha256_file(paths.freeze_manifest)
            if paths.freeze_manifest.is_file()
            else None
        ),
        "complete_marker_sha256": {
            reviewer: sha256_file(paths.reviewer_complete(reviewer))
            for reviewer in REVIEWERS
            if paths.reviewer_complete(reviewer).is_file()
        },
        "review_results_sha256": {
            reviewer: sha256_file(paths.reviewer_results(reviewer))
            for reviewer in REVIEWERS
            if paths.reviewer_results(reviewer).is_file()
        },
        "taxonomy_fingerprint": taxonomy_fingerprint(paths.taxonomy_yaml, paths.schema),
        "taxonomy_fingerprint_algorithm": FINGERPRINT_ALGORITHM,
        "taxonomy_yaml_sha256": sha256_file(paths.taxonomy_yaml),
        "review_result_schema_sha256": sha256_file(paths.schema),
        "snapshot_manifest_sha256": sha256_file(paths.snapshot_manifest),
        "review_manifest_sha256": (
            sha256_file(paths.review_manifest)
            if paths.review_manifest.is_file()
            else None
        ),
        "phase1_source_sha256": inputs.hashes(),
        "software": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
        "note": (
            "The two source repositories are read-only scientific provenance and "
            "were not modified by this analysis. "
            + PHASE1_MODIFIED_SENTENCE
        ),
    }
    if inputs.source_manifest is not None and Path(inputs.source_manifest).is_file():
        manifest = json.loads(Path(inputs.source_manifest).read_text(encoding="utf-8"))
        provenance["phase1_source_commit_sha"] = manifest.get("commit_sha")
        provenance["phase1_source_repository"] = manifest.get("repository")
    return provenance


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
def fmt_rate(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def fmt_float(value: float | None, places: int = 4) -> str:
    return "n/a" if value is None else f"{value:.{places}f}"


def fmt_signed(value: float | None, places: int = 4) -> str:
    return "n/a" if value is None else f"{value:+.{places}f}"


def fmt_ci(low: float | None, high: float | None, places: int = 4) -> str:
    if low is None or high is None:
        return "n/a"
    return f"[{low:.{places}f}, {high:.{places}f}]"


def fmt_p(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value < 1e-4:
        return "< 0.0001"
    return f"{value:.4f}"


def csv_float(value: float | None, places: int = 10) -> str:
    return "" if value is None else f"{value:.{places}f}"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_lines(path: Path, lines: Sequence[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_csv_rows(path: Path, header: Sequence[str], rows: Sequence[Sequence[str]]) -> None:
    body = [",".join(str(cell) for cell in header)]
    body += [",".join(str(cell) for cell in row) for row in rows]
    write_lines(path, body)


# ---------------------------------------------------------------------------
# Report rendering. Both reports carry all sixteen handoff section 29 sections;
# each expands the ones it owns and points at the other for the rest.
# ---------------------------------------------------------------------------
def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |"]
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return lines


def section_lines(number: int, payload: dict[str, Any], full: bool) -> list[str]:
    odc = payload["odc"]
    phase1 = payload["phase1"]
    other = AGREEMENT_REPORT if number in AGREEMENT_REPORT_FULL else COMPARISON_REPORT

    if not full and number not in (14, 16):
        return [
            f"Reported in full in [`{other}`](./{other}); see also the frozen "
            "protocol in "
            "[`../protocol/phase2_protocol.md`](../protocol/phase2_protocol.md)."
        ]

    if number == 1:
        return [
            f"Phase 1 measured these same {payload['n_cases']} frozen SWE-smith cases with",
            "the frozen AIDev-derived agent-failure taxonomy and found much lower",
            "inter-reviewer",
            "reproducibility than the same instrument achieved on AIDev. That result is",
            "consistent with two explanations it cannot separate: a construct mismatch",
            "between an agent-process taxonomy and static synthetic bugs, or a difficulty",
            "intrinsic to the synthetic bugs themselves. Phase 2 re-measures the identical",
            "cases with an independent, mechanism-neutral defect taxonomy to distinguish",
            "them. Full statement:",
            "[`../protocol/phase2_protocol.md`](../protocol/phase2_protocol.md) section 1.",
            "",
            "The Phase 1 figures this report compares against are **recomputed here from",
            "the sealed per-case Phase 1 labels**, never copied from a previous artifact.",
        ]

    if number == 2:
        return [
            "The Defect Type dimension of IBM's Orthogonal Defect Classification, which",
            "predates LLMs, coding agents, SWE-smith and AIDev, was not derived from this",
            "study, and classifies the semantics of the defect and its correction rather",
            "than an agent's reasoning process. Only the Defect Type dimension is used; no",
            "trigger, activity, impact, source or age attribute is collected. Rationale and",
            "citation:",
            "[`../protocol/external_taxonomy_selection.md`](../protocol/external_taxonomy_selection.md)",
            "and [`../taxonomy/SOURCE_PROVENANCE.md`](../taxonomy/SOURCE_PROVENANCE.md).",
        ]

    if number == 3:
        lines = [
            "The frozen rubric is [`../taxonomy/odc_defect_type_v1.md`](../taxonomy/odc_defect_type_v1.md)",
            "with the machine-readable form beside it. The eight canonical ODC defect types,",
            "in the frozen order, are:",
            "",
        ]
        lines += [f"{index}. `{name}`" for index, name in enumerate(CANONICAL_DEFECT_TYPES, 1)]
        lines += [
            "",
            f"`{SENTINEL_DEFECT_TYPE}` is a **study-level sentinel and is not an ODC defect",
            "type**. It records that none of the eight could be defensibly assigned from the",
            "frozen evidence, and it is data about taxonomy applicability rather than a",
            "reviewer failure. `taxonomy_fit` takes "
            + ", ".join(f"`{fit}`" for fit in TAXONOMY_FITS)
            + ", with the two-way rule",
            f"`{SENTINEL_DEFECT_TYPE}` if and only if `OUT_OF_SCOPE`. `pattern_confidence`",
            "(" + ", ".join(f"`{value}`" for value in PATTERN_CONFIDENCES) + ") is",
            "descriptive only and was not used for inclusion, weighting or any estimate.",
            "",
            "The operational tie-breaking guidance is this study's operationalisation of the",
            "published ODC types, not a modification of ODC, and it was frozen before any",
            "Phase 2 case was seen.",
            "",
            f"Taxonomy fingerprint: `{payload['provenance']['taxonomy_fingerprint']}`",
        ]
        return lines

    if number == 4:
        return [
            "Phase 2 showed the reviewers the same frozen evidence packets Phase 1 showed",
            "them: the same bytes, verified file by file and digest by digest against the",
            "same frozen snapshot manifest. No case was resampled, no bug was rebuilt and no",
            "specification was regenerated.",
            "",
            f"- packets: {payload['n_cases']} (`{payload['case_id_universe']}` corpus)",
            f"- snapshot manifest sha256: `{payload['provenance']['snapshot_manifest_sha256']}`",
            f"- review manifest sha256: `{payload['provenance']['review_manifest_sha256']}`",
            "",
            "Import and verification: [`../data/IMPORT_PROVENANCE.json`](../data/IMPORT_PROVENANCE.json).",
        ]

    if number == 5:
        return [
            "Each reviewer worked in a physically isolated bundle generated outside this",
            "repository from the frozen pre-review commit, containing only the ODC",
            "instructions, the frozen rubric, the schema, the validator, the evidence",
            "packets and its own empty output directory. Phase 1 labels, Phase 1 reports,",
            "generation metadata, the hidden sample mapping, the other reviewer's output and",
            "all AIDev data were physically excluded, and the exporter refuses to publish a",
            "bundle that contains any of them. Reviewer write boundaries are enforced in",
            "code: a reviewer can only write under its own `reviews/<reviewer>/`.",
            "",
            "Details: [`../protocol/blinding_protocol.md`](../protocol/blinding_protocol.md).",
        ]

    if number == 6:
        defect = odc["defect_type"]
        fit = odc["taxonomy_fit"]
        lines = [
            f"Across all {odc['n']} cases, under the ODC Defect Type taxonomy:",
            "",
        ]
        lines += _table(
            ["endpoint", "n", "agreements", "rate", "95% CI", "Cohen's kappa"],
            [
                [
                    "ODC defect type",
                    defect["n"],
                    defect["exact_agreements"],
                    fmt_rate(defect["agreement_rate"]),
                    fmt_ci(*defect["wilson_ci"]),
                    fmt_float(defect["cohens_kappa"]),
                ],
                [
                    "taxonomy_fit",
                    fit["n"],
                    fit["exact_agreements"],
                    fmt_rate(fit["agreement_rate"]),
                    fmt_ci(*fit["wilson_ci"]),
                    fmt_float(fit["cohens_kappa"]),
                ],
            ],
        )
        lines += [
            "",
            "Intervals are Wilson score intervals. Cohen's kappa is this repository's",
            "single unweighted implementation, the same one Phase 1A and Phase 1B use.",
            "",
            "Per-reviewer label distributions over the frozen order:",
            "",
        ]
        lines += _table(
            ["ODC defect type"] + list(REVIEWERS),
            [
                [f"`{label}`"]
                + [
                    odc["per_reviewer"][reviewer]["defect_type_distribution"][label]
                    for reviewer in REVIEWERS
                ]
                for label in DEFECT_TYPES
            ],
        )
        return lines

    if number == 7:
        family = phase1["family"]
        fine = phase1["fine"]
        defect = odc["defect_type"]
        lines = [
            "Both taxonomies were applied to the same cases by the same two reviewer",
            "families, so the comparison is paired and is analysed as such. The Phase 1",
            "values below are recomputed from the sealed Phase 1 per-case labels through the",
            "frozen family mapping.",
            "",
        ]
        lines += _table(
            ["taxonomy / level", "n", "agreements", "rate", "Cohen's kappa"],
            [
                [
                    "Phase 1 AIDev-derived, broad family (primary comparator)",
                    family["n"],
                    family["exact_agreements"],
                    fmt_rate(family["agreement_rate"]),
                    fmt_float(family["cohens_kappa"]),
                ],
                [
                    "Phase 1 AIDev-derived, fine label (secondary)",
                    fine["n"],
                    fine["exact_agreements"],
                    fmt_rate(fine["agreement_rate"]),
                    fmt_float(fine["cohens_kappa"]),
                ],
                [
                    "Phase 2 ODC Defect Type",
                    defect["n"],
                    defect["exact_agreements"],
                    fmt_rate(defect["agreement_rate"]),
                    fmt_float(defect["cohens_kappa"]),
                ],
            ],
        )
        crosscheck = payload["phase1_crosscheck"]
        lines += [
            "",
            "Phase 1 recomputation cross-check: "
            + (
                "the recomputed counts and kappas reproduce the frozen Phase 1 aggregate "
                f"at both levels within a tolerance of {crosscheck['kappa_tolerance']}."
                if crosscheck["agrees"]
                else "MISMATCH -- see the JSON artifact."
            ),
            "The frozen aggregate file is a validation checkpoint only; none of its",
            "recorded numbers is reproduced in this report.",
            "",
            PHASE1_MODIFIED_SENTENCE,
        ]
        return lines

    if number == 8:
        lines: list[str] = []
        for key, title in (
            ("primary_family", "Primary: Phase 1 broad family vs ODC"),
            ("secondary_fine", "Secondary: Phase 1 fine label vs ODC"),
        ):
            test = payload["mcnemar"][key]
            table = test["table"]
            lines += [
                f"**{title}.**",
                "",
            ]
            lines += _table(
                ["", "ODC agree", "ODC disagree"],
                [
                    ["Phase 1 agree", table["a"], table["b"]],
                    ["Phase 1 disagree", table["c"], table["d"]],
                ],
            )
            chi = test["continuity_corrected_chi_square"]
            lines += [
                "",
                f"- Phase 1 agreement rate: {fmt_rate(test['baseline_rate'])}",
                f"- ODC agreement rate: {fmt_rate(test['comparison_rate'])}",
                f"- paired absolute difference: {fmt_signed(test['paired_absolute_difference'])}",
                f"- discordant pairs: b = {table['b']} (Phase 1 only), "
                f"c = {table['c']} (ODC only), total {test['discordant_pairs']}",
                f"- **exact two-sided McNemar p-value: {fmt_p(test['p_value_two_sided'])}** "
                "(binomial test on the discordant pairs; this is the pre-registered result)",
                f"- continuity-corrected chi-square, REFERENCE ONLY: "
                f"chi2 = {fmt_float(chi['statistic'])}, df = 1, "
                f"p = {fmt_p(chi['p_value_two_sided'])}",
                "",
            ]
        lines += [
            "An unpaired test is not used for the taxonomy comparison. Both tests are",
            "exploratory comparisons of two measuring instruments on the same cases; neither",
            "is confirmatory and neither is causal evidence.",
        ]
        return lines

    if number == 9:
        boot = payload["paired_bootstrap"]
        agreement_part = boot["agreement_difference"]
        kappa_part = boot["kappa_difference"]
        lines = [
            f"Seed {boot['seed']}, {boot['replicates']} replicates, "
            f"{boot['ci_method']}.",
            "Case ids are resampled with replacement and all four labels of a case (Phase 1",
            "claude, Phase 1 codex, ODC claude, ODC codex) travel together, so the two",
            "taxonomies are never treated as independent samples.",
            "",
        ]
        lines += _table(
            ["statistic", "point estimate", "95% percentile interval", "replicates used"],
            [
                [
                    "ODC agreement - Phase 1 family agreement",
                    fmt_signed(agreement_part["point_estimate"]),
                    fmt_ci(agreement_part["ci_low"], agreement_part["ci_high"]),
                    agreement_part["valid_replicates"],
                ],
                [
                    "ODC kappa - Phase 1 family kappa",
                    fmt_signed(kappa_part["point_estimate"]),
                    fmt_ci(kappa_part["ci_low"], kappa_part["ci_high"]),
                    kappa_part["valid_replicates"],
                ],
            ],
        )
        lines += [
            "",
            f"Undefined kappa replicates: {kappa_part['undefined_replicates']} "
            f"(Phase 1 side {kappa_part['undefined_replicates_phase1_side']}, "
            f"ODC side {kappa_part['undefined_replicates_odc_side']}). "
            "They are counted and excluded from the interval, never replaced by zero.",
        ]
        gap = payload.get("procedural_gap_bootstrap")
        if gap is None:
            lines += [
                "",
                "The paired bootstrap of the change in the procedural agreement gap was not",
                "computed: see section 12 for the reason.",
            ]
        else:
            lines += [
                "",
                "Change in the procedural agreement gap between taxonomies "
                f"(seed {gap['seed']}, {gap['replicates']} replicates): "
                f"{fmt_signed(gap['point_estimate'])}, "
                f"95% interval {fmt_ci(gap['ci_low'], gap['ci_high'])}, "
                f"{gap['undefined_replicates']} undefined replicate(s) excluded.",
                "Descriptive only; no causal claim follows.",
            ]
        return lines

    if number == 10:
        matrix = odc["confusion_matrix"]
        lines = [
            f"Rows are **{matrix['rows']}**, columns are **{matrix['columns']}**, over the",
            "full frozen label set in the frozen order. The machine-readable copy is",
            "[`odc_confusion.csv`](./odc_confusion.csv).",
            "",
        ]
        header = [f"{matrix['rows']} \\ {matrix['columns']}"] + [
            f"`{label}`" for label in matrix["categories"]
        ]
        rows = [
            [f"`{label}`"] + [str(count) for count in matrix["counts"][index]]
            for index, label in enumerate(matrix["categories"])
        ]
        lines += _table(header, rows)
        lines += [
            "",
            "The diagonal is the exact-agreement count reported in section 6.",
        ]
        return lines

    if number == 11:
        blocks = payload.get("generation_family")
        if not blocks:
            return ["Not computed: no generation crosswalk was available for this root."]
        lines = [
            "The hidden SWE-smith generation crosswalk is joined to the ODC labels **only**",
            "after both reviews are sealed; the join function refuses below `BOTH_COMPLETE`.",
            "The machine-readable copy is",
            "[`generation_method_analysis.csv`](./generation_method_analysis.csv).",
            "",
        ]
        lines += _table(
            ["generation family", "n", "agreements", "rate", "95% CI", "kappa", "note"],
            [
                [
                    f"`{block['generation_family']}`",
                    block["n"],
                    block["exact_agreements"],
                    fmt_rate(block["agreement_rate"]),
                    fmt_ci(*block["wilson_ci"]),
                    fmt_float(block["cohens_kappa_or_none"]),
                    block["note"] or "",
                ]
                for block in blocks
            ],
        )
        lines += [
            "",
            "kappa is reported under the bootstrap degenerate rule: a subgroup whose kappa",
            "is undefined shows `n/a` rather than a manufactured 0.",
            "",
            "Taxonomy-fit distribution and sentinel counts per family and reviewer:",
            "",
        ]
        lines += _table(
            ["generation family", "reviewer"]
            + [f"fit {fit}" for fit in TAXONOMY_FITS]
            + [SENTINEL_DEFECT_TYPE],
            [
                [f"`{block['generation_family']}`", reviewer]
                + [
                    block["per_reviewer"][reviewer]["taxonomy_fit_distribution"][fit]
                    for fit in TAXONOMY_FITS
                ]
                + [block["per_reviewer"][reviewer]["unclassifiable_count"]]
                for block in blocks
                for reviewer in REVIEWERS
            ],
        )
        return lines

    if number == 12:
        contrasts = payload.get("procedural")
        if not contrasts:
            return ["Not computed: no generation crosswalk was available for this root."]
        lines = [
            "The frozen Phase 1B grouping is reused unchanged: `procedural` against",
            "`nonprocedural = llm + mirror + combine`, with `procedural` against",
            "`llm + mirror` as the pre-registered sensitivity. Both taxonomies are put",
            "through the same code path and the same estimators, so the cross-taxonomy",
            "comparison is descriptive rather than a comparison of two methods.",
            "",
        ]
        rows = []
        for entry in contrasts:
            fisher = entry["fisher_exact"]
            rows.append(
                [
                    entry["taxonomy"],
                    entry["comparison"],
                    f"{entry['group_a_agreements']}/{entry['n_group_a']} "
                    f"({fmt_rate(entry['group_a_rate'])})",
                    fmt_ci(*entry["group_a_wilson_ci"]),
                    f"{entry['group_b_agreements']}/{entry['n_group_b']} "
                    f"({fmt_rate(entry['group_b_rate'])})",
                    fmt_ci(*entry["group_b_wilson_ci"]),
                    fmt_signed(entry["gap_group_b_minus_group_a"]),
                    fmt_p(fisher["p_value"]),
                ]
            )
        lines += _table(
            [
                "taxonomy",
                "contrast",
                "procedural",
                "procedural 95% CI",
                "comparator",
                "comparator 95% CI",
                "gap",
                "Fisher p",
            ],
            rows,
        )
        lines += [
            "",
            "Effect sizes with intervals (Newcombe risk difference, Katz risk ratio, Woolf",
            "odds ratio) are in [`taxonomy_comparison.json`](./taxonomy_comparison.json).",
            "The Fisher exact tests are two-sided exploratory association tests on a single",
            "pre-registered contrast, with no multiplicity correction and no causal reading.",
            "",
            "Procedural gap under each taxonomy (nonprocedural rate minus procedural rate):",
            "",
        ]
        gaps = payload["procedural_gaps"]
        lines += _table(
            ["taxonomy", "procedural", "nonprocedural", "gap"],
            [
                [
                    entry["taxonomy"],
                    fmt_rate(entry["procedural_rate"]),
                    fmt_rate(entry["nonprocedural_rate"]),
                    fmt_signed(entry["gap"]),
                ]
                for entry in gaps
            ],
        )
        gap_boot = payload.get("procedural_gap_bootstrap")
        if gap_boot is None:
            lines += [
                "",
                "The paired bootstrap of the change in the gap was omitted: the contrast was",
                "not estimable on this input (one of the groups was empty), and protocol",
                "section 12 says to drop it rather than complicate it.",
            ]
        else:
            lines += [
                "",
                f"Paired bootstrap of the change in the gap: "
                f"{fmt_signed(gap_boot['point_estimate'])}, 95% interval "
                f"{fmt_ci(gap_boot['ci_low'], gap_boot['ci_high'])}.",
            ]
        return lines

    if number == 13:
        lines = [
            f"`{SENTINEL_DEFECT_TYPE}` is a study-level sentinel, not an ODC defect type,",
            "and is not a reviewer failure: it is the measurement of how often none of the",
            "eight canonical types could be defensibly assigned from the frozen evidence.",
            "`AMBIGUOUS` records that more than one type was plausible while a best primary",
            "type was still selected.",
            "",
        ]
        lines += _table(
            [
                "reviewer",
                "n",
                f"{SENTINEL_DEFECT_TYPE}",
                "rate",
                "95% CI",
                "AMBIGUOUS",
                "rate",
                "95% CI",
            ],
            [
                [
                    reviewer,
                    odc["per_reviewer"][reviewer]["n"],
                    odc["per_reviewer"][reviewer]["unclassifiable_count"],
                    fmt_rate(odc["per_reviewer"][reviewer]["unclassifiable_rate"]),
                    fmt_ci(*odc["per_reviewer"][reviewer]["unclassifiable_wilson_ci"]),
                    odc["per_reviewer"][reviewer]["ambiguous_count"],
                    fmt_rate(odc["per_reviewer"][reviewer]["ambiguous_rate"]),
                    fmt_ci(*odc["per_reviewer"][reviewer]["ambiguous_wilson_ci"]),
                ]
                for reviewer in REVIEWERS
            ],
        )
        lines += [
            "",
            "`pattern_confidence` distribution, descriptive only and used for nothing:",
            "",
        ]
        lines += _table(
            ["reviewer"] + list(PATTERN_CONFIDENCES),
            [
                [reviewer]
                + [
                    odc["per_reviewer"][reviewer]["pattern_confidence_distribution"][value]
                    for value in PATTERN_CONFIDENCES
                ]
                for reviewer in REVIEWERS
            ],
        )
        return lines

    if number == 14:
        return [
            "Agreement measures reproducibility between two reviewers applying one scheme.",
            "It does not measure correctness, and no ground truth exists for these cases.",
            "Phase 2 is a measurement control experiment. Regardless of outcome, none of the",
            "following is established:",
            "",
        ] + [
            f"- {item}" for item in payload["interpretation"]["not_established"]
        ] + [
            "",
            "Two reviewer families are not a population of reviewers; one external taxonomy",
            "is not a survey of taxonomies; the exploratory tests here carry no multiplicity",
            "correction; and the `combine` subgroup is too small to interpret. Further",
            "caveats:",
            "[`../../../docs/threats_to_validity.md`](../../../docs/threats_to_validity.md)",
            "and [`../protocol/phase2_protocol.md`](../protocol/phase2_protocol.md) section 14.",
        ]

    if number == 15:
        interpretation = payload["interpretation"]
        lines = [
            "The four outcomes were pre-registered before any Phase 2 case was reviewed, so",
            "that whichever was observed, the reading of it was fixed beforehand. The",
            "thresholds below were stated in advance and are reported here as the rule that",
            "was applied; a reader may disagree with the reading without disagreeing with",
            "any number in this report.",
            "",
            "**Rule applied.**",
            "",
        ]
        lines += [f"- {item}" for item in interpretation["rule_applied"]]
        lines += [
            "",
            "**Observed inputs to the rule.**",
            "",
        ]
        inputs = interpretation["inputs"]
        lines += _table(
            ["quantity", "value"],
            [
                ["Phase 1 family agreement rate", fmt_rate(inputs["phase1_family_agreement_rate"])],
                ["ODC agreement rate", fmt_rate(inputs["odc_agreement_rate"])],
                ["difference d", fmt_signed(inputs["agreement_difference"])],
                [
                    "bootstrap 95% interval for d",
                    fmt_ci(
                        inputs["agreement_difference_ci_low"],
                        inputs["agreement_difference_ci_high"],
                    ),
                ],
                [
                    "interval excludes 0",
                    "yes" if inputs["agreement_difference_ci_excludes_zero"] else "no",
                ],
                ["exact McNemar p", fmt_p(inputs["mcnemar_exact_p_value"])],
                ["Phase 1 procedural gap", fmt_signed(inputs["phase1_procedural_gap"])],
                ["ODC procedural gap", fmt_signed(inputs["odc_procedural_gap"])],
            ],
        )
        lines += [
            "",
            f"**Outcome {interpretation['outcome']}** — {interpretation['outcome_headline']}.",
            "",
            interpretation["conditional_reading"],
            "",
            "The pre-registered reading of this outcome is:",
            "",
            f"> {interpretation['interpretation']}",
            "",
            "On the procedural contrast, the permitted phrasing that applies is:",
            "",
            f"> {interpretation['permitted_procedural_phrasing']}",
            "",
        ]
        if interpretation.get("procedural_phrasing_caveat"):
            lines += [interpretation["procedural_phrasing_caveat"], ""]
        lines += [
            "No other phrasing of the procedural contrast is permitted by the protocol, and",
            "no causal claim is made.",
        ]
        return lines

    if number == 16:
        provenance = payload["provenance"]
        lines = [
            provenance["block_label"],
            "",
        ]
        rows = [
            ["repository commit", f"`{provenance['repository_commit_sha']}`"],
            ["freeze manifest sha256", f"`{provenance['freeze_manifest_sha256']}`"],
            ["taxonomy fingerprint", f"`{provenance['taxonomy_fingerprint']}`"],
            ["fingerprint algorithm", provenance["taxonomy_fingerprint_algorithm"]],
            ["snapshot manifest sha256", f"`{provenance['snapshot_manifest_sha256']}`"],
            ["review-result schema sha256", f"`{provenance['review_result_schema_sha256']}`"],
        ]
        for reviewer in REVIEWERS:
            marker = provenance["complete_marker_sha256"].get(reviewer)
            results = provenance["review_results_sha256"].get(reviewer)
            rows.append([f"{reviewer} COMPLETE marker sha256", f"`{marker}`"])
            rows.append([f"{reviewer} review_results.jsonl sha256", f"`{results}`"])
        for name, digest in provenance["phase1_source_sha256"].items():
            rows.append([f"{name} sha256", f"`{digest}`"])
        if "phase1_source_commit_sha" in provenance:
            rows.append(
                ["Phase 1 source commit", f"`{provenance['phase1_source_commit_sha']}`"]
            )
        lines += _table(["artifact", "value"], rows)
        lines += [
            "",
            f"Software: Python {provenance['software']['python']}, "
            f"numpy {provenance['software']['numpy']}, scipy {provenance['software']['scipy']}.",
            "",
            provenance["note"],
        ]
        return lines

    return ["(no content)"]


def render_report(payload: dict[str, Any], *, title: str, subtitle: str, full: frozenset[int]) -> list[str]:
    lines = [
        f"# {title}",
        "",
        subtitle,
        "",
        PHASE1_MODIFIED_SENTENCE,
        "",
        "No timestamp appears in this report. Identity is the hashes in section 16.",
        "",
    ]
    for number, heading in REPORT_SECTIONS:
        lines.append(f"## {number}. {heading}")
        lines.append("")
        lines.extend(section_lines(number, payload, number in full))
        lines.append("")
    return [line.rstrip() for line in lines]


# ---------------------------------------------------------------------------
# The analysis itself
# ---------------------------------------------------------------------------
def default_phase1_inputs() -> analysis.Phase1Inputs:
    """The repository's frozen Phase 1 artifacts. Defaults, not constants."""
    return analysis.Phase1Inputs(
        codex_results=repo_paths.SWESMITH_CODEX_RESULTS,
        claude_results=repo_paths.SWESMITH_CLAUDE_RESULTS,
        family_mapping=repo_paths.SWESMITH_FAMILY_MAPPING,
        crosswalk=repo_paths.SWESMITH_SAMPLE_METADATA,
        headline_results=repo_paths.TAXONOMY_TRANSFER_DIR / "headline_results.json",
        source_manifest=repo_paths.SWESMITH_MANIFEST,
    )


def build_payload(
    paths: Phase2Paths,
    inputs: analysis.Phase1Inputs,
    *,
    check_phase1: bool,
) -> dict[str, Any]:
    expected = manifest_case_ids(paths)
    universe = "STUDY" if set(expected) == set(study_case_ids()) else "NON_STUDY"
    if universe == "STUDY" and len(expected) != STUDY_CASE_COUNT:
        raise Phase2Error(
            f"the frozen manifest lists {len(expected)} study cases, expected "
            f"{STUDY_CASE_COUNT}"
        )

    reviews = analysis.load_odc_reviews(paths, expected_case_ids=expected)
    case_ids = list(reviews.case_ids)

    labels = analysis.load_phase1_labels(inputs, case_ids)
    crosscheck: dict[str, Any] = {"performed": False}
    if inputs.headline_results is not None:
        crosscheck = analysis.crosscheck_phase1_against_headline(
            labels, inputs.headline_results
        )
        crosscheck["performed"] = True
        if check_phase1 and crosscheck["problems"]:
            raise Phase2Error(
                "the recomputed Phase 1 result does not reproduce the frozen Phase 1 "
                "aggregate:\n  " + "\n  ".join(crosscheck["problems"])
            )

    odc = analysis.odc_endpoints(reviews)
    phase1_blocks = {
        "family": agreement_block(labels.family["claude"], labels.family["codex"]),
        "fine": agreement_block(labels.fine["claude"], labels.fine["codex"]),
    }

    odc_agree = reviews.agree_indicators()
    family_agree = labels.family_agree_indicators()
    fine_agree = labels.fine_agree_indicators()

    mcnemar = {
        "primary_family": analysis.mcnemar_test(
            family_agree,
            odc_agree,
            label="Phase 1 broad-family agreement vs ODC agreement (primary)",
        ),
        "secondary_fine": analysis.mcnemar_test(
            fine_agree,
            odc_agree,
            label="Phase 1 fine-label agreement vs ODC agreement (secondary)",
        ),
    }

    bootstrap = analysis.paired_bootstrap_taxonomy_difference(
        labels.family["claude"],
        labels.family["codex"],
        reviews.defect_types("claude"),
        reviews.defect_types("codex"),
    )

    payload: dict[str, Any] = {
        "generated_by": "scripts/analyze_phase2_odc.py",
        "phase": "phase2_odc_control",
        "n_cases": reviews.n,
        "case_id_universe": universe,
        "case_ids": case_ids,
        "odc": odc,
        "phase1": {
            "family": phase1_blocks["family"],
            "fine": phase1_blocks["fine"],
            "source": (
                "the sealed Phase 1 SWE-smith reviewer labels, mapped through the "
                "frozen family mapping; recomputed here, never copied"
            ),
        },
        "phase1_crosscheck": crosscheck,
        "mcnemar": mcnemar,
        "paired_bootstrap": bootstrap,
        "per_case_indicators": {
            "note": (
                "1 = the two reviewers chose the same label for that case under "
                "that taxonomy. Emitted so the paired table can be rebuilt."
            ),
            "case_ids": case_ids,
            "phase1_family_agree": family_agree,
            "phase1_fine_agree": fine_agree,
            "odc_agree": odc_agree,
        },
    }

    # -- generation families, behind the same BOTH_COMPLETE gate --------------
    families = analysis.load_generation_crosswalk(
        paths, Path(inputs.crosswalk), case_ids=case_ids
    )
    payload["generation_family"] = analysis.generation_family_blocks(reviews, families)

    procedural_ids = [
        case_id for case_id in case_ids if families[case_id] == analysis.PROCEDURAL_FAMILY
    ]
    contrasts: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    definitions = (
        (
            "procedural vs nonprocedural",
            analysis.NONPROCEDURAL_FAMILIES,
            "nonprocedural",
            "method_family in {llm, mirror, combine} (the frozen Phase 1B grouping)",
        ),
        (
            "procedural vs llm+mirror (sensitivity)",
            analysis.LLM_MIRROR_FAMILIES,
            "llm_mirror",
            "method_family in {llm, mirror}; the pre-registered sensitivity contrast",
        ),
    )
    for taxonomy_name, indicators in (
        ("Phase 1 AIDev-derived family", family_agree),
        ("Phase 2 ODC Defect Type", odc_agree),
    ):
        group_a = analysis.group_indicators(
            case_ids, indicators, families, [analysis.PROCEDURAL_FAMILY]
        )
        for comparison, wanted, label, definition in definitions:
            group_b = analysis.group_indicators(case_ids, indicators, families, wanted)
            if not group_a or not group_b:
                continue
            contrasts.append(
                analysis.compare_groups(
                    group_a,
                    group_b,
                    comparison=comparison,
                    group_b_label=label,
                    group_b_definition=definition,
                    taxonomy=taxonomy_name,
                )
            )
        nonprocedural = analysis.group_indicators(
            case_ids, indicators, families, analysis.NONPROCEDURAL_FAMILIES
        )
        gaps.append(
            {
                "taxonomy": taxonomy_name,
                "n_procedural": len(group_a),
                "n_nonprocedural": len(nonprocedural),
                "procedural_rate": (sum(group_a) / len(group_a)) if group_a else None,
                "nonprocedural_rate": (
                    sum(nonprocedural) / len(nonprocedural) if nonprocedural else None
                ),
                "gap": (
                    sum(nonprocedural) / len(nonprocedural) - sum(group_a) / len(group_a)
                    if group_a and nonprocedural
                    else None
                ),
            }
        )
    payload["procedural"] = contrasts
    payload["procedural_gaps"] = gaps
    payload["procedural_grouping"] = {
        "procedural": "method_family == procedural",
        "nonprocedural": "method_family in {llm, mirror, combine}",
        "llm_mirror": "method_family in {llm, mirror}",
        "note": (
            "the frozen Phase 1B grouping, reused unchanged; the same estimators "
            "are applied to both taxonomies through one code path"
        ),
    }

    procedural_flags = [
        int(families[case_id] == analysis.PROCEDURAL_FAMILY) for case_id in case_ids
    ]
    if procedural_ids and len(procedural_ids) < len(case_ids):
        payload["procedural_gap_bootstrap"] = analysis.paired_bootstrap_gap_change(
            procedural_flags, family_agree, odc_agree
        )
    else:
        payload["procedural_gap_bootstrap"] = None

    phase1_gap = next(
        entry["gap"] for entry in gaps if entry["taxonomy"].startswith("Phase 1")
    )
    odc_gap = next(
        entry["gap"] for entry in gaps if entry["taxonomy"].startswith("Phase 2")
    )
    payload["interpretation"] = analysis.interpret_outcome(
        phase1_agreement_rate=phase1_blocks["family"]["agreement_rate"],
        odc_agreement_rate=odc["defect_type"]["agreement_rate"],
        agreement_difference_ci=(
            bootstrap["agreement_difference"]["ci_low"],
            bootstrap["agreement_difference"]["ci_high"],
        ),
        mcnemar_p_value=mcnemar["primary_family"]["p_value_two_sided"],
        phase1_procedural_gap=phase1_gap,
        odc_procedural_gap=odc_gap,
    )

    payload["settings"] = {
        "bootstrap_seed": analysis.SEED,
        "bootstrap_replicates": analysis.BOOTSTRAP_REPLICATES,
        "procedural_gap_bootstrap_seed": list(analysis.GAP_BOOTSTRAP_SEED),
        "confidence": analysis.CONFIDENCE,
        "proportion_ci_method": "Wilson score interval",
        "kappa_ci_method": "percentile bootstrap",
        "mcnemar_method": "exact two-sided binomial on the discordant pairs",
        "mcnemar_reference_method": "continuity-corrected chi-square (reference only)",
        "fisher_alternative": analysis.FISHER_ALTERNATIVE,
        "fisher_implementation": "scipy.stats.fisher_exact",
        "phase1_checkpoint_tolerance": analysis.PHASE1_KAPPA_TOLERANCE,
        "confusion_matrix_orientation": "rows = claude, columns = codex",
        "label_order": list(DEFECT_TYPES),
        "determinism_note": (
            "No timestamp is written. Every collection is emitted in a declared "
            "order and every random draw is seeded, so two runs on unchanged "
            "input produce byte-identical artifacts."
        ),
    }
    payload["provenance"] = build_provenance(paths, inputs)
    return payload


def write_outputs(paths: Phase2Paths, payload: dict[str, Any]) -> list[Path]:
    directory = paths.analysis_dir
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    agreement_payload = {
        key: payload[key]
        for key in (
            "generated_by",
            "phase",
            "n_cases",
            "case_id_universe",
            "case_ids",
            "odc",
            "settings",
            "provenance",
        )
    }
    agreement_payload["phase1_unmodified"] = PHASE1_MODIFIED_SENTENCE
    write_json(directory / "odc_agreement.json", agreement_payload)
    written.append(directory / "odc_agreement.json")

    comparison_payload = {
        key: payload[key]
        for key in (
            "generated_by",
            "phase",
            "n_cases",
            "case_id_universe",
            "phase1",
            "phase1_crosscheck",
            "mcnemar",
            "paired_bootstrap",
            "per_case_indicators",
            "generation_family",
            "procedural",
            "procedural_gaps",
            "procedural_grouping",
            "procedural_gap_bootstrap",
            "interpretation",
            "settings",
            "provenance",
        )
    }
    comparison_payload["odc_headline"] = payload["odc"]["defect_type"]
    comparison_payload["phase1_unmodified"] = PHASE1_MODIFIED_SENTENCE
    write_json(directory / "taxonomy_comparison.json", comparison_payload)
    written.append(directory / "taxonomy_comparison.json")

    matrix = payload["odc"]["confusion_matrix"]
    write_csv_rows(
        directory / "odc_confusion.csv",
        [f"{matrix['rows']}_label"] + [f"{matrix['columns']}_{label}" for label in matrix["categories"]],
        [
            [label] + [str(count) for count in matrix["counts"][index]]
            for index, label in enumerate(matrix["categories"])
        ],
    )
    written.append(directory / "odc_confusion.csv")

    header = [
        "generation_family",
        "n",
        "exact_agreements",
        "agreement_rate",
        "wilson_ci_low",
        "wilson_ci_high",
        "cohens_kappa_or_none",
        "cohens_kappa_defined_rule",
    ]
    for reviewer in REVIEWERS:
        header += [f"{reviewer}_fit_{fit}" for fit in TAXONOMY_FITS]
        header += [f"{reviewer}_{SENTINEL_DEFECT_TYPE.lower()}"]
    header += ["note"]
    rows = []
    for block in payload["generation_family"]:
        row = [
            block["generation_family"],
            str(block["n"]),
            str(block["exact_agreements"]),
            csv_float(block["agreement_rate"]),
            csv_float(block["wilson_ci"][0]),
            csv_float(block["wilson_ci"][1]),
            csv_float(block["cohens_kappa_or_none"]),
            csv_float(block["cohens_kappa_defined_rule"]),
        ]
        for reviewer in REVIEWERS:
            fits = block["per_reviewer"][reviewer]["taxonomy_fit_distribution"]
            row += [str(fits[fit]) for fit in TAXONOMY_FITS]
            row += [str(block["per_reviewer"][reviewer]["unclassifiable_count"])]
        row += [block["note"]]
        rows.append(row)
    write_csv_rows(directory / "generation_method_analysis.csv", header, rows)
    written.append(directory / "generation_method_analysis.csv")

    write_lines(
        directory / AGREEMENT_REPORT,
        render_report(
            payload,
            title="Phase 2 ODC external-taxonomy control — ODC agreement",
            subtitle=(
                "Inter-reviewer agreement on the same frozen SWE-smith cases under the "
                "ODC Defect Type dimension. Sections follow the pre-registered report "
                "outline; sections owned by the companion report link to it."
            ),
            full=AGREEMENT_REPORT_FULL,
        ),
    )
    written.append(directory / AGREEMENT_REPORT)

    write_lines(
        directory / COMPARISON_REPORT,
        render_report(
            payload,
            title="Phase 2 ODC external-taxonomy control — taxonomy comparison",
            subtitle=(
                "The paired comparison of the Phase 1 AIDev-derived taxonomy and the "
                "ODC Defect Type taxonomy on the same frozen SWE-smith cases. Sections "
                "follow the pre-registered report outline; sections owned by the "
                "companion report link to it."
            ),
            full=COMPARISON_REPORT_FULL,
        ),
    )
    written.append(directory / COMPARISON_REPORT)
    return written


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--root", default=None, help="the Phase 2 root to analyse")
    parser.add_argument(
        "--check-phase1",
        dest="check_phase1",
        action="store_true",
        default=True,
        help=(
            "assert the recomputed Phase 1 result reproduces the frozen Phase 1 "
            "aggregate (default)"
        ),
    )
    parser.add_argument(
        "--no-check-phase1",
        dest="check_phase1",
        action="store_false",
        help="skip the Phase 1 recomputation cross-check",
    )
    parser.add_argument("--phase1-codex", default=None)
    parser.add_argument("--phase1-claude", default=None)
    parser.add_argument("--phase1-family-mapping", default=None)
    parser.add_argument("--phase1-crosswalk", default=None)
    parser.add_argument("--phase1-headline-results", default=None)
    parser.add_argument("--phase1-source-manifest", default=None)
    args = parser.parse_args(argv)

    try:
        paths = resolve_paths(args.root, script_file=__file__)
    except Phase2Error as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 1

    try:
        assert_state_at_least(paths, BOTH_COMPLETE)
    except Phase2Error as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        print(
            "\nNothing was written. The Phase 2 comparison is locked until both "
            "reviewers have sealed a review; that lock is the blinding, not a "
            "formality.",
            file=sys.stderr,
        )
        return 1

    defaults = default_phase1_inputs()
    inputs = analysis.Phase1Inputs(
        codex_results=Path(args.phase1_codex or defaults.codex_results),
        claude_results=Path(args.phase1_claude or defaults.claude_results),
        family_mapping=Path(args.phase1_family_mapping or defaults.family_mapping),
        crosswalk=Path(args.phase1_crosswalk or defaults.crosswalk),
        headline_results=(
            Path(args.phase1_headline_results)
            if args.phase1_headline_results
            else defaults.headline_results
        ),
        source_manifest=(
            Path(args.phase1_source_manifest)
            if args.phase1_source_manifest
            else defaults.source_manifest
        ),
    )

    try:
        payload = build_payload(paths, inputs, check_phase1=args.check_phase1)
    except Phase2Error as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 1

    written = write_outputs(paths, payload)

    print(f"Phase 2 ODC analysis over {payload['n_cases']} cases.")
    print(
        f"  ODC agreement      {payload['odc']['defect_type']['exact_agreements']}"
        f"/{payload['n_cases']}"
        f"  kappa {fmt_float(payload['odc']['defect_type']['cohens_kappa'])}"
    )
    print(
        f"  Phase 1 family     {payload['phase1']['family']['exact_agreements']}"
        f"/{payload['n_cases']}"
        f"  kappa {fmt_float(payload['phase1']['family']['cohens_kappa'])}"
    )
    print(
        "  exact McNemar p    "
        f"{fmt_p(payload['mcnemar']['primary_family']['p_value_two_sided'])}"
    )
    print(f"  pre-registered outcome  {payload['interpretation']['outcome']}")
    print()
    for path in written:
        print(f"  wrote {path}")
    print()
    print(f"Phase 2 workflow state is now {compute_state(paths)} (expected {ANALYZED}).")
    print(PHASE1_MODIFIED_SENTENCE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
