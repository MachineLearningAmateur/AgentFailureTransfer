"""Shared fixtures. Everything reads imported artifacts; nothing is written."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from agentfailuretransfer import paths  # noqa: E402
from agentfailuretransfer.manifest import load_manifest  # noqa: E402
from agentfailuretransfer.reviews import load_review_jsonl  # noqa: E402
from agentfailuretransfer.taxonomy import load_family_mapping  # noqa: E402


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def aidev_manifest() -> dict:
    return load_manifest(paths.AIDEV_MANIFEST)


@pytest.fixture(scope="session")
def swesmith_manifest() -> dict:
    return load_manifest(paths.SWESMITH_MANIFEST)


@pytest.fixture(scope="session")
def family_mapping() -> dict[str, str]:
    return load_family_mapping(paths.AIDEV_FAMILY_MAPPING)


@pytest.fixture(scope="session")
def aidev_reviews() -> dict[str, dict[str, dict]]:
    return {
        "codex": {r["case_id"]: r for r in load_review_jsonl(paths.AIDEV_CODEX_RESULTS)},
        "claude": {r["case_id"]: r for r in load_review_jsonl(paths.AIDEV_CLAUDE_RESULTS)},
    }


@pytest.fixture(scope="session")
def swesmith_reviews() -> dict[str, dict[str, dict]]:
    return {
        "codex": {r["case_id"]: r for r in load_review_jsonl(paths.SWESMITH_CODEX_RESULTS)},
        "claude": {r["case_id"]: r for r in load_review_jsonl(paths.SWESMITH_CLAUDE_RESULTS)},
    }


@pytest.fixture(scope="session")
def swesmith_crosswalk() -> dict[str, dict]:
    with paths.SWESMITH_SAMPLE_METADATA.open(encoding="utf-8", newline="") as handle:
        return {row["case_id"]: row for row in csv.DictReader(handle)}


@pytest.fixture(scope="session")
def headline_results() -> dict:
    path = paths.TAXONOMY_TRANSFER_DIR / "headline_results.json"
    if not path.is_file():
        pytest.skip("run scripts/reproduce_headline_results.py first")
    return json.loads(path.read_text(encoding="utf-8"))
