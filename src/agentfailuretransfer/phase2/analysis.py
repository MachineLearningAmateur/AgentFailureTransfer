"""Phase 2 — the pre-registered ODC analysis, as computation only.

This module implements exactly the analysis plan pre-registered in
``experiments/phase2_odc_control/protocol/phase2_protocol.md`` sections 9-13
(handoff sections 21-27). It decides nothing that the protocol did not decide
in advance, and it computes nothing that the protocol did not ask for.

Three properties are deliberate and are asserted by the tests:

**The gate comes first.** Every entry point that touches a sealed ODC review,
and every entry point that touches the hidden generation crosswalk, calls
:func:`agentfailuretransfer.phase2.state.assert_state_at_least` with
``BOTH_COMPLETE`` before it reads anything. The state machine lives in
``state.py`` and is not re-implemented here: this module asks it, and refuses
when it says no. Joining generation metadata to labels is locked behind the
same gate, so a half-finished review cannot be peeked at by family.

**The computations are pure.** Loading is separated from arithmetic. Every
statistic below is a function of plain Python sequences, so a test can hand it
three hand-built cases and check the answer by hand. Nothing computed here
reads a path, a clock, or an environment variable.

**Phase 1 is an input, never an edit.** The sealed Phase 1 SWE-smith labels are
read through the same loaders Phase 1A and Phase 1B use
(:func:`agentfailuretransfer.reviews.load_review_jsonl`,
:func:`agentfailuretransfer.taxonomy.load_family_mapping`), mapped to families
with the same frozen mapping, and compared with the same single unweighted
Cohen's kappa (:mod:`agentfailuretransfer.agreement`). No Phase 1 reviewer
classification is modified, and the Phase 1 aggregate file is read *only* to
cross-check that the recomputation still reproduces it; its recorded numbers are
never copied into an emitted artifact.

Where the paths come from
-------------------------

Every Phase 1 input and the hidden crosswalk are **parameters**
(:class:`Phase1Inputs`), not module constants. The real repository paths appear
only as the defaults of ``scripts/analyze_phase2_odc.py``. That is what lets the
whole analysis be rehearsed against a toy Phase 2 root and a toy label set,
without a study case or a study label being involved.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy import stats as scipy_stats

from agentfailuretransfer.agreement import agreement as agreement_block
from agentfailuretransfer.hashing import sha256_file
from agentfailuretransfer.phase2 import Phase2Error
from agentfailuretransfer.phase2.packets import study_case_ids
from agentfailuretransfer.phase2.paths import REVIEWERS, Phase2Paths
from agentfailuretransfer.phase2.review_records import (
    NON_STUDY_CASE_ID_PATTERN,
    STUDY_CASE_ID_PATTERN,
    duplicate_case_ids,
    validate_record,
)
from agentfailuretransfer.phase2.state import BOTH_COMPLETE, assert_state_at_least
from agentfailuretransfer.phase2.taxonomy import (
    DEFECT_TYPES,
    PATTERN_CONFIDENCES,
    SENTINEL_DEFECT_TYPE,
    TAXONOMY_FITS,
)
from agentfailuretransfer.reviews import load_review_jsonl
from agentfailuretransfer.stats import (
    cohen_kappa_or_none,
    odds_ratio_woolf,
    risk_difference_newcombe,
    risk_ratio_wald,
    wilson_interval,
)
from agentfailuretransfer.taxonomy import UNASSIGNED, family_for, load_family_mapping

# ---------------------------------------------------------------------------
# Pre-registered analysis settings. Frozen in the protocol before any review.
# ---------------------------------------------------------------------------
SEED = 20260906
BOOTSTRAP_REPLICATES = 10000
CONFIDENCE = 0.95
FISHER_ALTERNATIVE = "two-sided"

#: Tolerance for the Phase 1 recomputation cross-check. The exact agreement
#: counts must match exactly; kappa is compared at this tolerance because the
#: frozen file stores it at full precision from the same implementation.
PHASE1_KAPPA_TOLERANCE = 5e-4

#: The confusion matrix is square over the full frozen label set, in the frozen
#: order, rows = claude, columns = codex.
CONFUSION_ROW_REVIEWER = "claude"
CONFUSION_COLUMN_REVIEWER = "codex"

AMBIGUOUS_FIT = "AMBIGUOUS"
OUT_OF_SCOPE_FIT = "OUT_OF_SCOPE"

#: The four SWE-smith generation families, in the order handoff section 24
#: lists them. `combine` has n = 2 and supports no substantive claim.
GENERATION_FAMILY_ORDER: tuple[str, ...] = ("llm", "mirror", "procedural", "combine")
EXPECTED_GENERATION_FAMILIES = frozenset(GENERATION_FAMILY_ORDER)
PROCEDURAL_FAMILY = "procedural"
NONPROCEDURAL_FAMILIES: tuple[str, ...] = ("combine", "llm", "mirror")
LLM_MIRROR_FAMILIES: tuple[str, ...] = ("llm", "mirror")
NO_SUBSTANTIVE_CLAIM_NOTE = (
    "no substantive claim: n = 2 carries no informative agreement estimate"
)

#: Independent bootstrap streams. The primary paired bootstrap uses the bare
#: pre-registered seed; the secondary gap bootstrap uses a distinct stream of
#: the same seed so that neither borrows the other's draws.
GAP_BOOTSTRAP_SEED: tuple[int, int] = (SEED, 2)


# ===========================================================================
# Loading (the only I/O in this module)
# ===========================================================================
@dataclass(frozen=True)
class OdcReviews:
    """Both sealed ODC reviews, case-aligned and label-order fixed."""

    case_ids: tuple[str, ...]
    records: Mapping[str, Mapping[str, Mapping[str, Any]]]

    def values(self, reviewer: str, field_name: str) -> list[str]:
        by_case = self.records[reviewer]
        return [by_case[case_id][field_name] for case_id in self.case_ids]

    def defect_types(self, reviewer: str) -> list[str]:
        return self.values(reviewer, "odc_defect_type")

    def taxonomy_fits(self, reviewer: str) -> list[str]:
        return self.values(reviewer, "taxonomy_fit")

    def confidences(self, reviewer: str) -> list[str]:
        return self.values(reviewer, "pattern_confidence")

    @property
    def n(self) -> int:
        return len(self.case_ids)

    def agree_indicators(self) -> list[int]:
        """1 where the two reviewers chose the same ODC defect type."""
        left = self.defect_types(CONFUSION_ROW_REVIEWER)
        right = self.defect_types(CONFUSION_COLUMN_REVIEWER)
        return [int(a == b) for a, b in zip(left, right)]


@dataclass(frozen=True)
class Phase1Inputs:
    """Where the Phase 1 side of the paired comparison is read from.

    Parameters, never constants: ``scripts/analyze_phase2_odc.py`` fills these
    with the repository's frozen artifacts, and a test fills them with a toy
    label set that has nothing to do with the study.
    """

    codex_results: Path
    claude_results: Path
    family_mapping: Path
    crosswalk: Path
    headline_results: Path | None = None
    source_manifest: Path | None = None

    def hashes(self) -> dict[str, str]:
        """sha256 of every Phase 1 input that exists. Provenance, from files."""
        named = {
            "phase1_codex_review_results": self.codex_results,
            "phase1_claude_review_results": self.claude_results,
            "phase1_family_mapping": self.family_mapping,
            "phase1_generation_crosswalk": self.crosswalk,
            "phase1_headline_results": self.headline_results,
            "phase1_source_manifest": self.source_manifest,
        }
        return {
            name: sha256_file(path)
            for name, path in sorted(named.items())
            if path is not None and Path(path).is_file()
        }


@dataclass(frozen=True)
class Phase1Labels:
    """Per-case Phase 1 labels at both levels, plus the paired indicators."""

    case_ids: tuple[str, ...]
    fine: Mapping[str, list[str]]
    family: Mapping[str, list[str]]

    def family_agree_indicators(self) -> list[int]:
        return [
            int(a == b)
            for a, b in zip(self.family["claude"], self.family["codex"])
        ]

    def fine_agree_indicators(self) -> list[int]:
        return [int(a == b) for a, b in zip(self.fine["claude"], self.fine["codex"])]


def _case_id_pattern_for(case_ids: Sequence[str]) -> str:
    """The study pattern for study ids, the rehearsal pattern otherwise."""
    import re

    if all(re.fullmatch(STUDY_CASE_ID_PATTERN, case_id) for case_id in case_ids):
        return STUDY_CASE_ID_PATTERN
    return NON_STUDY_CASE_ID_PATTERN


def load_odc_reviews(
    paths: Phase2Paths,
    *,
    expected_case_ids: Sequence[str] | None = None,
) -> OdcReviews:
    """Load both sealed ODC reviews. Refuses below ``BOTH_COMPLETE``.

    The gate is the shared state machine, not a local re-implementation: a
    review that is not sealed, or whose sealed JSONL no longer hashes to the
    value its own metadata records, is not ``BOTH_COMPLETE`` and never reaches
    this function's arithmetic.
    """
    assert_state_at_least(paths, BOTH_COMPLETE)

    expected = tuple(expected_case_ids) if expected_case_ids is not None else tuple(
        study_case_ids()
    )
    if not expected:
        raise Phase2Error("expected_case_ids is empty; there is nothing to analyse")
    pattern = _case_id_pattern_for(expected)

    records: dict[str, dict[str, dict[str, Any]]] = {}
    for reviewer in REVIEWERS:
        path = paths.reviewer_results(reviewer)
        rows = load_review_jsonl(path)
        duplicates = duplicate_case_ids(rows)
        if duplicates:
            raise Phase2Error(
                f"{path}: duplicate case_ids in a sealed review: {duplicates}"
            )
        if len(rows) != len(expected):
            raise Phase2Error(
                f"{path}: {len(rows)} sealed records, expected {len(expected)}"
            )
        problems: list[str] = []
        for row in rows:
            problems.extend(
                f"{row.get('case_id', '<no case_id>')}: {problem}"
                for problem in validate_record(
                    row, case_id_pattern=pattern, expected_case_ids=expected
                )
            )
        if problems:
            raise Phase2Error(
                f"{path}: sealed records do not satisfy the frozen record "
                "contract:\n  " + "\n  ".join(problems[:20])
            )
        records[reviewer] = {row["case_id"]: row for row in rows}

    left, right = (set(records[reviewer]) for reviewer in REVIEWERS)
    if left != right:
        raise Phase2Error(
            "the two sealed ODC reviews do not cover the same case ids: "
            f"{REVIEWERS[0]}-only={sorted(left - right)} "
            f"{REVIEWERS[1]}-only={sorted(right - left)}"
        )
    if left != set(expected):
        raise Phase2Error(
            "the sealed ODC reviews do not cover the expected case ids: "
            f"missing={sorted(set(expected) - left)} "
            f"unexpected={sorted(left - set(expected))}"
        )

    return OdcReviews(case_ids=tuple(sorted(expected)), records=records)


def load_phase1_labels(
    inputs: Phase1Inputs, case_ids: Sequence[str]
) -> Phase1Labels:
    """The sealed Phase 1 labels for these cases, fine and mapped to families.

    Read through the Phase 1 loaders and the frozen family mapping, unchanged.
    ``UNASSIGNED`` is refused rather than invented into a family: the SWE-smith
    review schema has no such value, so its presence would mean the input is
    not the corpus this analysis is pairing against.
    """
    mapping = load_family_mapping(inputs.family_mapping)
    wanted = list(case_ids)

    fine: dict[str, list[str]] = {}
    family: dict[str, list[str]] = {}
    for reviewer, path in (
        ("claude", inputs.claude_results),
        ("codex", inputs.codex_results),
    ):
        rows = load_review_jsonl(path)
        duplicates = duplicate_case_ids(rows)
        if duplicates:
            raise Phase2Error(f"{path}: duplicate case_ids: {duplicates}")
        by_case = {row["case_id"]: row for row in rows}
        missing = [case_id for case_id in wanted if case_id not in by_case]
        if missing:
            raise Phase2Error(
                f"{path}: no Phase 1 label for {len(missing)} of the Phase 2 "
                f"cases, e.g. {missing[:5]}"
            )
        labels = [by_case[case_id]["failure_pattern"] for case_id in wanted]
        offenders = [
            case_id
            for case_id, label in zip(wanted, labels)
            if label == UNASSIGNED
        ]
        if offenders:
            raise Phase2Error(
                f"{path}: contains {UNASSIGNED} labels, which the SWE-smith "
                f"review schema forbids: {sorted(offenders)[:5]}"
            )
        fine[reviewer] = labels
        family[reviewer] = [family_for(label, mapping) for label in labels]

    return Phase1Labels(case_ids=tuple(wanted), fine=fine, family=family)


#: The keys read out of the frozen Phase 1 aggregate file. Read, compared, and
#: then discarded: no value from this file is ever emitted.
PHASE1_CHECKPOINT_KEYS: dict[str, tuple[str, ...]] = {
    "family": ("swesmith", "family"),
    "fine": ("swesmith", "fine_grained"),
}


def crosscheck_phase1_against_headline(
    labels: Phase1Labels,
    headline_results: Path,
    *,
    tolerance: float = PHASE1_KAPPA_TOLERANCE,
) -> dict[str, Any]:
    """Cross-check the recomputed Phase 1 result against the frozen aggregate.

    The frozen file is a *checkpoint*, exactly as AGENTS.md requires: its
    numbers are compared against the recomputation and then dropped. Only the
    recomputed values, the key paths that were checked and whether they agreed
    are returned, so no artifact can end up carrying a copied Phase 1 number.
    """
    path = Path(headline_results)
    if not path.is_file():
        raise Phase2Error(f"the frozen Phase 1 aggregate file is missing: {path}")
    recorded = json.loads(path.read_text(encoding="utf-8"))

    checks: list[dict[str, Any]] = []
    problems: list[str] = []
    for level, key_path in PHASE1_CHECKPOINT_KEYS.items():
        left = labels.family if level == "family" else labels.fine
        block = agreement_block(left["claude"], left["codex"])
        node: Any = recorded
        for key in key_path:
            if not isinstance(node, Mapping) or key not in node:
                raise Phase2Error(
                    f"{path}: no key {'.'.join(key_path)} to cross-check against"
                )
            node = node[key]
        agrees_n = int(node["n"]) == block["n"]
        agrees_exact = int(node["exact_agreements"]) == block["exact_agreements"]
        agrees_kappa = (
            abs(float(node["cohens_kappa"]) - block["cohens_kappa"]) <= tolerance
        )
        if not agrees_n:
            problems.append(f"{level}: recomputed n = {block['n']} disagrees")
        if not agrees_exact:
            problems.append(
                f"{level}: recomputed exact agreements = {block['exact_agreements']} "
                "disagrees"
            )
        if not agrees_kappa:
            problems.append(
                f"{level}: recomputed kappa = {block['cohens_kappa']!r} disagrees "
                f"beyond the {tolerance} tolerance"
            )
        checks.append(
            {
                "level": level,
                "checkpoint_key": ".".join(key_path),
                "recomputed_n": block["n"],
                "recomputed_exact_agreements": block["exact_agreements"],
                "recomputed_agreement_rate": block["agreement_rate"],
                "recomputed_cohens_kappa": block["cohens_kappa"],
                "n_agrees": agrees_n,
                "exact_agreements_agree": agrees_exact,
                "kappa_agrees_within_tolerance": agrees_kappa,
            }
        )

    return {
        "checkpoint_file": path.name,
        "checkpoint_file_sha256": sha256_file(path),
        "kappa_tolerance": tolerance,
        "checks": checks,
        "problems": problems,
        "agrees": not problems,
        "note": (
            "The frozen Phase 1 aggregate file is a validation checkpoint only. "
            "Its recorded values are compared against the recomputation and are "
            "not copied into any Phase 2 artifact; every Phase 1 number reported "
            "below is recomputed from the sealed per-case labels."
        ),
    }


def load_generation_crosswalk(
    paths: Phase2Paths,
    crosswalk: Path,
    *,
    case_ids: Sequence[str],
    column: str = "method_family",
) -> dict[str, str]:
    """The hidden generation family per case. Refuses below ``BOTH_COMPLETE``.

    Handoff section 24 and protocol section 12: the generation metadata may be
    joined to ODC labels **only** after both reviews are sealed. That rule is
    enforced here, at the only place in this module that opens the crosswalk,
    so there is no path to a family breakdown that does not pass the gate.
    """
    assert_state_at_least(paths, BOTH_COMPLETE)

    path = Path(crosswalk)
    if not path.is_file():
        raise Phase2Error(f"the hidden generation crosswalk is missing: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or column not in rows[0]:
        raise Phase2Error(f"{path}: no {column!r} column to join on")

    families = {row["case_id"]: row[column] for row in rows}
    wanted = set(case_ids)
    missing = sorted(wanted - set(families))
    if missing:
        raise Phase2Error(
            f"{path}: the crosswalk does not cover {len(missing)} reviewed case "
            f"ids, e.g. {missing[:5]}"
        )
    joined = {case_id: families[case_id] for case_id in case_ids}
    unexpected = sorted(set(joined.values()) - EXPECTED_GENERATION_FAMILIES)
    if unexpected:
        raise Phase2Error(f"{path}: unexpected {column} values: {unexpected}")
    return joined


# ===========================================================================
# Computation. Everything below is a pure function of plain sequences.
# ===========================================================================
def label_distribution(labels: Sequence[str], categories: Sequence[str]) -> dict[str, int]:
    """Counts over the full frozen category list, in the frozen order."""
    counts = {category: 0 for category in categories}
    for label in labels:
        if label not in counts:
            raise ValueError(f"label {label!r} is outside the frozen category list")
        counts[label] += 1
    return counts


def confusion_matrix(
    rows: Sequence[str], columns: Sequence[str], categories: Sequence[str] = DEFECT_TYPES
) -> list[list[int]]:
    """Square confusion counts over ``categories`` in the given order.

    ``rows`` is the row reviewer's label per case and ``columns`` the column
    reviewer's, so ``matrix[i][j]`` counts cases the row reviewer called
    ``categories[i]`` and the column reviewer called ``categories[j]``.
    """
    if len(rows) != len(columns):
        raise ValueError(
            f"label sequences differ in length: {len(rows)} vs {len(columns)}"
        )
    index = {category: position for position, category in enumerate(categories)}
    size = len(categories)
    matrix = [[0] * size for _ in range(size)]
    for row_label, column_label in zip(rows, columns):
        if row_label not in index or column_label not in index:
            raise ValueError(
                f"label pair ({row_label!r}, {column_label!r}) is outside the "
                "frozen category list"
            )
        matrix[index[row_label]][index[column_label]] += 1
    return matrix


def odc_endpoints(reviews: OdcReviews) -> dict[str, Any]:
    """Protocol section 9: every primary endpoint, over all reviewed cases."""
    row_labels = reviews.defect_types(CONFUSION_ROW_REVIEWER)
    column_labels = reviews.defect_types(CONFUSION_COLUMN_REVIEWER)
    defect_block = agreement_block(row_labels, column_labels)
    fit_block = agreement_block(
        reviews.taxonomy_fits(CONFUSION_ROW_REVIEWER),
        reviews.taxonomy_fits(CONFUSION_COLUMN_REVIEWER),
    )
    n = reviews.n

    per_reviewer: dict[str, Any] = {}
    for reviewer in REVIEWERS:
        defects = reviews.defect_types(reviewer)
        fits = reviews.taxonomy_fits(reviewer)
        unclassifiable = sum(1 for label in defects if label == SENTINEL_DEFECT_TYPE)
        ambiguous = sum(1 for fit in fits if fit == AMBIGUOUS_FIT)
        per_reviewer[reviewer] = {
            "n": n,
            "defect_type_distribution": label_distribution(defects, DEFECT_TYPES),
            "taxonomy_fit_distribution": label_distribution(fits, TAXONOMY_FITS),
            "pattern_confidence_distribution": label_distribution(
                reviews.confidences(reviewer), PATTERN_CONFIDENCES
            ),
            "unclassifiable_count": unclassifiable,
            "unclassifiable_rate": (unclassifiable / n) if n else None,
            "unclassifiable_wilson_ci": list(wilson_interval(unclassifiable, n, CONFIDENCE)),
            "ambiguous_count": ambiguous,
            "ambiguous_rate": (ambiguous / n) if n else None,
            "ambiguous_wilson_ci": list(wilson_interval(ambiguous, n, CONFIDENCE)),
        }

    return {
        "n": n,
        "defect_type": {
            **defect_block,
            "cohens_kappa_or_none": cohen_kappa_or_none(row_labels, column_labels),
            "wilson_ci": list(
                wilson_interval(defect_block["exact_agreements"], n, CONFIDENCE)
            ),
            "ci_method": "Wilson score interval (95%)",
        },
        "taxonomy_fit": {
            **fit_block,
            "wilson_ci": list(
                wilson_interval(fit_block["exact_agreements"], n, CONFIDENCE)
            ),
            "ci_method": "Wilson score interval (95%)",
        },
        "per_reviewer": per_reviewer,
        "confusion_matrix": {
            "rows": CONFUSION_ROW_REVIEWER,
            "columns": CONFUSION_COLUMN_REVIEWER,
            "categories": list(DEFECT_TYPES),
            "counts": confusion_matrix(row_labels, column_labels, DEFECT_TYPES),
        },
        "pattern_confidence_note": (
            "pattern_confidence is descriptive only. It was never used for "
            "inclusion, weighting, or any reported estimate."
        ),
        "kappa_note": (
            "Cohen's kappa is this repository's single unweighted implementation "
            "(agentfailuretransfer.agreement.cohen_kappa), the same one Phase 1A "
            "and Phase 1B use. cohens_kappa_or_none is the identical statistic "
            "under the bootstrap degenerate rule and is reported for continuity "
            "with the interval below."
        ),
    }


# ---------------------------------------------------------------------------
# McNemar
# ---------------------------------------------------------------------------
def mcnemar_table(
    baseline: Sequence[int], comparison: Sequence[int]
) -> dict[str, int]:
    """The paired 2x2 table of two binary indicators over the same cases.

    ``baseline`` is the Phase 1 per-case agreement indicator and ``comparison``
    the ODC one, so the cells are, in protocol section 10's layout:

    ``a`` both agree, ``b`` Phase 1 agrees and ODC does not, ``c`` ODC agrees
    and Phase 1 does not, ``d`` neither agrees.
    """
    if len(baseline) != len(comparison):
        raise ValueError(
            f"indicator sequences differ in length: {len(baseline)} vs {len(comparison)}"
        )
    for name, values in (("baseline", baseline), ("comparison", comparison)):
        if any(value not in (0, 1) for value in values):
            raise ValueError(f"{name} must contain only 0/1 indicators")
    a = sum(1 for x, y in zip(baseline, comparison) if x == 1 and y == 1)
    b = sum(1 for x, y in zip(baseline, comparison) if x == 1 and y == 0)
    c = sum(1 for x, y in zip(baseline, comparison) if x == 0 and y == 1)
    d = sum(1 for x, y in zip(baseline, comparison) if x == 0 and y == 0)
    return {"a": a, "b": b, "c": c, "d": d, "n": len(baseline)}


def mcnemar_test(
    baseline: Sequence[int], comparison: Sequence[int], *, label: str = ""
) -> dict[str, Any]:
    """Two-sided exact McNemar, with the corrected chi-square for reference.

    The reported p-value is the **exact** one: a two-sided binomial test on the
    discordant pairs under p = 1/2, via ``scipy.stats.binomtest``. It is exact
    at every discordant count, including the small ones, which is why it is the
    primary. The continuity-corrected chi-square approximation is reported
    beside it, clearly labelled as an approximation and never as the result.
    """
    table = mcnemar_table(baseline, comparison)
    b, c = table["b"], table["c"]
    discordant = b + c

    if discordant == 0:
        exact_p: float | None = 1.0
        exact_note = (
            "no discordant pairs: the two taxonomies agree on the agreement "
            "indicator for every case, so the exact two-sided p-value is 1.0"
        )
    else:
        exact_p = float(
            scipy_stats.binomtest(b, discordant, 0.5, alternative="two-sided").pvalue
        )
        exact_note = (
            "two-sided exact binomial test on the discordant pairs under p = 1/2"
        )

    if discordant == 0:
        chi2_statistic: float | None = None
        chi2_p: float | None = None
    else:
        chi2_statistic = float((abs(b - c) - 1) ** 2 / discordant)
        chi2_p = float(scipy_stats.chi2.sf(chi2_statistic, 1))

    baseline_rate = sum(baseline) / len(baseline) if baseline else None
    comparison_rate = sum(comparison) / len(comparison) if comparison else None

    return {
        "label": label,
        "table": table,
        "table_layout": (
            "rows = Phase 1 agree / Phase 1 disagree; columns = ODC agree / ODC "
            "disagree; a = both agree, b = Phase 1 only, c = ODC only, d = neither"
        ),
        "baseline_agreements": sum(baseline),
        "comparison_agreements": sum(comparison),
        "baseline_rate": baseline_rate,
        "comparison_rate": comparison_rate,
        "paired_absolute_difference": (
            comparison_rate - baseline_rate
            if baseline_rate is not None and comparison_rate is not None
            else None
        ),
        "discordant_pairs": discordant,
        "discordant_b_phase1_only": b,
        "discordant_c_odc_only": c,
        "p_value_two_sided": exact_p,
        "p_value_method": "exact McNemar (scipy.stats.binomtest, two-sided)",
        "p_value_note": exact_note,
        "continuity_corrected_chi_square": {
            "statistic": chi2_statistic,
            "degrees_of_freedom": 1,
            "p_value_two_sided": chi2_p,
            "method": (
                "continuity-corrected McNemar chi-square, (|b - c| - 1)^2 / (b + c)"
            ),
            "status": (
                "REFERENCE ONLY: a large-sample approximation reported alongside "
                "the exact test, which is the pre-registered result"
            ),
        },
        "interpretation": (
            "exploratory paired comparison of two measuring instruments on the "
            "same cases; not causal evidence and not a confirmatory test"
        ),
    }


# ---------------------------------------------------------------------------
# Paired bootstrap
# ---------------------------------------------------------------------------
def _encode(left: Sequence[str], right: Sequence[str]) -> tuple[np.ndarray, np.ndarray, int]:
    labels = sorted(set(left) | set(right))
    codes = {label: index for index, label in enumerate(labels)}
    return (
        np.array([codes[value] for value in left], dtype=np.int64),
        np.array([codes[value] for value in right], dtype=np.int64),
        len(labels),
    )


def _kappa_from_codes(
    left: np.ndarray, right: np.ndarray, n_labels: int
) -> float | None:
    """``stats.cohen_kappa_or_none`` semantics, on integer-coded labels.

    Same rule, same degenerate handling: ``None`` when n is 0 or expected
    agreement is exactly 1.0, never a silent 0.
    """
    n = left.size
    if n == 0:
        return None
    observed = float(np.count_nonzero(left == right)) / n
    left_p = np.bincount(left, minlength=n_labels) / n
    right_p = np.bincount(right, minlength=n_labels) / n
    expected = float(np.dot(left_p, right_p))
    if expected >= 1.0:
        return None
    return (observed - expected) / (1.0 - expected)


def _percentile_interval(
    values: Sequence[float], confidence: float
) -> tuple[float | None, float | None]:
    if not len(values):
        return (None, None)
    array = np.asarray(values, dtype=float)
    lower = 100.0 * (1.0 - confidence) / 2.0
    return (
        float(np.percentile(array, lower)),
        float(np.percentile(array, 100.0 - lower)),
    )


def paired_bootstrap_taxonomy_difference(
    phase1_left: Sequence[str],
    phase1_right: Sequence[str],
    odc_left: Sequence[str],
    odc_right: Sequence[str],
    *,
    seed: int | Sequence[int] = SEED,
    replicates: int = BOOTSTRAP_REPLICATES,
    confidence: float = CONFIDENCE,
) -> dict[str, Any]:
    """Protocol section 11: the paired case-level bootstrap.

    Case ids are resampled with replacement and **all four labels of a case
    travel together**, so the two taxonomies are never treated as independent
    samples. Per replicate the two differences are

    ``ODC agreement - Phase 1 family agreement`` and ``ODC kappa - Phase 1
    family kappa``.

    A replicate whose kappa is undefined on either side (expected agreement
    exactly 1.0, the 0/0 case) is counted and excluded from the kappa interval
    rather than being mapped to zero -- the same rule, for the same reason, as
    ``agentfailuretransfer.stats.bootstrap_kappa``. The agreement difference is
    defined for every replicate, so its interval uses all of them.
    """
    lengths = {len(phase1_left), len(phase1_right), len(odc_left), len(odc_right)}
    if len(lengths) != 1:
        raise ValueError(f"the four label sequences differ in length: {sorted(lengths)}")
    if replicates <= 0:
        raise ValueError("replicates must be positive")
    n = len(phase1_left)

    point_agreement_difference = None
    point_kappa_difference = None
    if n:
        odc_rate = sum(a == b for a, b in zip(odc_left, odc_right)) / n
        phase1_rate = sum(a == b for a, b in zip(phase1_left, phase1_right)) / n
        point_agreement_difference = odc_rate - phase1_rate
        odc_kappa = cohen_kappa_or_none(odc_left, odc_right)
        phase1_kappa = cohen_kappa_or_none(phase1_left, phase1_right)
        if odc_kappa is not None and phase1_kappa is not None:
            point_kappa_difference = odc_kappa - phase1_kappa

    phase1_codes_left, phase1_codes_right, phase1_labels = _encode(
        phase1_left, phase1_right
    )
    odc_codes_left, odc_codes_right, odc_labels = _encode(odc_left, odc_right)
    phase1_match = (phase1_codes_left == phase1_codes_right).astype(np.int64)
    odc_match = (odc_codes_left == odc_codes_right).astype(np.int64)

    agreement_differences: list[float] = []
    kappa_differences: list[float] = []
    undefined_phase1 = 0
    undefined_odc = 0
    undefined_either = 0

    if n:
        rng = np.random.default_rng(seed)
        for _ in range(replicates):
            index = rng.integers(0, n, size=n)
            agreement_differences.append(
                float(odc_match[index].sum() - phase1_match[index].sum()) / n
            )
            phase1_kappa_replicate = _kappa_from_codes(
                phase1_codes_left[index], phase1_codes_right[index], phase1_labels
            )
            odc_kappa_replicate = _kappa_from_codes(
                odc_codes_left[index], odc_codes_right[index], odc_labels
            )
            if phase1_kappa_replicate is None:
                undefined_phase1 += 1
            if odc_kappa_replicate is None:
                undefined_odc += 1
            if phase1_kappa_replicate is None or odc_kappa_replicate is None:
                undefined_either += 1
                continue
            kappa_differences.append(odc_kappa_replicate - phase1_kappa_replicate)
    else:
        undefined_phase1 = undefined_odc = undefined_either = replicates

    agreement_low, agreement_high = _percentile_interval(
        agreement_differences, confidence
    )
    kappa_low, kappa_high = _percentile_interval(kappa_differences, confidence)

    return {
        "n_cases": n,
        "seed": list(seed) if isinstance(seed, (list, tuple)) else seed,
        "replicates": replicates,
        "confidence": confidence,
        "resampling": (
            "case ids resampled with replacement; all four labels of a case "
            "(Phase 1 claude, Phase 1 codex, ODC claude, ODC codex) preserved "
            "together, so the comparison stays paired"
        ),
        "ci_method": f"percentile bootstrap ({confidence:.0%}), 2.5th and 97.5th",
        "agreement_difference": {
            "definition": "ODC exact agreement - Phase 1 family exact agreement",
            "point_estimate": point_agreement_difference,
            "ci_low": agreement_low,
            "ci_high": agreement_high,
            "valid_replicates": len(agreement_differences),
            "bootstrap_mean": (
                float(np.mean(agreement_differences)) if agreement_differences else None
            ),
        },
        "kappa_difference": {
            "definition": "ODC Cohen's kappa - Phase 1 family Cohen's kappa",
            "point_estimate": point_kappa_difference,
            "ci_low": kappa_low,
            "ci_high": kappa_high,
            "valid_replicates": len(kappa_differences),
            "bootstrap_mean": (
                float(np.mean(kappa_differences)) if kappa_differences else None
            ),
            "undefined_replicates": undefined_either,
            "undefined_replicates_phase1_side": undefined_phase1,
            "undefined_replicates_odc_side": undefined_odc,
            "undefined_rule": (
                "a replicate whose kappa is undefined on either side (expected "
                "agreement exactly 1.0) is counted here and excluded from the "
                "interval; it is never replaced by zero"
            ),
        },
    }


def paired_bootstrap_gap_change(
    procedural_flags: Sequence[int],
    phase1_agree: Sequence[int],
    odc_agree: Sequence[int],
    *,
    seed: int | Sequence[int] = GAP_BOOTSTRAP_SEED,
    replicates: int = BOOTSTRAP_REPLICATES,
    confidence: float = CONFIDENCE,
) -> dict[str, Any]:
    """Protocol section 12: the change in the procedural agreement gap.

    The gap under one taxonomy is ``nonprocedural rate - procedural rate``, and
    the statistic is ``ODC gap - Phase 1 gap``. Cases are resampled with
    replacement, keeping each case's group membership and both agreement
    indicators together. A replicate in which either group is empty has no gap;
    it is counted and excluded, never zeroed.

    Deliberately simple. Protocol section 12 says to drop this rather than
    complicate it, so it is one resample of one difference of two differences,
    with no nesting and no stratification.
    """
    lengths = {len(procedural_flags), len(phase1_agree), len(odc_agree)}
    if len(lengths) != 1:
        raise ValueError(f"the three sequences differ in length: {sorted(lengths)}")
    if replicates <= 0:
        raise ValueError("replicates must be positive")

    procedural = np.asarray(procedural_flags, dtype=bool)
    phase1 = np.asarray(phase1_agree, dtype=float)
    odc = np.asarray(odc_agree, dtype=float)
    n = procedural.size

    def gap(values: np.ndarray, mask: np.ndarray) -> float | None:
        if not mask.any() or not (~mask).any():
            return None
        return float(values[~mask].mean() - values[mask].mean())

    phase1_gap = gap(phase1, procedural) if n else None
    odc_gap = gap(odc, procedural) if n else None
    point = (
        odc_gap - phase1_gap
        if phase1_gap is not None and odc_gap is not None
        else None
    )

    differences: list[float] = []
    undefined = 0
    if n:
        rng = np.random.default_rng(seed)
        for _ in range(replicates):
            index = rng.integers(0, n, size=n)
            mask = procedural[index]
            replicate_phase1 = gap(phase1[index], mask)
            replicate_odc = gap(odc[index], mask)
            if replicate_phase1 is None or replicate_odc is None:
                undefined += 1
                continue
            differences.append(replicate_odc - replicate_phase1)
    else:
        undefined = replicates

    low, high = _percentile_interval(differences, confidence)
    return {
        "definition": (
            "(ODC nonprocedural agreement - ODC procedural agreement) minus "
            "(Phase 1 nonprocedural agreement - Phase 1 procedural agreement)"
        ),
        "phase1_gap": phase1_gap,
        "odc_gap": odc_gap,
        "point_estimate": point,
        "ci_low": low,
        "ci_high": high,
        "ci_method": f"percentile bootstrap ({confidence:.0%})",
        "seed": list(seed) if isinstance(seed, (list, tuple)) else seed,
        "replicates": replicates,
        "valid_replicates": len(differences),
        "undefined_replicates": undefined,
        "undefined_rule": (
            "a replicate in which either group is empty has no gap; it is "
            "counted here and excluded from the interval, never zeroed"
        ),
        "interpretation": (
            "descriptive only. A change in a difference of two agreement rates "
            "between two measuring instruments; no causal claim follows"
        ),
    }


# ---------------------------------------------------------------------------
# Group comparisons (the Phase 1B code path, applied to both taxonomies)
# ---------------------------------------------------------------------------
def compare_groups(
    group_a_indicators: Sequence[int],
    group_b_indicators: Sequence[int],
    *,
    comparison: str,
    group_a_label: str = "procedural",
    group_b_label: str = "nonprocedural",
    group_b_definition: str = "",
    taxonomy: str = "",
    confidence: float = CONFIDENCE,
) -> dict[str, Any]:
    """Two group agreement rates, their difference, and the effect sizes.

    Mirrors ``scripts/run_phase1b_robustness.py::compare_groups`` so that the
    Phase 1 side of the cross-taxonomy comparison is recomputed through exactly
    the same estimators as the ODC side: Wilson intervals for the rates, a
    Newcombe hybrid interval for the difference, Katz and Woolf intervals for
    the ratio and the odds ratio, and a two-sided Fisher exact test. The
    exploratory permutation check Phase 1B was separately commissioned to run is
    not part of the Phase 2 pre-registration and is not run here.
    """
    a, n1 = int(sum(group_a_indicators)), len(group_a_indicators)
    c, n2 = int(sum(group_b_indicators)), len(group_b_indicators)
    b, d = n1 - a, n2 - c
    if n1 == 0 or n2 == 0:
        raise ValueError(
            f"{comparison}: both groups must be non-empty (got {n1} and {n2})"
        )

    table = [[a, b], [c, d]]
    fisher = scipy_stats.fisher_exact(table, alternative=FISHER_ALTERNATIVE)

    rate_a = a / n1
    rate_b = c / n2
    return {
        "comparison": comparison,
        "taxonomy": taxonomy,
        "group_a": group_a_label,
        "group_b": group_b_label,
        "group_b_definition": group_b_definition,
        "table_2x2_row_major": table,
        "table": {
            f"{group_a_label}_agree": a,
            f"{group_a_label}_disagree": b,
            f"{group_b_label}_agree": c,
            f"{group_b_label}_disagree": d,
        },
        "n_group_a": n1,
        "n_group_b": n2,
        "group_a_agreements": a,
        "group_b_agreements": c,
        "group_a_rate": rate_a,
        "group_b_rate": rate_b,
        "group_a_wilson_ci": list(wilson_interval(a, n1, confidence)),
        "group_b_wilson_ci": list(wilson_interval(c, n2, confidence)),
        "gap_group_b_minus_group_a": rate_b - rate_a,
        "fisher_exact": {
            "alternative": FISHER_ALTERNATIVE,
            "odds_ratio": float(fisher[0]),
            "p_value": float(fisher[1]),
            "implementation": "scipy.stats.fisher_exact",
            "interpretation": (
                "exploratory association test; not causal evidence and not a "
                "confirmatory hypothesis test"
            ),
        },
        "risk_difference": risk_difference_newcombe(a, n1, c, n2, confidence),
        "risk_ratio": risk_ratio_wald(a, n1, c, n2, confidence),
        "odds_ratio": odds_ratio_woolf(a, b, c, d, confidence),
    }


def generation_family_blocks(
    reviews: OdcReviews, families: Mapping[str, str]
) -> list[dict[str, Any]]:
    """Protocol section 12: the per-family ODC breakdown.

    Reported per family: n, exact agreement, kappa under the bootstrap
    degenerate rule (``None`` rather than a manufactured 0), the taxonomy-fit
    distribution per reviewer, and the ``UNCLASSIFIABLE`` count per reviewer.
    ``combine`` is flagged as supporting no substantive claim.
    """
    grouped: dict[str, list[str]] = {}
    for case_id in reviews.case_ids:
        grouped.setdefault(families[case_id], []).append(case_id)

    ordered = [name for name in GENERATION_FAMILY_ORDER if name in grouped]
    ordered += sorted(name for name in grouped if name not in GENERATION_FAMILY_ORDER)

    position_of = {case_id: index for index, case_id in enumerate(reviews.case_ids)}
    all_defects = {reviewer: reviews.defect_types(reviewer) for reviewer in REVIEWERS}
    all_fits = {reviewer: reviews.taxonomy_fits(reviewer) for reviewer in REVIEWERS}

    blocks: list[dict[str, Any]] = []
    for name in ordered:
        case_ids = grouped[name]
        positions = [position_of[case_id] for case_id in case_ids]
        row = [all_defects[CONFUSION_ROW_REVIEWER][i] for i in positions]
        column = [all_defects[CONFUSION_COLUMN_REVIEWER][i] for i in positions]
        block = agreement_block(row, column)
        n = block["n"]
        per_reviewer = {}
        for reviewer in REVIEWERS:
            defects = [all_defects[reviewer][i] for i in positions]
            fits = [all_fits[reviewer][i] for i in positions]
            per_reviewer[reviewer] = {
                "taxonomy_fit_distribution": label_distribution(fits, TAXONOMY_FITS),
                "unclassifiable_count": sum(
                    1 for label in defects if label == SENTINEL_DEFECT_TYPE
                ),
            }
        blocks.append(
            {
                "generation_family": name,
                "n": n,
                "case_ids": list(case_ids),
                "exact_agreements": block["exact_agreements"],
                "agreement_rate": block["agreement_rate"],
                "wilson_ci": list(
                    wilson_interval(block["exact_agreements"], n, CONFIDENCE)
                ),
                "cohens_kappa_or_none": cohen_kappa_or_none(row, column),
                "cohens_kappa_defined_rule": block["cohens_kappa"],
                "per_reviewer": per_reviewer,
                "note": NO_SUBSTANTIVE_CLAIM_NOTE if name == "combine" else "",
            }
        )
    return blocks


def group_indicators(
    case_ids: Sequence[str],
    indicators: Sequence[int],
    families: Mapping[str, str],
    wanted: Iterable[str],
) -> list[int]:
    """The subset of ``indicators`` whose case belongs to one of ``wanted``."""
    selected = set(wanted)
    return [
        indicator
        for case_id, indicator in zip(case_ids, indicators)
        if families[case_id] in selected
    ]


# ---------------------------------------------------------------------------
# Interpretation
# ---------------------------------------------------------------------------
#: The four pre-registered readings, verbatim from handoff section 27 and
#: protocol section 13. Stored as data so that no report can paraphrase one.
OUTCOME_INTERPRETATIONS: dict[str, str] = {
    "A": (
        "Phase 1's poor transfer was substantially attributable to a construct "
        "mismatch between an agent-process taxonomy and static synthetic bugs."
    ),
    "B": (
        "The agent-process taxonomy contributed to the Phase 1 transfer failure, "
        "but procedural mutations retain an additional classification mismatch "
        "even under an independent defect taxonomy."
    ),
    "C": (
        "Replacing the AIDev-derived taxonomy with an independent generic defect "
        "taxonomy does not resolve the reproducibility problem, which weakens the "
        "explanation that Phase 1 was only a taxonomy-design artifact."
    ),
    "D": (
        "ODC itself may be poorly suited to these modern repair tasks, and no "
        "claim about SWE-smith realism follows without additional controls."
    ),
}

OUTCOME_HEADLINES: dict[str, str] = {
    "A": "ODC agreement much higher; procedural gap narrows substantially",
    "B": "ODC agreement much higher; procedural still much worse than nonprocedural",
    "C": "ODC agreement remains near Phase 1 levels",
    "D": "ODC agreement is worse",
}

#: The two permitted procedural phrasings, verbatim from handoff section 26 and
#: protocol section 12. One of these is returned; nothing else may be said.
PROCEDURAL_PHRASING_PERSISTS = (
    "the procedural subset remained associated with lower reviewer agreement."
)
PROCEDURAL_PHRASING_NARROWED = (
    "the procedural agreement gap substantially narrowed under ODC."
)

#: Pre-stated, deliberately conservative decision thresholds. They are stated
#: in the emitted artifacts as the rule that was applied, so a reader can
#: disagree with the reading without disagreeing with the numbers. Section 13
#: of the protocol says the boundaries are qualitative; these make one
#: qualitative reading explicit and auditable rather than improvised.
INTERPRETATION_THRESHOLDS: dict[str, Any] = {
    "material_increase_in_agreement": 0.15,
    "material_decrease_in_agreement": 0.10,
    "require_bootstrap_ci_to_exclude_zero": True,
    "require_mcnemar_exact_p_below": 0.05,
    "small_procedural_gap": 0.10,
    "gap_narrowed_fraction": 0.5,
}

INTERPRETATION_RULE_TEXT: tuple[str, ...] = (
    "Let d = ODC exact agreement rate - Phase 1 family exact agreement rate, "
    "and let each taxonomy's procedural gap be its nonprocedural agreement rate "
    "minus its procedural agreement rate.",
    "'Much higher' requires ALL THREE of: d >= 0.15; the paired bootstrap 95% "
    "interval for d excluding 0; and the exact two-sided McNemar p-value below "
    "0.05. Any one of them failing is not 'much higher'.",
    "'Worse' requires ALL THREE of: d <= -0.10; the paired bootstrap 95% "
    "interval for d excluding 0; and the exact two-sided McNemar p-value below "
    "0.05.",
    "Anything else is read as 'near Phase 1 levels' (Outcome C). C is the "
    "default: an inconclusive result is never promoted to A, B or D.",
    "Within 'much higher', the procedural gap decides A from B. The gap counts "
    "as substantially narrowed when the ODC gap is below 0.10 AND is at most "
    "half the Phase 1 gap; when the Phase 1 gap was already below 0.10 there is "
    "no substantial gap to narrow, and an ODC gap below 0.10 counts as narrowed. "
    "Otherwise the reading is B.",
    "The same 'substantially narrowed' test selects which of the two permitted "
    "procedural phrasings is used, so the phrasing and the outcome letter can "
    "never disagree with each other.",
    "These thresholds were stated before the data were seen. They encode no "
    "preferred outcome: they are symmetric in form, and the inconclusive "
    "reading is the default in both directions.",
)


def interpret_outcome(
    *,
    phase1_agreement_rate: float,
    odc_agreement_rate: float,
    agreement_difference_ci: tuple[float | None, float | None],
    mcnemar_p_value: float | None,
    phase1_procedural_gap: float | None,
    odc_procedural_gap: float | None,
    thresholds: Mapping[str, Any] = INTERPRETATION_THRESHOLDS,
) -> dict[str, Any]:
    """Map the observed numbers onto the pre-registered outcome matrix.

    Returns the outcome letter, the verbatim pre-registered reading for it, and
    the verbatim permitted procedural phrasing -- plus every input and every
    threshold that produced them, so the reading is reproducible and arguable.
    Nothing here encodes a preferred outcome; the inconclusive reading is the
    default in both directions.
    """
    difference = odc_agreement_rate - phase1_agreement_rate
    ci_low, ci_high = agreement_difference_ci
    ci_excludes_zero = (
        ci_low is not None
        and ci_high is not None
        and (ci_low > 0.0 or ci_high < 0.0)
    )
    p_below = (
        mcnemar_p_value is not None
        and mcnemar_p_value < thresholds["require_mcnemar_exact_p_below"]
    )

    much_higher = (
        difference >= thresholds["material_increase_in_agreement"]
        and (ci_excludes_zero or not thresholds["require_bootstrap_ci_to_exclude_zero"])
        and p_below
    )
    worse = (
        difference <= -thresholds["material_decrease_in_agreement"]
        and (ci_excludes_zero or not thresholds["require_bootstrap_ci_to_exclude_zero"])
        and p_below
    )

    small_gap = thresholds["small_procedural_gap"]
    if phase1_procedural_gap is None or odc_procedural_gap is None:
        narrowed: bool | None = None
        gap_rule = (
            "not evaluable: a procedural gap could not be computed for one of "
            "the taxonomies"
        )
    elif phase1_procedural_gap <= small_gap:
        narrowed = odc_procedural_gap <= small_gap
        gap_rule = (
            f"the Phase 1 procedural gap ({phase1_procedural_gap:.4f}) was already "
            f"at or below {small_gap}, so there was no substantial gap to narrow; "
            f"the ODC gap ({odc_procedural_gap:.4f}) is compared against {small_gap} "
            "alone"
        )
    else:
        narrowed = (
            odc_procedural_gap <= small_gap
            and odc_procedural_gap
            <= thresholds["gap_narrowed_fraction"] * phase1_procedural_gap
        )
        gap_rule = (
            f"the ODC gap ({odc_procedural_gap:.4f}) counts as substantially "
            f"narrowed when it is at or below {small_gap} and at or below "
            f"{thresholds['gap_narrowed_fraction']} x the Phase 1 gap "
            f"({phase1_procedural_gap:.4f})"
        )

    if worse:
        outcome = "D"
    elif much_higher:
        outcome = "A" if narrowed else "B"
    else:
        outcome = "C"

    phrasing = (
        PROCEDURAL_PHRASING_NARROWED if narrowed else PROCEDURAL_PHRASING_PERSISTS
    )
    caveat = ""
    if narrowed and odc_procedural_gap is not None and odc_procedural_gap <= 0.0:
        caveat = (
            "The ODC procedural gap is not positive: the procedural subset did not "
            "show lower agreement than the nonprocedural subset under ODC. Of the two "
            "phrasings the protocol permits, only the one above is defensible here; "
            "it should be read as 'no procedural deficit remained', not as a claim "
            "that a deficit shrank by a measured amount."
        )
    elif (
        narrowed
        and phase1_procedural_gap is not None
        and phase1_procedural_gap <= small_gap
    ):
        caveat = (
            "The Phase 1 procedural gap was already at or below the stated threshold, "
            "so there was little gap to narrow. The phrasing above records that no "
            "substantial procedural deficit is present under ODC, not that a large "
            "one closed."
        )

    return {
        "outcome": outcome,
        "outcome_headline": OUTCOME_HEADLINES[outcome],
        "interpretation": OUTCOME_INTERPRETATIONS[outcome],
        "permitted_procedural_phrasing": phrasing,
        "procedural_phrasing_caveat": caveat,
        "conditional_reading": (
            "Read through the pre-registered interpretation matrix and the "
            f"thresholds stated below, the observed pattern corresponds to "
            f"Outcome {outcome}. The reading is conditional on those thresholds; "
            "the numbers are reported in full regardless of it."
        ),
        "inputs": {
            "phase1_family_agreement_rate": phase1_agreement_rate,
            "odc_agreement_rate": odc_agreement_rate,
            "agreement_difference": difference,
            "agreement_difference_ci_low": ci_low,
            "agreement_difference_ci_high": ci_high,
            "agreement_difference_ci_excludes_zero": ci_excludes_zero,
            "mcnemar_exact_p_value": mcnemar_p_value,
            "mcnemar_p_below_threshold": p_below,
            "phase1_procedural_gap": phase1_procedural_gap,
            "odc_procedural_gap": odc_procedural_gap,
        },
        "tests": {
            "much_higher": much_higher,
            "worse": worse,
            "procedural_gap_substantially_narrowed": narrowed,
        },
        "thresholds": dict(thresholds),
        "rule_applied": list(INTERPRETATION_RULE_TEXT) + [gap_rule],
        "not_established": [
            "that ODC is ground truth",
            "that higher inter-reviewer agreement means greater real-world realism",
            "that SWE-smith is good or bad overall",
            "that procedural mutations cause poor downstream model performance",
            "that ODC categories are the correct training-data distribution",
            "that SWE-smith lacks a particular real-agent failure family",
            "that training utility equals failure realism",
            "that the AIDev taxonomy is invalid for its original purpose",
        ],
    }
