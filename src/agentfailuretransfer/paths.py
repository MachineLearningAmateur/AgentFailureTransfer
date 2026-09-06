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
