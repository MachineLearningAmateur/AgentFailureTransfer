"""Canonical paths inside the AgentFailureTransfer repository."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SOURCES_DIR = REPO_ROOT / "sources"
AIDEV_MANIFEST = SOURCES_DIR / "aidev_source.json"
SWESMITH_MANIFEST = SOURCES_DIR / "swesmith_source.json"

DATA_DIR = REPO_ROOT / "data"
AIDEV_DIR = DATA_DIR / "aidev"
SWESMITH_DIR = DATA_DIR / "swesmith"
DERIVED_DIR = DATA_DIR / "derived"

ANALYSIS_DIR = REPO_ROOT / "analysis"
TAXONOMY_TRANSFER_DIR = ANALYSIS_DIR / "taxonomy_transfer"
GENERATION_METHOD_DIR = ANALYSIS_DIR / "generation_method"
PHASE1B_DIR = TAXONOMY_TRANSFER_DIR / "phase1b_robustness"

# Imported artifacts referenced by name from more than one place.
AIDEV_CODEX_RESULTS = AIDEV_DIR / "reviews" / "codex" / "review_results.jsonl"
AIDEV_CLAUDE_RESULTS = AIDEV_DIR / "reviews" / "claude" / "review_results.jsonl"
AIDEV_FAMILY_MAPPING = AIDEV_DIR / "taxonomy" / "proposed_pattern_families.yaml"
AIDEV_TAXONOMY = AIDEV_DIR / "taxonomy" / "frozen_failure_taxonomy_v1.md"
AIDEV_PR_MANIFEST = AIDEV_DIR / "data" / "pr_manifest.csv"
AIDEV_AGREEMENT_METRICS = AIDEV_DIR / "dual_review" / "agreement_metrics.json"

SWESMITH_CODEX_RESULTS = SWESMITH_DIR / "reviews" / "codex" / "review_results.jsonl"
SWESMITH_CLAUDE_RESULTS = SWESMITH_DIR / "reviews" / "claude" / "review_results.jsonl"
SWESMITH_FAMILY_MAPPING = SWESMITH_DIR / "taxonomy" / "pattern_families.yaml"
SWESMITH_TAXONOMY = SWESMITH_DIR / "taxonomy" / "frozen_failure_taxonomy_v1.md"
SWESMITH_SAMPLE_METADATA = SWESMITH_DIR / "hidden" / "sample_metadata.csv"

# --------------------------------------------------------------------------
# Phase 2 — ODC external-taxonomy control.
#
# These are the in-repository locations only. The Phase 2 tooling must also
# run inside an exported reviewer bundle, which is a *different* root with the
# same internal layout, so everything downstream takes a root argument (see
# ``agentfailuretransfer.phase2.paths.Phase2Paths``) rather than reaching for
# these constants. They exist so that repo-side callers and the tests have one
# place to name the experiment directory.
# --------------------------------------------------------------------------

EXPERIMENTS_DIR = REPO_ROOT / "experiments"
PHASE2_DIR = EXPERIMENTS_DIR / "phase2_odc_control"

PHASE2_PROTOCOL_DIR = PHASE2_DIR / "protocol"
PHASE2_TAXONOMY_DIR = PHASE2_DIR / "taxonomy"
PHASE2_DATA_DIR = PHASE2_DIR / "data"
PHASE2_SCHEMAS_DIR = PHASE2_DIR / "schemas"
PHASE2_REVIEWS_DIR = PHASE2_DIR / "reviews"
PHASE2_ANALYSIS_DIR = PHASE2_DIR / "analysis"
PHASE2_BUNDLES_DIR = PHASE2_DIR / "bundles"

PHASE2_TAXONOMY_YAML = PHASE2_TAXONOMY_DIR / "odc_defect_type_v1.yaml"
PHASE2_TAXONOMY_MD = PHASE2_TAXONOMY_DIR / "odc_defect_type_v1.md"
PHASE2_TAXONOMY_PROVENANCE = PHASE2_TAXONOMY_DIR / "SOURCE_PROVENANCE.md"

PHASE2_SCHEMA = PHASE2_SCHEMAS_DIR / "odc_review_result.schema.json"

PHASE2_REVIEW_PACKETS = PHASE2_DATA_DIR / "review_packets"
PHASE2_REVIEW_MANIFEST = PHASE2_DATA_DIR / "review_manifest.csv"
PHASE2_SNAPSHOT_MANIFEST = PHASE2_DATA_DIR / "review_snapshot_manifest.json"
PHASE2_IMPORT_PROVENANCE = PHASE2_DATA_DIR / "IMPORT_PROVENANCE.json"

PHASE2_FREEZE_MANIFEST = PHASE2_DIR / "FREEZE_MANIFEST.json"

# The Phase 1 SWE-smith artifacts the Phase 2 import verifies its copies
# against. Reading these is a hash comparison; no per-case label is opened.
SWESMITH_REVIEW_MANIFEST = SWESMITH_DIR / "review_manifest.csv"
SWESMITH_SNAPSHOT_MANIFEST = SWESMITH_DIR / "review_snapshot_manifest.json"
