#!/usr/bin/env python3
"""Recompute the headline agreement results from the imported sealed labels.

    python scripts/reproduce_headline_results.py [--no-check]

Nothing here is read out of a report. Every number is computed from the
imported reviewer records using the canonical inclusion rules of the two source
studies:

* AIDev  -- include a case iff BOTH reviewers assigned a technical pattern,
  i.e. ``failure_pattern != "UNASSIGNED"`` on both sides. This is the rule in
  ``AIBugAnalysis/scripts/analyze_dual_reviews.py`` (``both_pattern``); it is
  the ONLY filter, and it is not conditioned on outcome, scope or confidence.
* SWE-smith -- include all 100 frozen cases. The SWE-smith review schema has no
  ``UNASSIGNED`` value, so no exclusion rule applies.

The frozen fine -> broad-family mapping is then applied deterministically to
BOTH reviewers' original labels. No label is reinterpreted, adjudicated or
re-classified anywhere in this script.

Generation metadata is joined ONLY after the reviewer results are loaded, from
the hidden crosswalk that was withheld from the reviewers.

Outputs:
    analysis/taxonomy_transfer/headline_results.json
    analysis/taxonomy_transfer/headline_results.md
    analysis/generation_method/agreement_by_generation.json
    analysis/generation_method/agreement_by_generation.md
    data/derived/aidev_both_assigned_case_ids.json     (derived reconstruction)
    data/derived/aidev_strict_code_state_case_ids.json (derived reconstruction)
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from agentfailuretransfer import paths  # noqa: E402
from agentfailuretransfer.agreement import agreement  # noqa: E402
from agentfailuretransfer.hashing import sha256_file  # noqa: E402
from agentfailuretransfer.reviews import (  # noqa: E402
    duplicate_case_ids,
    load_review_jsonl,
)
from agentfailuretransfer.taxonomy import (  # noqa: E402
    TAXONOMY_VERSION,
    UNASSIGNED,
    load_family_mapping,
)

# --------------------------------------------------------------------------
# Validation checkpoint. These are TARGETS, never outputs: --check compares the
# computed values against them and exits non-zero on a mismatch. No number
# below is ever written into an analysis artifact.
# --------------------------------------------------------------------------
KAPPA_TOLERANCE = 5e-4

EXPECTED = {
    "aidev": {
        "n": 49,
        "fine": {"exact": 31, "kappa": 0.5828},
        "family": {"exact": 36, "kappa": 0.6575},
    },
    "swesmith": {
        "n": 100,
        "fine": {"exact": 41, "kappa": 0.254},
        "family": {"exact": 41, "kappa": 0.242},
    },
    # The published per-generation-family kappas are FAMILY-level.
    "generation_family": {
        "llm": {"n": 36, "exact": 20, "kappa": 0.298},
        "mirror": {"n": 28, "exact": 15, "kappa": 0.393},
        "procedural": {"n": 34, "exact": 6, "kappa": 0.127},
        "combine": {"n": 2, "exact": 0, "kappa": 0.0},
    },
}

EXPECTED_GENERATION_FAMILIES = {"llm", "mirror", "procedural", "combine"}

TECHNICAL_DEFECT_OUTCOMES = {"TECHNICAL_FAILURE_EVIDENCE", "MERGED_AFTER_HUMAN_CORRECTION"}
CODE_STATE_COMPATIBLE_SCOPES = {"CODE_STATE", "BOTH"}


def index_by_case_id(records: list[dict], label: str) -> dict[str, dict]:
    dupes = duplicate_case_ids(records)
    if dupes:
        raise SystemExit(f"STOP: {label} has duplicate case_ids: {dupes}")
    return {record["case_id"]: record for record in records}


def require_same_case_ids(left: dict, right: dict, label: str) -> list[str]:
    if set(left) != set(right):
        only_left = sorted(set(left) - set(right))
        only_right = sorted(set(right) - set(left))
        raise SystemExit(
            f"STOP: {label} reviewers did not review the same case ids: "
            f"codex-only={only_left} claude-only={only_right}"
        )
    return sorted(left)


def load_pr_manifest(path: Path) -> dict[str, dict]:
    """Mirror the source study's one-to-one join onto data/pr_manifest.csv."""
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    seen: dict[str, dict] = {}
    for row in rows:
        case_id = row["case_id"]
        if case_id in seen:
            raise SystemExit(f"STOP: {path} is not one-to-one on case_id ({case_id})")
        seen[case_id] = row
    return seen


def analyse_aidev(mapping: dict[str, str]) -> dict:
    codex = index_by_case_id(load_review_jsonl(paths.AIDEV_CODEX_RESULTS), "AIDev codex")
    claude = index_by_case_id(load_review_jsonl(paths.AIDEV_CLAUDE_RESULTS), "AIDev claude")
    all_ids = require_same_case_ids(codex, claude, "AIDev")

    manifest = load_pr_manifest(paths.AIDEV_PR_MANIFEST)
    if set(manifest) != set(all_ids):
        raise SystemExit(
            "STOP: pr_manifest.csv case_ids do not match the reviewed case ids"
        )

    # Canonical inclusion rule (analyze_dual_reviews.py::both_pattern).
    both_ids = [
        case_id
        for case_id in all_ids
        if codex[case_id]["failure_pattern"] != UNASSIGNED
        and claude[case_id]["failure_pattern"] != UNASSIGNED
    ]

    codex_fine = [codex[c]["failure_pattern"] for c in both_ids]
    claude_fine = [claude[c]["failure_pattern"] for c in both_ids]
    codex_family = [mapping[label] for label in codex_fine]
    claude_family = [mapping[label] for label in claude_fine]

    # Derived reconstruction of the 35-case strict code-state corpus
    # (build_rq1_aidev_dataset.py). This restates imported reviewer labels; it
    # creates no new classification.
    strict_ids = [
        case_id
        for case_id in both_ids
        if codex[case_id]["outcome_classification"] in TECHNICAL_DEFECT_OUTCOMES
        and claude[case_id]["outcome_classification"] in TECHNICAL_DEFECT_OUTCOMES
        and codex[case_id]["failure_scope"] in CODE_STATE_COMPATIBLE_SCOPES
        and claude[case_id]["failure_scope"] in CODE_STATE_COMPATIBLE_SCOPES
        and mapping[codex[case_id]["failure_pattern"]]
        == mapping[claude[case_id]["failure_pattern"]]
    ]

    return {
        "corpus": "AIDev (real coding-agent repair attempts)",
        "reviewed_cases": len(all_ids),
        "inclusion_rule": (
            "both reviewers assigned a technical pattern "
            '(failure_pattern != "UNASSIGNED" on both sides)'
        ),
        "inclusion_rule_source": (
            "AIBugAnalysis@scripts/analyze_dual_reviews.py (both_pattern)"
        ),
        "n_included": len(both_ids),
        "included_case_ids": both_ids,
        "fine_grained": agreement(codex_fine, claude_fine),
        "family": agreement(codex_family, claude_family),
        "strict_code_state_case_ids": strict_ids,
        "strict_code_state_n": len(strict_ids),
        "fine_label_distribution": {
            "codex": dict(Counter(codex_fine).most_common()),
            "claude": dict(Counter(claude_fine).most_common()),
        },
        "family_distribution": {
            "codex": dict(Counter(codex_family).most_common()),
            "claude": dict(Counter(claude_family).most_common()),
        },
    }


def analyse_swesmith(mapping: dict[str, str]) -> tuple[dict, dict]:
    codex = index_by_case_id(
        load_review_jsonl(paths.SWESMITH_CODEX_RESULTS), "SWE-smith codex"
    )
    claude = index_by_case_id(
        load_review_jsonl(paths.SWESMITH_CLAUDE_RESULTS), "SWE-smith claude"
    )
    case_ids = require_same_case_ids(codex, claude, "SWE-smith")

    for label, records in (("codex", codex), ("claude", claude)):
        offenders = [c for c, r in records.items() if r["failure_pattern"] == UNASSIGNED]
        if offenders:
            raise SystemExit(
                f"STOP: SWE-smith {label} contains UNASSIGNED labels, which the "
                f"schema forbids: {offenders}"
            )

    codex_fine = [codex[c]["failure_pattern"] for c in case_ids]
    claude_fine = [claude[c]["failure_pattern"] for c in case_ids]
    codex_family = [mapping[label] for label in codex_fine]
    claude_family = [mapping[label] for label in claude_fine]

    pooled = {
        "corpus": "SWE-smith (synthetic training bugs)",
        "reviewed_cases": len(case_ids),
        "inclusion_rule": (
            "all frozen cases; the SWE-smith review schema has no UNASSIGNED "
            "value, so no exclusion rule applies"
        ),
        "inclusion_rule_source": (
            "SWE-Smith-Bug-Analysis@scripts/apply_frozen_families.py (no filtering)"
        ),
        "n_included": len(case_ids),
        "fine_grained": agreement(codex_fine, claude_fine),
        "family": agreement(codex_family, claude_family),
        "fine_label_distribution": {
            "codex": dict(Counter(codex_fine).most_common()),
            "claude": dict(Counter(claude_fine).most_common()),
        },
        "family_distribution": {
            "codex": dict(Counter(codex_family).most_common()),
            "claude": dict(Counter(claude_family).most_common()),
        },
    }

    # --- generation metadata is joined ONLY NOW, after the labels are loaded ---
    with paths.SWESMITH_SAMPLE_METADATA.open(encoding="utf-8", newline="") as handle:
        meta_rows = list(csv.DictReader(handle))
    meta: dict[str, dict] = {}
    for row in meta_rows:
        if row["case_id"] in meta:
            raise SystemExit(
                f"STOP: hidden sample_metadata.csv duplicates {row['case_id']}"
            )
        meta[row["case_id"]] = row
    if set(meta) != set(case_ids):
        raise SystemExit(
            "STOP: hidden sample metadata does not cover exactly the reviewed "
            f"case ids (metadata n={len(meta)}, reviewed n={len(case_ids)})"
        )

    observed_families = {row["method_family"] for row in meta.values()}
    unexpected = observed_families - EXPECTED_GENERATION_FAMILIES
    if unexpected:
        raise SystemExit(
            f"STOP: unexpected method_family values in the crosswalk: {sorted(unexpected)}"
        )

    groups: dict[str, list[str]] = defaultdict(list)
    for case_id in case_ids:
        groups[meta[case_id]["method_family"]].append(case_id)

    by_family: dict[str, dict] = {}
    for family in sorted(groups):
        subset = groups[family]
        sub_codex_fine = [codex[c]["failure_pattern"] for c in subset]
        sub_claude_fine = [claude[c]["failure_pattern"] for c in subset]
        by_family[family] = {
            "n": len(subset),
            "case_ids": subset,
            "generation_methods": dict(
                Counter(meta[c]["generation_method"] for c in subset).most_common()
            ),
            # The PUBLISHED per-family kappa is the family-level one.
            "family_level": agreement(
                [mapping[label] for label in sub_codex_fine],
                [mapping[label] for label in sub_claude_fine],
            ),
            # Reported for completeness only; it is NOT the published number.
            "fine_level": agreement(sub_codex_fine, sub_claude_fine),
        }

    generation = {
        "corpus": "SWE-smith (synthetic training bugs)",
        "join_note": (
            "The hidden generation crosswalk was withheld from both reviewers "
            "and is joined only after the sealed labels are loaded."
        ),
        "crosswalk": "data/swesmith/hidden/sample_metadata.csv",
        "crosswalk_sha256": sha256_file(paths.SWESMITH_SAMPLE_METADATA),
        "mapping_authority": (
            "materialised method_family column, produced by "
            "SWE-Smith-Bug-Analysis@ssr/swesmith.py::method_family()"
        ),
        "published_level": "family_level",
        "n_cases": len(case_ids),
        "by_generation_family": by_family,
        "pooled_family_level": pooled["family"],
        "pooled_fine_level": pooled["fine_grained"],
    }
    return pooled, generation


def close_enough(actual: float, expected: float) -> bool:
    return abs(actual - expected) <= KAPPA_TOLERANCE


def run_check(aidev: dict, swesmith: dict, generation: dict) -> list[str]:
    problems: list[str] = []

    def check_block(name: str, computed: dict, expected: dict, n_expected: int) -> None:
        if computed["n"] != n_expected:
            problems.append(
                f"{name}: n = {computed['n']}, expected {n_expected}"
            )
        if computed["exact_agreements"] != expected["exact"]:
            problems.append(
                f"{name}: exact agreements = {computed['exact_agreements']}, "
                f"expected {expected['exact']}"
            )
        if not close_enough(computed["cohens_kappa"], expected["kappa"]):
            problems.append(
                f"{name}: kappa = {computed['cohens_kappa']:.10f}, expected "
                f"{expected['kappa']} (tolerance {KAPPA_TOLERANCE})"
            )

    check_block(
        "AIDev fine", aidev["fine_grained"], EXPECTED["aidev"]["fine"], EXPECTED["aidev"]["n"]
    )
    check_block(
        "AIDev family", aidev["family"], EXPECTED["aidev"]["family"], EXPECTED["aidev"]["n"]
    )
    check_block(
        "SWE-smith fine",
        swesmith["fine_grained"],
        EXPECTED["swesmith"]["fine"],
        EXPECTED["swesmith"]["n"],
    )
    check_block(
        "SWE-smith family",
        swesmith["family"],
        EXPECTED["swesmith"]["family"],
        EXPECTED["swesmith"]["n"],
    )

    observed = set(generation["by_generation_family"])
    expected_families = set(EXPECTED["generation_family"])
    if observed != expected_families:
        problems.append(
            f"generation families = {sorted(observed)}, expected {sorted(expected_families)}"
        )
    for family, expectation in EXPECTED["generation_family"].items():
        block = generation["by_generation_family"].get(family)
        if block is None:
            continue
        if block["n"] != expectation["n"]:
            problems.append(
                f"generation family {family}: n = {block['n']}, expected {expectation['n']}"
            )
        check_block(
            f"generation family {family} (family-level)",
            block["family_level"],
            {"exact": expectation["exact"], "kappa": expectation["kappa"]},
            expectation["n"],
        )

    # Independent cross-check against the imported source-study metrics file.
    published = json.loads(paths.AIDEV_AGREEMENT_METRICS.read_text(encoding="utf-8"))
    fine_block = published["pattern_both_assigned"]
    family_block = published["pattern_family_both_assigned"]
    if fine_block["n"] != aidev["fine_grained"]["n"]:
        problems.append(
            "imported AIDev agreement_metrics.json disagrees on n: "
            f"{fine_block['n']} vs {aidev['fine_grained']['n']}"
        )
    if fine_block["exact_agreement"] != aidev["fine_grained"]["exact_agreements"]:
        problems.append(
            "imported AIDev agreement_metrics.json disagrees on fine exact agreement: "
            f"{fine_block['exact_agreement']} vs {aidev['fine_grained']['exact_agreements']}"
        )
    if not close_enough(fine_block["cohen_kappa"], aidev["fine_grained"]["cohens_kappa"]):
        problems.append(
            "imported AIDev agreement_metrics.json disagrees on fine kappa: "
            f"{fine_block['cohen_kappa']} vs {aidev['fine_grained']['cohens_kappa']}"
        )
    if family_block["exact_agreement"] != aidev["family"]["exact_agreements"]:
        problems.append(
            "imported AIDev agreement_metrics.json disagrees on family exact agreement: "
            f"{family_block['exact_agreement']} vs {aidev['family']['exact_agreements']}"
        )
    if not close_enough(family_block["cohen_kappa"], aidev["family"]["cohens_kappa"]):
        problems.append(
            "imported AIDev agreement_metrics.json disagrees on family kappa: "
            f"{family_block['cohen_kappa']} vs {aidev['family']['cohens_kappa']}"
        )
    return problems


CAVEATS = [
    "The broad-family mapping was developed from AIDev disagreement data "
    "(analysis/taxonomy/family_mapping_analysis.md in the source study). The "
    "AIDev family-level agreement is therefore partly IN-SAMPLE and is not an "
    "out-of-sample estimate. The SWE-smith family-level agreement is the "
    "out-of-sample application of the same frozen mapping.",
    "The two populations are NOT structurally comparable. The AIDev metrics are "
    "computed on the 49 cases where both reviewers assigned a technical pattern; "
    "the SWE-smith metrics are computed on all 100 cases, because the SWE-smith "
    "review schema has no UNASSIGNED value.",
    "Agreement measures reproducibility between two LLM reviewers. It is not a "
    "measure of correctness.",
    "The combine generation family has n = 2 and is not interpretable. Its "
    "agreement and kappa are reported only for completeness.",
    "The per-generation-family kappas reported as the headline are FAMILY-LEVEL. "
    "The fine-level values are listed beside them and differ (notably for llm).",
]


def fmt_pct(rate: float | None) -> str:
    return "n/a" if rate is None else f"{rate * 100:.1f}%"


def render_headline_md(payload: dict) -> str:
    aidev = payload["aidev"]
    swesmith = payload["swesmith"]
    lines: list[str] = []
    lines.append("# Headline taxonomy-transfer results")
    lines.append("")
    lines.append(
        "Recomputed from the imported sealed reviewer labels by "
        "`scripts/reproduce_headline_results.py`. No value here is read out of a "
        "source-study report, and no reviewer label was reinterpreted."
    )
    lines.append("")
    lines.append(f"- Taxonomy version: `{payload['taxonomy_version']}`")
    lines.append(f"- Family mapping sha256: `{payload['family_mapping_sha256']}`")
    lines.append(f"- Kappa: unweighted Cohen's kappa, {payload['kappa_note']}")
    lines.append("")

    lines.append("## Fine-grained taxonomy")
    lines.append("")
    lines.append("The 11 frozen fine-grained failure patterns, exactly as sealed.")
    lines.append("")
    lines.append("| Corpus | n | exact agreement | rate | Cohen's kappa | kappa (4 dp) |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for block in (aidev, swesmith):
        fine = block["fine_grained"]
        lines.append(
            f"| {block['corpus']} | {fine['n']} | {fine['exact_agreements']} | "
            f"{fmt_pct(fine['agreement_rate'])} | {fine['cohens_kappa']:.10f} | "
            f"{fine['cohens_kappa_4dp']} |"
        )
    lines.append("")

    lines.append("## Frozen broad-family mapping")
    lines.append("")
    lines.append(
        "The same sealed fine labels mapped deterministically through the frozen "
        "`fine -> family` mapping. Neither reviewer re-classified anything."
    )
    lines.append("")
    lines.append("| Corpus | n | exact agreement | rate | Cohen's kappa | kappa (4 dp) |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for block in (aidev, swesmith):
        fam = block["family"]
        lines.append(
            f"| {block['corpus']} | {fam['n']} | {fam['exact_agreements']} | "
            f"{fmt_pct(fam['agreement_rate'])} | {fam['cohens_kappa']:.10f} | "
            f"{fam['cohens_kappa_4dp']} |"
        )
    lines.append("")

    lines.append("## Inclusion rules")
    lines.append("")
    for block in (aidev, swesmith):
        lines.append(f"- **{block['corpus']}** ({block['n_included']} cases): {block['inclusion_rule']}")
        lines.append(f"  - source of the rule: `{block['inclusion_rule_source']}`")
    lines.append("")

    lines.append("## Caveats")
    lines.append("")
    for caveat in CAVEATS:
        lines.append(f"- {caveat}")
    lines.append("")

    lines.append("## Derived reconstructions")
    lines.append("")
    lines.append(
        "`data/derived/aidev_both_assigned_case_ids.json` and "
        "`data/derived/aidev_strict_code_state_case_ids.json` restate which "
        "imported cases satisfy the two source-study inclusion rules "
        f"({aidev['n_included']} and {aidev['strict_code_state_n']} cases "
        "respectively). They are derived from imported labels, not new "
        "classifications. Coverage of the strict corpus is deliberately not "
        "analysed here."
    )
    lines.append("")
    return "\n".join(lines)


def render_generation_md(payload: dict) -> str:
    lines: list[str] = []
    lines.append("# Agreement by synthetic bug-generation family")
    lines.append("")
    lines.append(
        "Recomputed from the imported sealed SWE-smith labels. The generation "
        "crosswalk was withheld from both reviewers and is joined only after the "
        "labels are loaded."
    )
    lines.append("")
    lines.append(f"- Crosswalk: `{payload['crosswalk']}`")
    lines.append(f"- Crosswalk sha256: `{payload['crosswalk_sha256']}`")
    lines.append(f"- Mapping authority: {payload['mapping_authority']}")
    lines.append("")

    lines.append("## Frozen broad-family mapping (the published level)")
    lines.append("")
    lines.append("| Generation family | n | exact agreement | rate | Cohen's kappa | kappa (4 dp) |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for family in sorted(payload["by_generation_family"]):
        block = payload["by_generation_family"][family]["family_level"]
        lines.append(
            f"| {family} | {block['n']} | {block['exact_agreements']} | "
            f"{fmt_pct(block['agreement_rate'])} | {block['cohens_kappa']:.10f} | "
            f"{block['cohens_kappa_4dp']} |"
        )
    pooled = payload["pooled_family_level"]
    lines.append(
        f"| **pooled (all cases)** | {pooled['n']} | {pooled['exact_agreements']} | "
        f"{fmt_pct(pooled['agreement_rate'])} | {pooled['cohens_kappa']:.10f} | "
        f"{pooled['cohens_kappa_4dp']} |"
    )
    lines.append("")

    lines.append("## Fine-grained taxonomy (for completeness, NOT the published level)")
    lines.append("")
    lines.append("| Generation family | n | exact agreement | rate | Cohen's kappa | kappa (4 dp) |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for family in sorted(payload["by_generation_family"]):
        block = payload["by_generation_family"][family]["fine_level"]
        lines.append(
            f"| {family} | {block['n']} | {block['exact_agreements']} | "
            f"{fmt_pct(block['agreement_rate'])} | {block['cohens_kappa']:.10f} | "
            f"{block['cohens_kappa_4dp']} |"
        )
    pooled_fine = payload["pooled_fine_level"]
    lines.append(
        f"| **pooled (all cases)** | {pooled_fine['n']} | {pooled_fine['exact_agreements']} | "
        f"{fmt_pct(pooled_fine['agreement_rate'])} | {pooled_fine['cohens_kappa']:.10f} | "
        f"{pooled_fine['cohens_kappa_4dp']} |"
    )
    lines.append("")
    lines.append(
        "Each subgroup kappa uses that subgroup's own marginals, not the pooled "
        "marginals."
    )
    lines.append("")

    lines.append("## Generation methods behind each family")
    lines.append("")
    for family in sorted(payload["by_generation_family"]):
        methods = payload["by_generation_family"][family]["generation_methods"]
        rendered = ", ".join(f"`{m}` ({c})" for m, c in methods.items())
        lines.append(f"- **{family}**: {rendered}")
    lines.append("")

    lines.append("## Caveats")
    lines.append("")
    for caveat in CAVEATS:
        lines.append(f"- {caveat}")
    lines.append("")
    return "\n".join(lines)


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

    mapping = load_family_mapping(paths.AIDEV_FAMILY_MAPPING)
    swesmith_mapping = load_family_mapping(paths.SWESMITH_FAMILY_MAPPING)
    if mapping != swesmith_mapping:
        raise SystemExit("STOP: the two imported family mappings differ")

    aidev = analyse_aidev(mapping)
    swesmith, generation = analyse_swesmith(mapping)

    kappa_note = (
        "hand-rolled, expected agreement over the union of both "
        "raters' observed labels; reported at full precision and rounded to "
        "4 dp. Degenerate rule: expected agreement == 1.0 (or n == 0) yields "
        "0.0 unless observed agreement is 1.0, in which case 1.0."
    )

    headline = {
        "generated_by": "scripts/reproduce_headline_results.py",
        "taxonomy_version": TAXONOMY_VERSION,
        "family_mapping_sha256": sha256_file(paths.AIDEV_FAMILY_MAPPING),
        "taxonomy_sha256": sha256_file(paths.AIDEV_TAXONOMY),
        "kappa_note": kappa_note,
        "caveats": CAVEATS,
        "aidev": aidev,
        "swesmith": swesmith,
    }

    generation_payload = {
        "generated_by": "scripts/reproduce_headline_results.py",
        "taxonomy_version": TAXONOMY_VERSION,
        "kappa_note": kappa_note,
        "caveats": CAVEATS,
        **generation,
    }

    paths.TAXONOMY_TRANSFER_DIR.mkdir(parents=True, exist_ok=True)
    paths.GENERATION_METHOD_DIR.mkdir(parents=True, exist_ok=True)
    paths.DERIVED_DIR.mkdir(parents=True, exist_ok=True)

    (paths.TAXONOMY_TRANSFER_DIR / "headline_results.json").write_text(
        json.dumps(headline, indent=2) + "\n", encoding="utf-8"
    )
    (paths.TAXONOMY_TRANSFER_DIR / "headline_results.md").write_text(
        render_headline_md(headline), encoding="utf-8"
    )
    (paths.GENERATION_METHOD_DIR / "agreement_by_generation.json").write_text(
        json.dumps(generation_payload, indent=2) + "\n", encoding="utf-8"
    )
    (paths.GENERATION_METHOD_DIR / "agreement_by_generation.md").write_text(
        render_generation_md(generation_payload), encoding="utf-8"
    )

    derivation_note = (
        "DERIVED RECONSTRUCTION. These case ids are recomputed from the "
        "imported sealed reviewer labels by applying a source-study inclusion "
        "rule. They are not a new classification, not an adjudication, and not "
        "a new labelling exercise."
    )
    (paths.DERIVED_DIR / "aidev_both_assigned_case_ids.json").write_text(
        json.dumps(
            {
                "note": derivation_note,
                "rule": aidev["inclusion_rule"],
                "rule_source": aidev["inclusion_rule_source"],
                "n": aidev["n_included"],
                "case_ids": aidev["included_case_ids"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (paths.DERIVED_DIR / "aidev_strict_code_state_case_ids.json").write_text(
        json.dumps(
            {
                "note": derivation_note,
                "rule": (
                    "technical_defect_consensus == BOTH_YES (both "
                    "outcome_classification in {TECHNICAL_FAILURE_EVIDENCE, "
                    "MERGED_AFTER_HUMAN_CORRECTION}) AND both failure_scope in "
                    "{CODE_STATE, BOTH} AND both reviewers assigned a technical "
                    "pattern AND the two broad families agree"
                ),
                "rule_source": "AIBugAnalysis@scripts/build_rq1_aidev_dataset.py",
                "expected_to_equal": (
                    "the rows of the imported opaque artifact "
                    "data/aidev/derived/aidev_rq1_primary_cases.parquet, which "
                    "this repository stores by hash and never parses"
                ),
                "coverage_analysis": "deliberately not performed in this phase",
                "n": aidev["strict_code_state_n"],
                "case_ids": aidev["strict_code_state_case_ids"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    # ---- console summary (computed values only) ----
    print("== AIDev (real coding-agent repair attempts) ==")
    print(f"   inclusion rule : {aidev['inclusion_rule']}")
    print(f"   reviewed cases : {aidev['reviewed_cases']}")
    print(f"   included cases : {aidev['n_included']}")
    for level, key in (("fine  ", "fine_grained"), ("family", "family")):
        block = aidev[key]
        print(
            f"   {level} : {block['exact_agreements']}/{block['n']} = "
            f"{fmt_pct(block['agreement_rate'])}  kappa = "
            f"{block['cohens_kappa']:.10f} ({block['cohens_kappa_4dp']})"
        )
    print(f"   derived strict code-state corpus: {aidev['strict_code_state_n']} cases")
    print()
    print("== SWE-smith (synthetic training bugs) ==")
    print(f"   inclusion rule : {swesmith['inclusion_rule']}")
    print(f"   included cases : {swesmith['n_included']}")
    for level, key in (("fine  ", "fine_grained"), ("family", "family")):
        block = swesmith[key]
        print(
            f"   {level} : {block['exact_agreements']}/{block['n']} = "
            f"{fmt_pct(block['agreement_rate'])}  kappa = "
            f"{block['cohens_kappa']:.10f} ({block['cohens_kappa_4dp']})"
        )
    print()
    print("== SWE-smith by generation family (family level = published level) ==")
    for family in sorted(generation["by_generation_family"]):
        block = generation["by_generation_family"][family]
        fam = block["family_level"]
        fine = block["fine_level"]
        print(
            f"   {family:<11} n={fam['n']:<4} family: {fam['exact_agreements']}/{fam['n']} = "
            f"{fmt_pct(fam['agreement_rate'])} kappa={fam['cohens_kappa']:.10f} "
            f"({fam['cohens_kappa_4dp']})"
        )
        print(
            f"   {'':<11} {'':<4}    fine  : {fine['exact_agreements']}/{fine['n']} = "
            f"{fmt_pct(fine['agreement_rate'])} kappa={fine['cohens_kappa']:.10f} "
            f"({fine['cohens_kappa_4dp']})"
        )
    print()

    if args.check:
        problems = run_check(aidev, swesmith, generation)
        if problems:
            print("VALIDATION CHECKPOINT FAILED:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            print(
                "\nSTOP. Investigate source semantics; do not force the number.",
                file=sys.stderr,
            )
            return 1
        print(
            "validation checkpoint: all expected counts matched exactly and all "
            f"kappas matched within {KAPPA_TOLERANCE}"
        )

    print("wrote analysis/taxonomy_transfer/ and analysis/generation_method/ outputs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
