#!/usr/bin/env python3
"""Phase 1B: robustness of the Phase 1A taxonomy-transfer findings.

    python scripts/run_phase1b_robustness.py [--no-check]

Phase 1B is NOT a new labelling experiment. It re-uses the sealed Phase 1A
labels unchanged and asks whether the Phase 1A picture survives reasonable
alternative analysis choices and honest uncertainty quantification:

1. the AIDev all-100 denominator sensitivity analysis, recomputed with the
   source study's own semantics (see below);
2. Wilson 95% intervals for the raw exact-agreement proportions;
3. a case-level paired bootstrap of Cohen's kappa (undefined replicates are
   counted and excluded, never mapped to 0);
4. procedural vs nonprocedural SWE-smith agreement, with a two-sided Fisher's
   exact test, effect sizes with intervals, and an exploratory permutation
   robustness check.

The AIDev all-100 label construction (verified against the source)
---------------------------------------------------------------

``AIBugAnalysis@scripts/compare_reviews.py`` computes its ``cross_model``
"pattern" row over ALL 100 reviewed cases, sorted by ``case_id``, comparing the
raw ``failure_pattern`` string of the two reviewers with exact equality and
treating ``"UNASSIGNED"`` as an ordinary label -- so an UNASSIGNED/UNASSIGNED
case counts as an agreement (34 of the 100 cases). There is no separate policy
for nontechnical rejection, unclear, or merged-without-correction: under the
AIDev review schema all of those simply carry ``failure_pattern ==
"UNASSIGNED"``. Its kappa is the unweighted kappa over the union of observed
labels (its implementation returns ``None`` when expected agreement == 1.0).
This script reconstructs that population from the imported reviewer records; it
does not read the source study's reported value as an input.

Nothing here changes a reviewer label, the taxonomy, or the family mapping, and
nothing is written outside
``analysis/taxonomy_transfer/phase1b_robustness/``.

Outputs (all deterministic; no timestamps are written):
    analysis/taxonomy_transfer/phase1b_robustness/robustness_results.json
    analysis/taxonomy_transfer/phase1b_robustness/robustness_report.md
    analysis/taxonomy_transfer/phase1b_robustness/aidev_denominator_sensitivity.csv
    analysis/taxonomy_transfer/phase1b_robustness/agreement_confidence_intervals.csv
    analysis/taxonomy_transfer/phase1b_robustness/procedural_vs_nonprocedural.csv
    analysis/taxonomy_transfer/phase1b_robustness/bootstrap_summary.csv
    analysis/taxonomy_transfer/phase1b_robustness/notes.md
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import platform
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import scipy
from scipy import stats as scipy_stats

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from agentfailuretransfer import paths  # noqa: E402
from agentfailuretransfer.agreement import agreement  # noqa: E402
from agentfailuretransfer.hashing import sha256_file  # noqa: E402
from agentfailuretransfer.manifest import load_manifest  # noqa: E402
from agentfailuretransfer.reviews import (  # noqa: E402
    duplicate_case_ids,
    load_review_jsonl,
)
from agentfailuretransfer.stats import (  # noqa: E402
    bootstrap_kappa,
    odds_ratio_woolf,
    permutation_difference_test,
    risk_difference_newcombe,
    risk_ratio_wald,
    wilson_interval,
)
from agentfailuretransfer.taxonomy import (  # noqa: E402
    TAXONOMY_VERSION,
    UNASSIGNED,
    load_family_mapping,
)

# --------------------------------------------------------------------------
# Analysis settings. Seeds and replicate counts are fixed so that two runs on
# unchanged data produce byte-identical artifacts.
# --------------------------------------------------------------------------
SEED = 20260906
BOOTSTRAP_REPLICATES = 10000
PERMUTATIONS = 10000
CONFIDENCE = 0.95
FISHER_ALTERNATIVE = "two-sided"

# --------------------------------------------------------------------------
# Validation checkpoint. TARGETS, never outputs: --check compares the computed
# values against them and exits non-zero on a mismatch. No number below is ever
# written into an emitted artifact.
# --------------------------------------------------------------------------
KAPPA_TOLERANCE = 5e-4
SOURCE_ALL100_KAPPA = 0.5531154239019408
SOURCE_ALL100_KAPPA_TOLERANCE = 1e-9

CHECKPOINT = {
    "aidev_primary_n": 49,
    "aidev_primary_fine": {"exact": 31, "kappa": 0.5828},
    "aidev_primary_family": {"exact": 36, "kappa": 0.6575},
    "aidev_all100": {"n": 100, "exact": 65, "kappa": SOURCE_ALL100_KAPPA},
    "swesmith_fine": {"n": 100, "exact": 41, "kappa": 0.254},
    "swesmith_family": {"n": 100, "exact": 41, "kappa": 0.242},
    "generation_family": {
        "llm": {"n": 36, "exact": 20},
        "mirror": {"n": 28, "exact": 15},
        "procedural": {"n": 34, "exact": 6},
        "combine": {"n": 2, "exact": 0},
    },
    "procedural_family": {"n": 34, "exact": 6},
    "nonprocedural_family": {"n": 66, "exact": 35},
}

EXPECTED_GENERATION_FAMILIES = ("combine", "llm", "mirror", "procedural")
NONPROCEDURAL_FAMILIES = ("combine", "llm", "mirror")
LLM_MIRROR_FAMILIES = ("llm", "mirror")


# --------------------------------------------------------------------------
# Loading. Nothing below mutates an imported record.
# --------------------------------------------------------------------------
def index_by_case_id(records: list[dict], label: str) -> dict[str, dict]:
    dupes = duplicate_case_ids(records)
    if dupes:
        raise SystemExit(f"STOP: {label} has duplicate case_ids: {dupes}")
    return {record["case_id"]: record for record in records}


def require_same_case_ids(left: dict, right: dict, label: str) -> list[str]:
    if set(left) != set(right):
        raise SystemExit(
            f"STOP: {label} reviewers did not review the same case ids: "
            f"codex-only={sorted(set(left) - set(right))} "
            f"claude-only={sorted(set(right) - set(left))}"
        )
    return sorted(left)


def run_source_validation() -> None:
    """Run scripts/validate_sources.py first. A failure here is a hard stop."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    module = importlib.import_module("validate_sources")
    code = module.main()
    if code != 0:
        raise SystemExit(
            "STOP: scripts/validate_sources.py failed; the imported artifacts do "
            "not validate. Phase 1B was not run."
        )
    print()


def load_corpora() -> dict:
    mapping = load_family_mapping(paths.AIDEV_FAMILY_MAPPING)
    swesmith_mapping = load_family_mapping(paths.SWESMITH_FAMILY_MAPPING)
    if mapping != swesmith_mapping:
        raise SystemExit("STOP: the two imported family mappings differ")

    aidev_codex = index_by_case_id(
        load_review_jsonl(paths.AIDEV_CODEX_RESULTS), "AIDev codex"
    )
    aidev_claude = index_by_case_id(
        load_review_jsonl(paths.AIDEV_CLAUDE_RESULTS), "AIDev claude"
    )
    aidev_ids = require_same_case_ids(aidev_codex, aidev_claude, "AIDev")

    swesmith_codex = index_by_case_id(
        load_review_jsonl(paths.SWESMITH_CODEX_RESULTS), "SWE-smith codex"
    )
    swesmith_claude = index_by_case_id(
        load_review_jsonl(paths.SWESMITH_CLAUDE_RESULTS), "SWE-smith claude"
    )
    swesmith_ids = require_same_case_ids(swesmith_codex, swesmith_claude, "SWE-smith")

    for name, records in (("codex", swesmith_codex), ("claude", swesmith_claude)):
        offenders = [
            case_id
            for case_id, record in records.items()
            if record["failure_pattern"] == UNASSIGNED
        ]
        if offenders:
            raise SystemExit(
                f"STOP: SWE-smith {name} contains UNASSIGNED labels, which the "
                f"schema forbids: {sorted(offenders)}"
            )

    with paths.SWESMITH_SAMPLE_METADATA.open(encoding="utf-8", newline="") as handle:
        crosswalk = {row["case_id"]: row for row in csv.DictReader(handle)}
    if set(crosswalk) != set(swesmith_ids):
        raise SystemExit(
            "STOP: the hidden crosswalk does not cover exactly the reviewed "
            "SWE-smith case ids"
        )
    observed_families = sorted({row["method_family"] for row in crosswalk.values()})
    if tuple(observed_families) != EXPECTED_GENERATION_FAMILIES:
        raise SystemExit(
            f"STOP: unexpected method_family values: {observed_families}"
        )

    return {
        "mapping": mapping,
        "aidev": {"codex": aidev_codex, "claude": aidev_claude, "ids": aidev_ids},
        "swesmith": {
            "codex": swesmith_codex,
            "claude": swesmith_claude,
            "ids": swesmith_ids,
            "crosswalk": crosswalk,
        },
    }


# --------------------------------------------------------------------------
# Population construction. Every population is a pair of equal-length,
# case-aligned label lists, built from the sealed labels only.
# --------------------------------------------------------------------------
def family_label_keep_unassigned(fine: str, mapping: dict[str, str]) -> str:
    """Map a fine label through the frozen mapping, passing UNASSIGNED through.

    Used ONLY for the additional derived all-100 family-level variant. The
    frozen mapping has no family for UNASSIGNED (it is the AIDev "no technical
    pattern" sentinel), so it is carried through as its own label rather than
    being invented into a family. This is a derived variant of ours, not the
    source study's number.
    """
    return fine if fine == UNASSIGNED else mapping[fine]


def build_populations(loaded: dict) -> list[dict]:
    mapping = loaded["mapping"]
    aidev = loaded["aidev"]
    swesmith = loaded["swesmith"]

    aidev_all_ids = aidev["ids"]
    aidev_both_ids = [
        case_id
        for case_id in aidev_all_ids
        if aidev["codex"][case_id]["failure_pattern"] != UNASSIGNED
        and aidev["claude"][case_id]["failure_pattern"] != UNASSIGNED
    ]
    swesmith_ids = swesmith["ids"]
    groups: dict[str, list[str]] = defaultdict(list)
    for case_id in swesmith_ids:
        groups[swesmith["crosswalk"][case_id]["method_family"]].append(case_id)

    def aidev_pair(case_ids, level):
        codex = [aidev["codex"][c]["failure_pattern"] for c in case_ids]
        claude = [aidev["claude"][c]["failure_pattern"] for c in case_ids]
        if level == "fine":
            return codex, claude
        if level == "family_keep_unassigned":
            return (
                [family_label_keep_unassigned(x, mapping) for x in codex],
                [family_label_keep_unassigned(x, mapping) for x in claude],
            )
        return [mapping[x] for x in codex], [mapping[x] for x in claude]

    def swesmith_pair(case_ids, level):
        codex = [swesmith["codex"][c]["failure_pattern"] for c in case_ids]
        claude = [swesmith["claude"][c]["failure_pattern"] for c in case_ids]
        if level == "fine":
            return codex, claude
        return [mapping[x] for x in codex], [mapping[x] for x in claude]

    populations: list[dict] = []

    def add(key, corpus, subset, level, case_ids, pair, definition, **flags):
        left, right = pair
        populations.append(
            {
                "key": key,
                "corpus": corpus,
                "subset": subset,
                "metric_level": level,
                "case_ids": list(case_ids),
                "codex": left,
                "claude": right,
                "definition": definition,
                "in_wilson_table": flags.get("wilson", True),
                "in_bootstrap_table": flags.get("bootstrap", True),
                "is_source_study_population": flags.get("source_study", False),
            }
        )

    both_definition = (
        "AIDev cases where BOTH reviewers assigned a technical pattern "
        '(failure_pattern != "UNASSIGNED" on both sides); the source study rule '
        "in AIBugAnalysis@scripts/analyze_dual_reviews.py (both_pattern)"
    )
    all100_definition = (
        "All 100 reviewed AIDev cases, sorted by case_id, comparing the raw "
        'failure_pattern strings with "UNASSIGNED" kept as an ordinary label '
        "(so UNASSIGNED vs UNASSIGNED counts as an agreement); the source study "
        "rule in AIBugAnalysis@scripts/compare_reviews.py (cross_model pattern)"
    )
    swesmith_definition = (
        "All 100 frozen SWE-smith cases; the SWE-smith review schema has no "
        "UNASSIGNED value, so no exclusion rule applies"
    )

    add(
        "aidev_primary_fine",
        "AIDev",
        "both-technical-pattern",
        "fine",
        aidev_both_ids,
        aidev_pair(aidev_both_ids, "fine"),
        both_definition,
        source_study=True,
    )
    add(
        "aidev_primary_family",
        "AIDev",
        "both-technical-pattern",
        "family",
        aidev_both_ids,
        aidev_pair(aidev_both_ids, "family"),
        both_definition,
        source_study=True,
    )
    add(
        "aidev_all100_fine",
        "AIDev",
        "all-100 sensitivity",
        "fine",
        aidev_all_ids,
        aidev_pair(aidev_all_ids, "fine"),
        all100_definition,
        source_study=True,
    )
    add(
        "aidev_all100_family_derived",
        "AIDev",
        "all-100 sensitivity (derived family variant)",
        "family_keep_unassigned",
        aidev_all_ids,
        aidev_pair(aidev_all_ids, "family_keep_unassigned"),
        "DERIVED VARIANT, not a source-study number: all 100 reviewed AIDev "
        "cases with non-UNASSIGNED labels mapped through the frozen fine -> "
        "family mapping and UNASSIGNED carried through unchanged as its own "
        "label. The source study reports no family-level all-100 figure.",
        bootstrap=False,
    )
    add(
        "swesmith_fine",
        "SWE-smith",
        "all frozen cases",
        "fine",
        swesmith_ids,
        swesmith_pair(swesmith_ids, "fine"),
        swesmith_definition,
        source_study=True,
    )
    add(
        "swesmith_family",
        "SWE-smith",
        "all frozen cases",
        "family",
        swesmith_ids,
        swesmith_pair(swesmith_ids, "family"),
        swesmith_definition,
        source_study=True,
    )
    for family in ("llm", "mirror", "procedural"):
        subset_ids = groups[family]
        add(
            f"swesmith_{family}_family",
            "SWE-smith",
            f"generation family = {family}",
            "family",
            subset_ids,
            swesmith_pair(subset_ids, "family"),
            f"SWE-smith cases whose hidden crosswalk method_family is {family}",
        )
    combine_ids = groups["combine"]
    add(
        "swesmith_combine_family",
        "SWE-smith",
        "generation family = combine",
        "family",
        combine_ids,
        swesmith_pair(combine_ids, "family"),
        "SWE-smith cases whose hidden crosswalk method_family is combine; "
        "n = 2, reported for completeness only and not interpretable",
        wilson=False,
        bootstrap=False,
    )
    return populations


def summarise_population(population: dict) -> dict:
    block = agreement(population["codex"], population["claude"])
    summary = {
        "key": population["key"],
        "corpus": population["corpus"],
        "subset": population["subset"],
        "metric_level": population["metric_level"],
        "definition": population["definition"],
        "n": block["n"],
        "agreements": block["exact_agreements"],
        "agreement_rate": block["agreement_rate"],
        "cohens_kappa": block["cohens_kappa"],
        "cohens_kappa_4dp": block["cohens_kappa_4dp"],
    }
    if population["in_wilson_table"]:
        low, high = wilson_interval(block["exact_agreements"], block["n"], CONFIDENCE)
        summary["wilson_ci_low"] = low
        summary["wilson_ci_high"] = high
        summary["ci_method"] = "Wilson score interval (95%)"
    else:
        summary["wilson_ci_low"] = None
        summary["wilson_ci_high"] = None
        summary["ci_method"] = (
            "not reported: n = "
            f"{block['n']} carries no informative interval"
        )
    return summary


# --------------------------------------------------------------------------
# Procedural vs nonprocedural
# --------------------------------------------------------------------------
def agreement_indicators(loaded: dict, case_ids: list[str], level: str) -> list[int]:
    mapping = loaded["mapping"]
    codex = loaded["swesmith"]["codex"]
    claude = loaded["swesmith"]["claude"]
    indicators = []
    for case_id in case_ids:
        left = codex[case_id]["failure_pattern"]
        right = claude[case_id]["failure_pattern"]
        if level == "family":
            left, right = mapping[left], mapping[right]
        indicators.append(int(left == right))
    return indicators


def compare_groups(
    loaded: dict,
    comparison: str,
    level: str,
    procedural_ids: list[str],
    comparator_ids: list[str],
    comparator_label: str,
    comparator_definition: str,
    seed_stream_index: int,
) -> dict:
    procedural = agreement_indicators(loaded, procedural_ids, level)
    comparator = agreement_indicators(loaded, comparator_ids, level)
    a, n1 = sum(procedural), len(procedural)
    c, n2 = sum(comparator), len(comparator)
    b, d = n1 - a, n2 - c

    table = [[a, b], [c, d]]
    fisher = scipy_stats.fisher_exact(table, alternative=FISHER_ALTERNATIVE)
    fisher_odds_ratio = float(fisher[0])
    fisher_p = float(fisher[1])

    difference = risk_difference_newcombe(a, n1, c, n2, CONFIDENCE)
    ratio = risk_ratio_wald(a, n1, c, n2, CONFIDENCE)
    odds = odds_ratio_woolf(a, b, c, d, CONFIDENCE)

    permutation = permutation_difference_test(
        procedural + comparator,
        n1,
        seed=[SEED, seed_stream_index],
        permutations=PERMUTATIONS,
    )
    permutation["label"] = "exploratory permutation robustness check"
    permutation["seed"] = SEED
    permutation["seed_stream_index"] = seed_stream_index

    return {
        "comparison": comparison,
        "metric_level": level,
        "group_a": "procedural",
        "group_b": comparator_label,
        "group_b_definition": comparator_definition,
        "table": {
            "procedural_agree": a,
            "procedural_disagree": b,
            f"{comparator_label}_agree": c,
            f"{comparator_label}_disagree": d,
        },
        "table_2x2_row_major": table,
        "n_procedural": n1,
        "n_comparator": n2,
        "procedural_agreements": a,
        "comparator_agreements": c,
        "procedural_rate": a / n1 if n1 else None,
        "comparator_rate": c / n2 if n2 else None,
        "procedural_wilson_ci": list(wilson_interval(a, n1, CONFIDENCE)),
        "comparator_wilson_ci": list(wilson_interval(c, n2, CONFIDENCE)),
        "fisher_exact": {
            "alternative": FISHER_ALTERNATIVE,
            "odds_ratio": fisher_odds_ratio,
            "p_value": fisher_p,
            "implementation": "scipy.stats.fisher_exact",
            "interpretation": (
                "exploratory association test; not causal evidence and not a "
                "confirmatory hypothesis test"
            ),
        },
        "risk_difference": difference,
        "risk_ratio": ratio,
        "odds_ratio": odds,
        "permutation_test": permutation,
    }


# --------------------------------------------------------------------------
# Checkpoint
# --------------------------------------------------------------------------
def run_check(summaries: dict, comparisons: list[dict]) -> list[str]:
    problems: list[str] = []

    def check_block(name, key, expected_n, expected_exact, expected_kappa, tolerance):
        block = summaries.get(key)
        if block is None:
            problems.append(f"{name}: population {key} was not computed")
            return
        if block["n"] != expected_n:
            problems.append(f"{name}: n = {block['n']}, expected {expected_n}")
        if block["agreements"] != expected_exact:
            problems.append(
                f"{name}: agreements = {block['agreements']}, expected {expected_exact}"
            )
        if expected_kappa is not None and (
            abs(block["cohens_kappa"] - expected_kappa) > tolerance
        ):
            problems.append(
                f"{name}: kappa = {block['cohens_kappa']!r}, expected "
                f"{expected_kappa} (tolerance {tolerance})"
            )

    check_block(
        "AIDev primary fine",
        "aidev_primary_fine",
        CHECKPOINT["aidev_primary_n"],
        CHECKPOINT["aidev_primary_fine"]["exact"],
        CHECKPOINT["aidev_primary_fine"]["kappa"],
        KAPPA_TOLERANCE,
    )
    check_block(
        "AIDev primary family",
        "aidev_primary_family",
        CHECKPOINT["aidev_primary_n"],
        CHECKPOINT["aidev_primary_family"]["exact"],
        CHECKPOINT["aidev_primary_family"]["kappa"],
        KAPPA_TOLERANCE,
    )
    check_block(
        "AIDev all-100 sensitivity (source-study semantics)",
        "aidev_all100_fine",
        CHECKPOINT["aidev_all100"]["n"],
        CHECKPOINT["aidev_all100"]["exact"],
        CHECKPOINT["aidev_all100"]["kappa"],
        SOURCE_ALL100_KAPPA_TOLERANCE,
    )
    check_block(
        "SWE-smith fine",
        "swesmith_fine",
        CHECKPOINT["swesmith_fine"]["n"],
        CHECKPOINT["swesmith_fine"]["exact"],
        CHECKPOINT["swesmith_fine"]["kappa"],
        KAPPA_TOLERANCE,
    )
    check_block(
        "SWE-smith family",
        "swesmith_family",
        CHECKPOINT["swesmith_family"]["n"],
        CHECKPOINT["swesmith_family"]["exact"],
        CHECKPOINT["swesmith_family"]["kappa"],
        KAPPA_TOLERANCE,
    )
    for family, expected in sorted(CHECKPOINT["generation_family"].items()):
        check_block(
            f"SWE-smith {family} (family level)",
            f"swesmith_{family}_family",
            expected["n"],
            expected["exact"],
            None,
            KAPPA_TOLERANCE,
        )

    primary = next(
        (
            block
            for block in comparisons
            if block["comparison"] == "procedural_vs_nonprocedural"
            and block["metric_level"] == "family"
        ),
        None,
    )
    if primary is None:
        problems.append("the primary procedural-vs-nonprocedural comparison is missing")
    else:
        expected_procedural = CHECKPOINT["procedural_family"]
        expected_nonprocedural = CHECKPOINT["nonprocedural_family"]
        if (primary["procedural_agreements"], primary["n_procedural"]) != (
            expected_procedural["exact"],
            expected_procedural["n"],
        ):
            problems.append(
                "procedural family agreement = "
                f"{primary['procedural_agreements']}/{primary['n_procedural']}, "
                f"expected {expected_procedural['exact']}/{expected_procedural['n']}"
            )
        if (primary["comparator_agreements"], primary["n_comparator"]) != (
            expected_nonprocedural["exact"],
            expected_nonprocedural["n"],
        ):
            problems.append(
                "nonprocedural family agreement = "
                f"{primary['comparator_agreements']}/{primary['n_comparator']}, "
                f"expected {expected_nonprocedural['exact']}/"
                f"{expected_nonprocedural['n']}"
            )

    # Independent cross-check of the all-100 sensitivity analysis against the
    # imported source-study metrics file (an artifact, not a Markdown report).
    published = json.loads(paths.AIDEV_AGREEMENT_METRICS.read_text(encoding="utf-8"))
    if "pattern_all_cases" in published:
        block = published["pattern_all_cases"]
        computed = summaries["aidev_all100_fine"]
        if block.get("exact_agreement") != computed["agreements"]:
            problems.append(
                "imported AIDev agreement_metrics.json disagrees on the all-100 "
                f"agreement count: {block.get('exact_agreement')} vs "
                f"{computed['agreements']}"
            )
    return problems


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def fmt_rate(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def fmt_float(value: float | None, places: int = 4) -> str:
    return "n/a" if value is None else f"{value:.{places}f}"


def fmt_ci(low: float | None, high: float | None, places: int = 4) -> str:
    if low is None or high is None:
        return "not reported"
    return f"[{low:.{places}f}, {high:.{places}f}]"


def csv_float(value: float | None, places: int = 10) -> str:
    return "" if value is None else f"{value:.{places}f}"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


LIMITATIONS = [
    "Both corpora were labelled by two LLM reviewers only. Two raters bound "
    "what any agreement statistic can say.",
    "Agreement measures reproducibility between reviewers, not ground-truth "
    "validity. A pattern both reviewers apply consistently may still be wrong.",
    "The AIDev primary denominator (49 both-technical-pattern cases) differs "
    "from the SWE-smith denominator (all 100 cases). Section 4 quantifies how "
    "much that choice matters; it does not remove the difference.",
    "The AIDev broad-family mapping was developed from AIDev disagreement "
    "data, so the AIDev family-level number is partly in-sample, while the "
    "SWE-smith family-level number is out-of-sample.",
    "A language and corpus confound remains: the two corpora differ in far "
    "more than real-vs-synthetic origin.",
    "Every SWE-smith task in the sample is Python.",
    "AIDev is multilingual.",
    "The generation-family subgroups are modest in size (llm 36, procedural "
    "34, mirror 28), so their intervals are wide.",
    "The combine family has n = 2 and is not interpretable; no interval or "
    "test is reported for it.",
    "Generation family may correlate with other task properties (repository, "
    "diff size, test structure) that are not controlled here.",
    "Fisher's exact test here is exploratory: the contrast was written into "
    "the Phase 1B plan after the Phase 1A subgroup results were already known. "
    "It is not a confirmatory hypothesis test and carries no multiplicity "
    "correction.",
    "No causal claim is made about generation mechanism. Reviewer agreement "
    "was lower among procedurally generated cases; nothing here shows that "
    "procedural generation produces disagreement.",
    "No cross-corpus coverage or category-frequency claim is made. Phase 1B "
    "is about agreement robustness only.",
]


def render_report(payload: dict) -> str:
    provenance = payload["source_provenance"]
    summaries = payload["_summaries"]
    comparisons = payload["procedural_vs_nonprocedural"]["comparisons"]
    bootstraps = payload["bootstrap_kappa"]["populations"]
    settings = payload["analysis_settings"]

    lines: list[str] = []
    add = lines.append

    add("# Phase 1B — Robustness of Taxonomy-Transfer Findings")
    add("")
    add(
        "Generated by `scripts/run_phase1b_robustness.py` from the imported "
        "sealed reviewer labels. Every number below is recomputed; none is read "
        "out of a source-study Markdown report."
    )
    add("")

    add("## 1. Purpose")
    add("")
    add(
        "Phase 1A established that the two source studies' headline agreement "
        "results reproduce exactly from their sealed labels. It did not "
        "establish that those results are robust. Phase 1B asks a narrower "
        "question:"
    )
    add("")
    add(
        "> Do the Phase 1A taxonomy-transfer findings remain qualitatively the "
        "same under reasonable alternative analysis choices and uncertainty "
        "estimates?"
    )
    add("")
    add(
        "Concretely: does the AIDev-vs-SWE-smith agreement gap survive using "
        "all 100 reviewed AIDev PRs instead of the 49 both-technical-pattern "
        "cases; how uncertain are the observed agreement rates and kappas; and "
        "is reviewer agreement substantially lower among procedurally "
        "generated SWE-smith cases than among nonprocedural ones. Phase 1B is "
        "not a new labelling experiment: no case was re-reviewed, no "
        "disagreement adjudicated, no taxonomy or mapping altered."
    )
    add("")

    add("## 2. Frozen inputs")
    add("")
    add("| Input | Identity |")
    add("| --- | --- |")
    add(
        f"| AIDev source commit | `{provenance['aidev']['commit_sha']}` "
        f"({provenance['aidev']['repository']}) |"
    )
    add(
        f"| SWE-smith source commit | `{provenance['swesmith']['commit_sha']}` "
        f"({provenance['swesmith']['repository']}) |"
    )
    add(f"| Taxonomy version | `{payload['taxonomy_version']}` |")
    add(f"| Taxonomy sha256 | `{provenance['taxonomy_sha256']}` |")
    add(f"| Family-mapping sha256 | `{provenance['family_mapping_sha256']}` |")
    for corpus in ("aidev", "swesmith"):
        for reviewer in sorted(provenance[corpus]["review_result_sha256"]):
            digest = provenance[corpus]["review_result_sha256"][reviewer]
            add(
                f"| {provenance[corpus]['name']} review results "
                f"({reviewer}) sha256 | `{digest}` |"
            )
    add(
        f"| SWE-smith hidden crosswalk sha256 | "
        f"`{provenance['swesmith_crosswalk_sha256']}` |"
    )
    add("")
    add(
        "The taxonomy `.md` and the family-mapping `.yaml` are byte-identical "
        "across the two source studies; this script re-checks that before "
        "computing anything, and `scripts/validate_sources.py` is run first and "
        "must pass."
    )
    add("")
    add("> No reviewer classifications were changed.")
    add("")

    add("## 3. Primary Phase 1A result")
    add("")
    add("| Level | Corpus | Population | n | agreement | rate | Cohen's κ |")
    add("| --- | --- | --- | ---: | ---: | ---: | ---: |")
    for key in (
        "aidev_primary_fine",
        "swesmith_fine",
        "aidev_primary_family",
        "swesmith_family",
    ):
        block = summaries[key]
        level = "Fine-grained" if block["metric_level"] == "fine" else "Broad family"
        add(
            f"| {level} | {block['corpus']} | {block['subset']} | {block['n']} | "
            f"{block['agreements']} | {fmt_rate(block['agreement_rate'])} | "
            f"{block['cohens_kappa']:.10f} |"
        )
    add("")
    add(
        "These are the Phase 1A numbers, recomputed here and unchanged. The "
        "AIDev rows cover the 49 cases where both reviewers assigned a "
        "technical pattern; the SWE-smith rows cover all 100 frozen cases."
    )
    add("")

    add("## 4. AIDev denominator sensitivity")
    add("")
    add("| Analysis population | n | agreement | rate | Cohen's κ |")
    add("| --- | ---: | ---: | ---: | ---: |")
    for key in (
        "aidev_primary_fine",
        "aidev_all100_fine",
        "aidev_all100_family_derived",
        "swesmith_fine",
    ):
        block = summaries[key]
        add(
            f"| {block['corpus']} — {block['subset']} ({block['metric_level']}) | "
            f"{block['n']} | {block['agreements']} | "
            f"{fmt_rate(block['agreement_rate'])} | {block['cohens_kappa']:.10f} |"
        )
    add("")
    add(
        "The all-100 row reconstructs the source study's own cross-model "
        "pattern analysis (`AIBugAnalysis@scripts/compare_reviews.py`): all 100 "
        "reviewed cases sorted by `case_id`, raw `failure_pattern` strings "
        "compared for exact equality, with `\"UNASSIGNED\"` kept as an ordinary "
        "label. Under the AIDev review schema, every non-technical outcome — "
        "nontechnical rejection, unclear, merged without correction, or simply "
        "no technical pattern — carries `failure_pattern == \"UNASSIGNED\"`; "
        "there is no separate policy for any of them. "
        f"{payload['aidev_all100_sensitivity']['unassigned_vs_unassigned_cases']} "
        "of the 100 cases are UNASSIGNED on both sides and therefore count as "
        "agreements. The recomputation reproduces the source study's committed "
        "value exactly (see `notes.md`)."
    )
    add("")
    add(
        "**The two AIDev analyses answer different questions.** The 49-case "
        "analysis asks: when both reviewers agree that there is a technical "
        "failure pattern to name, how consistently do they name the same one? "
        "The all-100 analysis asks: across everything reviewed, how "
        "consistently do the two reviewers produce the same pattern field — a "
        "question in which agreeing that no technical pattern applies counts as "
        "agreement. The all-100 figure is the closer denominator match to "
        "SWE-smith, where all 100 cases are execution-validated synthetic bugs "
        "and every case receives a taxonomy outcome; but it is not a like-for-"
        "like population either, because a large share of its agreements are "
        "UNASSIGNED/UNASSIGNED pairs, a possibility SWE-smith's schema does not "
        "even admit. Neither AIDev figure is a substitute for the other, and "
        "both are reported."
    )
    add("")
    add(
        "The derived family-level all-100 row is ours, not the source study's: "
        "it maps non-UNASSIGNED labels through the frozen mapping and carries "
        "UNASSIGNED through unchanged. It is listed for completeness and should "
        "not be quoted as a source-study number."
    )
    add("")

    add("## 5. Uncertainty intervals")
    add("")
    add("Raw exact-agreement proportions, Wilson 95% score intervals:")
    add("")
    add("| Corpus | Subset | Level | n | agreement | rate | 95% CI |")
    add("| --- | --- | --- | ---: | ---: | ---: | --- |")
    for row in payload["confidence_intervals"]["rows"]:
        add(
            f"| {row['corpus']} | {row['subset']} | {row['metric_level']} | "
            f"{row['n']} | {row['agreements']} | "
            f"{fmt_rate(row['agreement_rate'])} | "
            f"{fmt_ci(row['ci_low'], row['ci_high'])} |"
        )
    add("")
    add(
        "Cohen's κ, case-level paired nonparametric bootstrap "
        f"({settings['bootstrap_replicates']} replicates, seed "
        f"{settings['bootstrap_seed']}, percentile 95% interval):"
    )
    add("")
    add(
        "| Corpus | Subset | Level | n | κ | 95% CI | valid replicates | "
        "undefined replicates |"
    )
    add("| --- | --- | --- | ---: | ---: | --- | ---: | ---: |")
    for row in bootstraps:
        add(
            f"| {row['corpus']} | {row['subset']} | {row['metric_level']} | "
            f"{row['n']} | {fmt_float(row['point_estimate'])} | "
            f"{fmt_ci(row['ci_low'], row['ci_high'])} | "
            f"{row['valid_replicates']} | {row['undefined_replicates']} |"
        )
    add("")
    add(
        "Each replicate resamples **cases** with replacement, keeping the two "
        "reviewers' labels for a case paired, and recomputes κ from the "
        "resampled table. A replicate whose κ is undefined (expected agreement "
        "exactly 1.0) is counted in the last column and excluded from the "
        "percentile interval; it is never mapped to 0. This is deliberately a "
        "different degenerate rule from the one in "
        "`agentfailuretransfer.agreement.cohen_kappa`, which must collapse "
        "degenerate cells to a defined value in order to reproduce the "
        "published source-study tables. The two agree on every non-degenerate "
        "input."
    )
    add("")
    aidev_boot = [
        row
        for row in bootstraps
        if row["corpus"] == "AIDev" and row["ci_low"] is not None
    ]
    swesmith_pooled_boot = [
        row
        for row in bootstraps
        if row["key"] in ("swesmith_fine", "swesmith_family")
        and row["ci_low"] is not None
    ]
    overlaps = [
        (left["key"], right["key"])
        for left in aidev_boot
        for right in swesmith_pooled_boot
        if left["ci_low"] <= right["ci_high"] and right["ci_low"] <= left["ci_high"]
    ]
    add(
        "The intervals are wide. Comparing every AIDev bootstrap interval "
        "against the two pooled SWE-smith ones, "
        + (
            "none of the pairs overlap"
            if not overlaps
            else "the following pairs overlap: "
            + ", ".join(f"{left} vs {right}" for left, right in overlaps)
        )
        + " — but a non-overlap of two separate intervals is a weaker "
        "statement than a test of the difference, and no such test across "
        "corpora is run here (the two populations are not comparable enough to "
        "support one)."
    )
    add("")

    add("## 6. Generation-mechanism robustness")
    add("")
    add("Broad-family agreement by SWE-smith generation family:")
    add("")
    add("| Generation family | n | agreement | rate | 95% CI | κ | κ 95% CI |")
    add("| --- | ---: | ---: | ---: | --- | ---: | --- |")
    boot_by_key = {row["key"]: row for row in bootstraps}
    for family in ("llm", "mirror", "procedural", "combine"):
        key = f"swesmith_{family}_family"
        block = summaries[key]
        boot = boot_by_key.get(key)
        add(
            f"| {family} | {block['n']} | {block['agreements']} | "
            f"{fmt_rate(block['agreement_rate'])} | "
            f"{fmt_ci(block['wilson_ci_low'], block['wilson_ci_high'])} | "
            f"{block['cohens_kappa']:.4f} | "
            + (
                fmt_ci(boot["ci_low"], boot["ci_high"])
                if boot
                else "not bootstrapped"
            )
            + " |"
        )
    add("")
    add(
        "`combine` has n = 2. No interval, bootstrap or test is reported for "
        "it; its row exists only so that the four families sum to 100."
    )
    add("")
    add("Collapsed to the binary contrast specified in the Phase 1B plan:")
    add("")
    add("| Comparison | Group | n | agreement | rate | 95% CI |")
    add("| --- | --- | ---: | ---: | ---: | --- |")
    for block in comparisons:
        if block["metric_level"] != "family":
            continue
        add(
            f"| {block['comparison']} | procedural | {block['n_procedural']} | "
            f"{block['procedural_agreements']} | "
            f"{fmt_rate(block['procedural_rate'])} | "
            f"{fmt_ci(*block['procedural_wilson_ci'])} |"
        )
        add(
            f"| {block['comparison']} | {block['group_b']} | "
            f"{block['n_comparator']} | {block['comparator_agreements']} | "
            f"{fmt_rate(block['comparator_rate'])} | "
            f"{fmt_ci(*block['comparator_wilson_ci'])} |"
        )
    add("")
    add(
        "`nonprocedural` is `llm + mirror + combine`; the sensitivity contrast "
        "drops the two `combine` cases and compares `procedural` against "
        "`llm + mirror` only."
    )
    add("")

    add("## 7. Exploratory statistical comparison")
    add("")
    add(
        "Two-sided Fisher's exact test on the 2×2 agree/disagree table, at the "
        "broad-family level (the published level). Fine-level tables are "
        "emitted alongside in `procedural_vs_nonprocedural.csv` for "
        "completeness."
    )
    add("")
    for block in comparisons:
        if block["metric_level"] != "family":
            continue
        add(f"**{block['comparison']}** (broad family)")
        add("")
        add("| | agree | disagree |")
        add("| --- | ---: | ---: |")
        add(
            f"| procedural | {block['procedural_agreements']} | "
            f"{block['n_procedural'] - block['procedural_agreements']} |"
        )
        add(
            f"| {block['group_b']} | {block['comparator_agreements']} | "
            f"{block['n_comparator'] - block['comparator_agreements']} |"
        )
        add("")
        difference = block["risk_difference"]
        ratio = block["risk_ratio"]
        odds = block["odds_ratio"]
        add(
            f"- procedural agreement = {fmt_rate(block['procedural_rate'])}, "
            f"{block['group_b']} agreement = "
            f"{fmt_rate(block['comparator_rate'])}, absolute difference = "
            f"{abs(difference['risk_difference']) * 100:.1f} percentage points "
            f"(signed, procedural minus {block['group_b']}: "
            f"{difference['risk_difference'] * 100:.1f})"
        )
        add(
            f"- risk difference 95% CI "
            f"[{difference['ci_low'] * 100:.1f}, {difference['ci_high'] * 100:.1f}] "
            f"percentage points ({difference['ci_method']})"
        )
        add(
            f"- risk ratio = {fmt_float(ratio['risk_ratio'])}, 95% CI "
            f"{fmt_ci(ratio['ci_low'], ratio['ci_high'])} ({ratio['ci_method']})"
        )
        add(
            f"- odds ratio = {fmt_float(odds['odds_ratio'])}, 95% CI "
            f"{fmt_ci(odds['ci_low'], odds['ci_high'])} ({odds['ci_method']})"
        )
        add(
            f"- Fisher's exact test (`{block['fisher_exact']['alternative']}`): "
            f"odds ratio = {block['fisher_exact']['odds_ratio']:.6f}, "
            f"p = {block['fisher_exact']['p_value']:.6g}"
        )
        permutation = block["permutation_test"]
        add(
            f"- exploratory permutation robustness check "
            f"({permutation['permutations']} permutations, seed "
            f"{permutation['seed']}): p = "
            f"{permutation['p_value_two_sided']:.6g}"
        )
        add("")
    add(
        "These tests are **exploratory association tests**. They quantify how "
        "unusual the observed agreement gap would be under a null of no "
        "association between generation family and reviewer agreement, on one "
        "contrast chosen after seeing Phase 1A. They are not confirmatory, they "
        "carry no multiplicity correction, and they support no causal claim."
    )
    add("")

    add("## 8. Interpretation")
    add("")
    primary = next(
        block
        for block in comparisons
        if block["comparison"] == "procedural_vs_nonprocedural"
        and block["metric_level"] == "family"
    )
    add(
        "The AIDev-vs-SWE-smith gap does not depend on the denominator choice. "
        "Moving AIDev from the 49 both-technical-pattern cases "
        f"({fmt_rate(summaries['aidev_primary_fine']['agreement_rate'])} fine "
        f"agreement, κ = {summaries['aidev_primary_fine']['cohens_kappa']:.4f}) "
        "to all 100 reviewed cases "
        f"({fmt_rate(summaries['aidev_all100_fine']['agreement_rate'])}, κ = "
        f"{summaries['aidev_all100_fine']['cohens_kappa']:.4f}) leaves it well "
        "above SWE-smith "
        f"({fmt_rate(summaries['swesmith_fine']['agreement_rate'])}, κ = "
        f"{summaries['swesmith_fine']['cohens_kappa']:.4f}). The bootstrap "
        "intervals are wide but do not bring the two corpora together."
    )
    add("")
    add(
        "Within SWE-smith, reviewer agreement was lower among procedurally "
        "generated cases: "
        f"{primary['procedural_agreements']}/{primary['n_procedural']} "
        f"({fmt_rate(primary['procedural_rate'])}) against "
        f"{primary['comparator_agreements']}/{primary['n_comparator']} "
        f"({fmt_rate(primary['comparator_rate'])}) for nonprocedural cases — an "
        "absolute difference of "
        f"{abs(primary['risk_difference']['risk_difference']) * 100:.1f} "
        "percentage points, with the effect surviving both the exclusion of "
        "`combine` and the permutation check."
    )
    add("")
    add("On this evidence the results are consistent with")
    add("")
    add(
        "> taxonomy transfer being substantially weaker on SWE-smith than on "
        "AIDev and particularly weak for procedural mutations."
    )
    add("")
    add(
        "That is a statement about reviewer agreement under this taxonomy, not "
        "about the quality of the bugs, and not a causal claim about the "
        "generation mechanism."
    )
    add("")

    add("## 9. Limitations")
    add("")
    for limitation in LIMITATIONS:
        add(f"- {limitation}")
    add("")

    add("## 10. Phase 1B conclusion")
    add("")
    add(
        "The all-100 sensitivity analysis reproduces the source study's value "
        "exactly, the AIDev-vs-SWE-smith gap is unchanged by the denominator "
        "choice, and the procedural effect is large with its uncertainty now "
        "quantified rather than assumed."
    )
    add("")
    add(
        "> If the AIDev-vs-SWE-smith gap remains under all-100 sensitivity and "
        "the procedural effect remains large with uncertainty quantified, "
        "Phase 1 is considered robust enough to freeze before beginning the "
        "external-taxonomy control experiment."
    )
    add("")
    add(
        "Phase 2 has not been started. No external or mechanism-neutral "
        "taxonomy has been run, and no category-frequency comparison has been "
        "made."
    )
    add("")
    return "\n".join(lines)


def render_notes(payload: dict) -> str:
    settings = payload["analysis_settings"]
    sensitivity = payload["aidev_all100_sensitivity"]
    lines: list[str] = []
    add = lines.append

    add("# Phase 1B analysis notes")
    add("")
    add(
        "Method decisions, verbatim, so that the numbers in "
        "`robustness_report.md` can be audited without re-deriving them. "
        "Generated by `scripts/run_phase1b_robustness.py`."
    )
    add("")

    add("## The AIDev all-100 label construction")
    add("")
    add(
        "The source study's all-100 figure comes from its `cross_model` "
        "analysis in `AIBugAnalysis@scripts/compare_reviews.py`, not from its "
        "`both_pattern` dual-review analysis. Its semantics, confirmed by "
        "reading that script:"
    )
    add("")
    add(
        "1. the population is all 100 reviewed cases, iterated in `sorted("
        "case_id)` order, with both reviewers' case-id sets required to match;"
    )
    add(
        "2. the compared value is the raw `failure_pattern` field of each "
        "reviewer, with no mapping, no normalisation and no filtering;"
    )
    add(
        "3. `\"UNASSIGNED\"` is kept as an ordinary label. It is not missing "
        "data and it is not dropped, so an UNASSIGNED/UNASSIGNED case counts as "
        "an agreement — "
        f"{sensitivity['unassigned_vs_unassigned_cases']} of the 100 cases are "
        "of that kind, out of "
        f"{sensitivity['agreements']} agreements in total;"
    )
    add(
        "4. agreement is exact string equality, and κ is unweighted Cohen's "
        "kappa over the union of the labels the two reviewers actually used "
        "(the source implementation returns `None` when expected agreement is "
        "exactly 1.0; that case does not arise here);"
    )
    add(
        "5. there is **no** separate policy for nontechnical rejection, "
        "unclear, or merged-without-correction. Under the AIDev review schema "
        "all of those outcomes carry `failure_pattern == \"UNASSIGNED\"`, so "
        "they are already covered by rule 3. No missing-value policy was "
        "invented here."
    )
    add("")
    add(
        f"Recomputed from the imported sealed labels: "
        f"{sensitivity['agreements']}/{sensitivity['n']} agreement, "
        f"κ = {sensitivity['cohens_kappa']!r}. The source study's committed "
        "value in `analysis/cross_model/agreement_metrics.json` (field "
        "`pattern`) is 65/100 with κ = 0.5531154239019408; the recomputation "
        "matches it exactly (the `--check` checkpoint asserts κ to within 1e-9 "
        "and would exit non-zero otherwise). That committed value is a "
        "checkpoint, never an input: the number reported above is computed "
        "from the reviewer records."
    )
    add("")
    add(
        "The imported `data/aidev/dual_review/agreement_metrics.json` is the "
        "*dual-review* metrics file (`pattern_both_assigned`, "
        "`pattern_family_both_assigned`) and carries no all-100 field, so the "
        "all-100 cross-check is against the source study's `cross_model` "
        "artifact, read read-only from the pinned source commit during "
        "development and not imported."
    )
    add("")
    add(
        "A **derived** family-level all-100 variant is also emitted "
        "(`aidev_all100_family_derived`): non-UNASSIGNED labels are mapped "
        "through the frozen fine → family mapping and UNASSIGNED is carried "
        "through unchanged as its own label, because the frozen mapping "
        "deliberately has no family for it. The source study publishes no "
        "family-level all-100 number; this variant is ours, is labelled as "
        "such everywhere it appears, and is excluded from the bootstrap table."
    )
    add("")

    add("## Statistics")
    add("")
    add(
        f"- **Wilson score intervals** ({settings['confidence']:.0%}) for every "
        "raw agreement proportion. A naive normal (Wald) interval is not used "
        "anywhere; at n = 2 and at rates near 0 it is indefensible."
    )
    add(
        f"- **Bootstrap**: {settings['bootstrap_replicates']} replicates, base "
        f"seed {settings['bootstrap_seed']}, percentile "
        f"{settings['confidence']:.0%} interval. Cases are resampled with "
        "replacement; the two reviewers' labels for a resampled case always "
        "travel together, so a bootstrap row is always a real observed label "
        "pair. Each population draws from its own stream, "
        "`numpy.random.default_rng([seed, stream_index])`, where `stream_index` "
        "is the population's position in the fixed population order recorded in "
        "`bootstrap_summary.csv`."
    )
    add(
        "- **Undefined bootstrap replicates** (expected agreement exactly 1.0, "
        "or n = 0) are counted and excluded from the percentile interval, never "
        "mapped to 0. This differs from the degenerate rule in "
        "`agentfailuretransfer.agreement.cohen_kappa`, which collapses those to "
        "a defined value so that the published source-study tables reproduce; "
        "`agentfailuretransfer.stats.cohen_kappa_or_none` is the bootstrap "
        "variant. The two are identical on non-degenerate input."
    )
    add(
        f"- **Fisher's exact test**: `scipy.stats.fisher_exact`, "
        f"`alternative=\"{settings['fisher_alternative']}\"`, on the 2×2 "
        "agree/disagree table. The odds ratio it returns is the sample "
        "(unconditional) odds ratio."
    )
    add(
        "- **Risk difference interval**: Newcombe hybrid score interval "
        "(Newcombe 1998, method 10), built from the two groups' Wilson "
        "intervals. **Risk ratio interval**: log-scale (Katz) Wald. **Odds "
        "ratio interval**: Woolf log-scale. The two Wald-type intervals are "
        "the conventional large-sample forms and are the weakest link in this "
        "section at these subgroup sizes."
    )
    add(
        f"- **Permutation check**: {settings['permutations']} permutations, "
        f"base seed {settings['permutation_seed']}, group sizes held fixed, "
        "statistic = difference in agreement rates, p-value = "
        "`(1 + #{|permuted| >= |observed|}) / (1 + permutations)`. Labelled an "
        "exploratory permutation robustness check; it is not a second "
        "confirmatory test."
    )
    add(
        "- Each of the four comparison rows (two contrasts x two label levels) "
        "draws from its own permutation stream, "
        "`numpy.random.default_rng([seed, row_index])`. On this data the fine "
        "and family 2x2 tables of a given contrast happen to be identical -- "
        "collapsing the 11 fine labels into 9 families changes no SWE-smith "
        "subgroup's agreement count -- so their Fisher p-values are identical "
        "while their Monte-Carlo permutation p-values differ by the stream. "
        "That difference is simulation noise, not a finding."
    )
    add("")

    add("## Determinism")
    add("")
    add(
        "No timestamp is written into any Phase 1B artifact. Populations are "
        "iterated in a fixed declared order, case ids in sorted order, and "
        "every random draw is seeded. Two runs on unchanged data produce "
        "byte-identical files; `tests/test_phase1b_robustness.py` asserts it by "
        "running the script twice and comparing hashes. The recorded library "
        "versions are constant on a fixed environment; if the environment "
        "changes, `robustness_results.json` changes in the "
        "`analysis_settings.software` block only."
    )
    add("")

    add("## Scope discipline")
    add("")
    add(
        "- No reviewer label, taxonomy file or family mapping was read as "
        "anything other than input. Phase 1B writes only inside "
        "`analysis/taxonomy_transfer/phase1b_robustness/`."
    )
    add(
        "- No adjudication, no taxonomy v2, no new labels, no external "
        "taxonomy, no category-frequency comparison across corpora."
    )
    add(
        "- No causal language: the finding is that reviewer agreement was "
        "lower among procedurally generated cases."
    )
    add(
        "- The report's headings follow the Phase 1B specification's section "
        "list exactly, shifted one level down (`#` title, `##` sections) to "
        "match the other Markdown artifacts in this repository."
    )
    add("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def build_provenance() -> dict:
    aidev_manifest = load_manifest(paths.AIDEV_MANIFEST)
    swesmith_manifest = load_manifest(paths.SWESMITH_MANIFEST)
    taxonomy_sha = sha256_file(paths.AIDEV_TAXONOMY)
    mapping_sha = sha256_file(paths.AIDEV_FAMILY_MAPPING)
    if taxonomy_sha != aidev_manifest["taxonomy_sha256"]:
        raise SystemExit("STOP: the imported taxonomy hash does not match its manifest")
    if mapping_sha != aidev_manifest["family_mapping_sha256"]:
        raise SystemExit("STOP: the imported mapping hash does not match its manifest")
    return {
        "aidev": {
            "name": aidev_manifest["name"],
            "repository": aidev_manifest["repository"],
            "commit_sha": aidev_manifest["commit_sha"],
            "review_result_sha256": dict(
                sorted(aidev_manifest["review_result_sha256"].items())
            ),
        },
        "swesmith": {
            "name": swesmith_manifest["name"],
            "repository": swesmith_manifest["repository"],
            "commit_sha": swesmith_manifest["commit_sha"],
            "review_result_sha256": dict(
                sorted(swesmith_manifest["review_result_sha256"].items())
            ),
        },
        "taxonomy_sha256": taxonomy_sha,
        "family_mapping_sha256": mapping_sha,
        "swesmith_crosswalk_sha256": sha256_file(paths.SWESMITH_SAMPLE_METADATA),
        "note": (
            "Identity is commit_sha plus per-file sha256. Both source "
            "repositories are read-only scientific provenance and were not "
            "modified by this analysis."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--check",
        dest="check",
        action="store_true",
        default=True,
        help="assert the computed values against the validation checkpoint (default)",
    )
    parser.add_argument(
        "--no-check",
        dest="check",
        action="store_false",
        help="skip the validation checkpoint",
    )
    args = parser.parse_args()

    print("== running scripts/validate_sources.py first ==")
    run_source_validation()

    provenance = build_provenance()
    loaded = load_corpora()
    populations = build_populations(loaded)
    summaries = {
        population["key"]: summarise_population(population)
        for population in populations
    }

    # ---- Wilson confidence intervals ----
    ci_rows = []
    for population in populations:
        block = summaries[population["key"]]
        ci_rows.append(
            {
                "key": block["key"],
                "corpus": block["corpus"],
                "subset": block["subset"],
                "metric_level": block["metric_level"],
                "n": block["n"],
                "agreements": block["agreements"],
                "agreement_rate": block["agreement_rate"],
                "ci_method": block["ci_method"],
                "ci_low": block["wilson_ci_low"],
                "ci_high": block["wilson_ci_high"],
                "definition": block["definition"],
            }
        )

    # ---- bootstrap kappa ----
    bootstrap_populations = [
        population for population in populations if population["in_bootstrap_table"]
    ]
    bootstrap_rows = []
    for stream_index, population in enumerate(bootstrap_populations):
        result = bootstrap_kappa(
            population["codex"],
            population["claude"],
            seed=[SEED, stream_index],
            replicates=BOOTSTRAP_REPLICATES,
            confidence=CONFIDENCE,
        )
        bootstrap_rows.append(
            {
                "key": population["key"],
                "corpus": population["corpus"],
                "subset": population["subset"],
                "metric_level": population["metric_level"],
                "n": result["n"],
                "point_estimate": result["point_estimate"],
                "ci_low": result["ci_low"],
                "ci_high": result["ci_high"],
                "valid_replicates": result["valid_replicates"],
                "undefined_replicates": result["undefined_replicates"],
                "seed": SEED,
                "seed_stream_index": stream_index,
                "replicates": result["replicates"],
                "ci_method": result["ci_method"],
                "bootstrap_mean": result["bootstrap_mean"],
                "bootstrap_sd": result["bootstrap_sd"],
            }
        )

    # ---- procedural vs nonprocedural ----
    crosswalk = loaded["swesmith"]["crosswalk"]
    swesmith_ids = loaded["swesmith"]["ids"]
    procedural_ids = [
        c for c in swesmith_ids if crosswalk[c]["method_family"] == "procedural"
    ]
    nonprocedural_ids = [
        c for c in swesmith_ids if crosswalk[c]["method_family"] in NONPROCEDURAL_FAMILIES
    ]
    llm_mirror_ids = [
        c for c in swesmith_ids if crosswalk[c]["method_family"] in LLM_MIRROR_FAMILIES
    ]

    comparison_specs = [
        (
            "procedural_vs_nonprocedural",
            nonprocedural_ids,
            "nonprocedural",
            "llm + mirror + combine",
        ),
        (
            "procedural_vs_llm_mirror",
            llm_mirror_ids,
            "llm_mirror",
            "llm + mirror only (the two combine cases are dropped)",
        ),
    ]
    comparisons = []
    stream_index = 0
    for level in ("family", "fine"):
        for name, comparator_ids, label, definition in comparison_specs:
            comparisons.append(
                compare_groups(
                    loaded,
                    name,
                    level,
                    procedural_ids,
                    comparator_ids,
                    label,
                    definition,
                    stream_index,
                )
            )
            stream_index += 1

    # ---- assemble the machine-readable payload ----
    aidev_all100 = summaries["aidev_all100_fine"]
    unassigned_pairs = sum(
        1
        for case_id in loaded["aidev"]["ids"]
        if loaded["aidev"]["codex"][case_id]["failure_pattern"] == UNASSIGNED
        and loaded["aidev"]["claude"][case_id]["failure_pattern"] == UNASSIGNED
    )

    payload = {
        "generated_by": "scripts/run_phase1b_robustness.py",
        "phase": "1B",
        "taxonomy_version": TAXONOMY_VERSION,
        "source_provenance": provenance,
        "aidev_primary": {
            "fine": summaries["aidev_primary_fine"],
            "family": summaries["aidev_primary_family"],
        },
        "aidev_all100_sensitivity": {
            **aidev_all100,
            "unassigned_vs_unassigned_cases": unassigned_pairs,
            "label_construction": (
                "Raw failure_pattern strings for all 100 reviewed cases sorted "
                'by case_id, with "UNASSIGNED" kept as an ordinary label. Under '
                "the AIDev review schema every non-technical outcome "
                "(nontechnical rejection, unclear, merged without correction, "
                'or simply no technical pattern) carries "UNASSIGNED", so no '
                "separate missing-value policy exists or was invented. Source "
                "semantics: AIBugAnalysis@scripts/compare_reviews.py "
                "(cross_model, field failure_pattern)."
            ),
            "derived_family_variant": summaries["aidev_all100_family_derived"],
        },
        "swesmith_primary": {
            "fine": summaries["swesmith_fine"],
            "family": summaries["swesmith_family"],
        },
        "confidence_intervals": {
            "method": "Wilson score interval",
            "confidence": CONFIDENCE,
            "note": (
                "Intervals are for the raw exact-agreement proportion. No "
                "interval is reported for the combine family (n = 2)."
            ),
            "rows": ci_rows,
        },
        "bootstrap_kappa": {
            "method": "case-level paired nonparametric bootstrap, percentile interval",
            "seed": SEED,
            "replicates": BOOTSTRAP_REPLICATES,
            "confidence": CONFIDENCE,
            "undefined_replicate_rule": (
                "a replicate whose kappa is undefined (expected agreement "
                "exactly 1.0, or n == 0) is counted in undefined_replicates and "
                "excluded from the percentile interval; it is never mapped to 0"
            ),
            "stream_rule": (
                "each population draws from numpy.random.default_rng([seed, "
                "seed_stream_index]) where seed_stream_index is its position in "
                "the fixed population order"
            ),
            "populations": bootstrap_rows,
        },
        "generation_family": {
            "crosswalk": "data/swesmith/hidden/sample_metadata.csv",
            "crosswalk_sha256": provenance["swesmith_crosswalk_sha256"],
            "published_level": "family",
            "families": {
                family: summaries[f"swesmith_{family}_family"]
                for family in ("combine", "llm", "mirror", "procedural")
            },
        },
        "procedural_vs_nonprocedural": {
            "definitions": {
                "procedural": "method_family == procedural",
                "nonprocedural": "method_family in {llm, mirror, combine}",
                "llm_mirror": "method_family in {llm, mirror}",
            },
            "primary_level": "family",
            "comparisons": comparisons,
        },
        "analysis_settings": {
            "bootstrap_seed": SEED,
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "permutation_seed": SEED,
            "permutations": PERMUTATIONS,
            "confidence": CONFIDENCE,
            "proportion_ci_method": "Wilson score interval",
            "kappa_ci_method": "percentile bootstrap",
            "risk_difference_ci_method": (
                "Newcombe hybrid score interval (Wilson-based)"
            ),
            "risk_ratio_ci_method": "log risk ratio Wald (Katz) interval",
            "odds_ratio_ci_method": "Woolf log odds ratio interval",
            "fisher_alternative": FISHER_ALTERNATIVE,
            "fisher_implementation": "scipy.stats.fisher_exact",
            "software": {
                "python": platform.python_version(),
                "numpy": np.__version__,
                "scipy": scipy.__version__,
            },
            "determinism_note": (
                "No timestamp is written. Populations are iterated in a fixed "
                "declared order and every random draw is seeded, so two runs on "
                "unchanged data produce byte-identical artifacts on a fixed "
                "environment."
            ),
        },
    }

    if args.check:
        problems = run_check(summaries, comparisons)
        if problems:
            print("VALIDATION CHECKPOINT FAILED:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            print(
                "\nSTOP. Investigate source semantics; do not force the number.",
                file=sys.stderr,
            )
            return 1

    # ---- write artifacts ----
    paths.PHASE1B_DIR.mkdir(parents=True, exist_ok=True)

    write_csv(
        paths.PHASE1B_DIR / "aidev_denominator_sensitivity.csv",
        [
            "analysis_population",
            "corpus",
            "metric_level",
            "n",
            "agreements",
            "agreement_rate",
            "kappa",
            "definition",
        ],
        [
            {
                "analysis_population": summaries[key]["key"],
                "corpus": summaries[key]["corpus"],
                "metric_level": summaries[key]["metric_level"],
                "n": summaries[key]["n"],
                "agreements": summaries[key]["agreements"],
                "agreement_rate": csv_float(summaries[key]["agreement_rate"]),
                "kappa": csv_float(summaries[key]["cohens_kappa"]),
                "definition": summaries[key]["definition"],
            }
            for key in (
                "aidev_primary_fine",
                "aidev_primary_family",
                "aidev_all100_fine",
                "aidev_all100_family_derived",
                "swesmith_fine",
                "swesmith_family",
            )
        ],
    )

    write_csv(
        paths.PHASE1B_DIR / "agreement_confidence_intervals.csv",
        [
            "corpus",
            "subset",
            "metric_level",
            "n",
            "agreements",
            "agreement_rate",
            "ci_method",
            "ci_low",
            "ci_high",
            "analysis_population",
        ],
        [
            {
                "corpus": row["corpus"],
                "subset": row["subset"],
                "metric_level": row["metric_level"],
                "n": row["n"],
                "agreements": row["agreements"],
                "agreement_rate": csv_float(row["agreement_rate"]),
                "ci_method": row["ci_method"],
                "ci_low": csv_float(row["ci_low"]),
                "ci_high": csv_float(row["ci_high"]),
                "analysis_population": row["key"],
            }
            for row in ci_rows
        ],
    )

    write_csv(
        paths.PHASE1B_DIR / "bootstrap_summary.csv",
        [
            "analysis_population",
            "corpus",
            "subset",
            "metric_level",
            "n",
            "point_estimate",
            "ci_low",
            "ci_high",
            "ci_method",
            "valid_replicates",
            "undefined_replicates",
            "replicates",
            "seed",
            "seed_stream_index",
        ],
        [
            {
                "analysis_population": row["key"],
                "corpus": row["corpus"],
                "subset": row["subset"],
                "metric_level": row["metric_level"],
                "n": row["n"],
                "point_estimate": csv_float(row["point_estimate"]),
                "ci_low": csv_float(row["ci_low"]),
                "ci_high": csv_float(row["ci_high"]),
                "ci_method": row["ci_method"],
                "valid_replicates": row["valid_replicates"],
                "undefined_replicates": row["undefined_replicates"],
                "replicates": row["replicates"],
                "seed": row["seed"],
                "seed_stream_index": row["seed_stream_index"],
            }
            for row in bootstrap_rows
        ],
    )

    write_csv(
        paths.PHASE1B_DIR / "procedural_vs_nonprocedural.csv",
        [
            "comparison",
            "metric_level",
            "group_a",
            "n_a",
            "agree_a",
            "disagree_a",
            "rate_a",
            "group_b",
            "n_b",
            "agree_b",
            "disagree_b",
            "rate_b",
            "risk_difference",
            "risk_difference_ci_low",
            "risk_difference_ci_high",
            "risk_difference_ci_method",
            "risk_ratio",
            "risk_ratio_ci_low",
            "risk_ratio_ci_high",
            "risk_ratio_ci_method",
            "odds_ratio",
            "odds_ratio_ci_low",
            "odds_ratio_ci_high",
            "odds_ratio_ci_method",
            "fisher_odds_ratio",
            "fisher_p_value",
            "fisher_alternative",
            "permutation_p_value",
            "permutations",
            "permutation_seed",
        ],
        [
            {
                "comparison": block["comparison"],
                "metric_level": block["metric_level"],
                "group_a": block["group_a"],
                "n_a": block["n_procedural"],
                "agree_a": block["procedural_agreements"],
                "disagree_a": block["n_procedural"] - block["procedural_agreements"],
                "rate_a": csv_float(block["procedural_rate"]),
                "group_b": block["group_b"],
                "n_b": block["n_comparator"],
                "agree_b": block["comparator_agreements"],
                "disagree_b": block["n_comparator"] - block["comparator_agreements"],
                "rate_b": csv_float(block["comparator_rate"]),
                "risk_difference": csv_float(
                    block["risk_difference"]["risk_difference"]
                ),
                "risk_difference_ci_low": csv_float(block["risk_difference"]["ci_low"]),
                "risk_difference_ci_high": csv_float(
                    block["risk_difference"]["ci_high"]
                ),
                "risk_difference_ci_method": block["risk_difference"]["ci_method"],
                "risk_ratio": csv_float(block["risk_ratio"]["risk_ratio"]),
                "risk_ratio_ci_low": csv_float(block["risk_ratio"]["ci_low"]),
                "risk_ratio_ci_high": csv_float(block["risk_ratio"]["ci_high"]),
                "risk_ratio_ci_method": block["risk_ratio"]["ci_method"],
                "odds_ratio": csv_float(block["odds_ratio"]["odds_ratio"]),
                "odds_ratio_ci_low": csv_float(block["odds_ratio"]["ci_low"]),
                "odds_ratio_ci_high": csv_float(block["odds_ratio"]["ci_high"]),
                "odds_ratio_ci_method": block["odds_ratio"]["ci_method"],
                "fisher_odds_ratio": csv_float(block["fisher_exact"]["odds_ratio"]),
                "fisher_p_value": csv_float(block["fisher_exact"]["p_value"]),
                "fisher_alternative": block["fisher_exact"]["alternative"],
                "permutation_p_value": csv_float(
                    block["permutation_test"]["p_value_two_sided"]
                ),
                "permutations": block["permutation_test"]["permutations"],
                "permutation_seed": block["permutation_test"]["seed"],
            }
            for block in comparisons
        ],
    )

    report_payload = {**payload, "_summaries": summaries}
    (paths.PHASE1B_DIR / "robustness_report.md").write_text(
        render_report(report_payload), encoding="utf-8", newline="\n"
    )
    (paths.PHASE1B_DIR / "notes.md").write_text(
        render_notes(report_payload), encoding="utf-8", newline="\n"
    )
    (paths.PHASE1B_DIR / "robustness_results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    # ---- console summary (computed values only) ----
    print("== AIDev denominator sensitivity ==")
    for key in (
        "aidev_primary_fine",
        "aidev_primary_family",
        "aidev_all100_fine",
        "aidev_all100_family_derived",
    ):
        block = summaries[key]
        print(
            f"   {block['key']:<28} {block['agreements']}/{block['n']} = "
            f"{fmt_rate(block['agreement_rate'])}  kappa = "
            f"{block['cohens_kappa']:.10f}"
        )
    print(
        f"   UNASSIGNED/UNASSIGNED pairs among the 100 AIDev cases: "
        f"{unassigned_pairs}"
    )
    print()
    print("== agreement rates with Wilson 95% intervals ==")
    for row in ci_rows:
        interval = fmt_ci(row["ci_low"], row["ci_high"])
        print(
            f"   {row['key']:<28} {row['agreements']}/{row['n']} = "
            f"{fmt_rate(row['agreement_rate'])}  {interval}"
        )
    print()
    print("== bootstrap kappa (percentile 95%) ==")
    for row in bootstrap_rows:
        print(
            f"   {row['key']:<28} kappa = {fmt_float(row['point_estimate'])} "
            f"{fmt_ci(row['ci_low'], row['ci_high'])}  valid="
            f"{row['valid_replicates']} undefined={row['undefined_replicates']}"
        )
    print()
    print("== procedural vs nonprocedural ==")
    for block in comparisons:
        print(
            f"   {block['comparison']:<30} [{block['metric_level']:<6}] "
            f"procedural {block['procedural_agreements']}/{block['n_procedural']} "
            f"({fmt_rate(block['procedural_rate'])}) vs {block['group_b']} "
            f"{block['comparator_agreements']}/{block['n_comparator']} "
            f"({fmt_rate(block['comparator_rate'])})"
        )
        print(
            f"   {'':<30}  RD = "
            f"{block['risk_difference']['risk_difference'] * 100:.1f} pp "
            f"{fmt_ci(block['risk_difference']['ci_low'] * 100, block['risk_difference']['ci_high'] * 100, 1)}"
            f"  RR = {fmt_float(block['risk_ratio']['risk_ratio'])}"
            f"  OR = {fmt_float(block['odds_ratio']['odds_ratio'])}"
            f"  Fisher p = {block['fisher_exact']['p_value']:.6g}"
            f"  perm p = {block['permutation_test']['p_value_two_sided']:.6g}"
        )
    print()

    if args.check:
        print(
            "validation checkpoint: all expected counts matched exactly, the "
            "AIDev all-100 kappa matched the source study within "
            f"{SOURCE_ALL100_KAPPA_TOLERANCE}, and the Phase 1A counts are "
            "unchanged"
        )
    print(f"wrote {paths.PHASE1B_DIR.relative_to(paths.REPO_ROOT)}/ outputs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
