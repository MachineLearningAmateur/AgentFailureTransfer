"""The emitted reports must say the things the study design requires."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentfailuretransfer import paths

REPORTS = [
    paths.TAXONOMY_TRANSFER_DIR / "headline_results.md",
    paths.GENERATION_METHOD_DIR / "agreement_by_generation.md",
]

# The obsolete SSR sampling description must never appear anywhere in this repo.
# Built from parts so that this file is not itself an occurrence of them.
_SEP = "/"
FORBIDDEN_SUBSTRINGS = (
    _SEP.join(("30", "40", "30")),
    _SEP.join(("30", "30", "40")),
)


@pytest.fixture(params=REPORTS, ids=lambda p: p.name)
def report(request) -> str:
    if not request.param.is_file():
        pytest.skip("run scripts/reproduce_headline_results.py first")
    return request.param.read_text(encoding="utf-8")


def test_report_separates_fine_from_family(report):
    assert "Fine-grained taxonomy" in report
    assert "Frozen broad-family mapping" in report


def test_report_states_the_in_sample_caveat(report):
    assert "IN-SAMPLE" in report or "in-sample" in report
    assert "AIDev disagreement data" in report


def test_report_states_the_population_caveat(report):
    assert "49" in report
    assert "UNASSIGNED" in report


def test_report_flags_combine_as_uninterpretable(report):
    assert "combine" in report
    assert "n = 2" in report


def test_generation_report_labels_the_published_level():
    path = paths.GENERATION_METHOD_DIR / "agreement_by_generation.md"
    if not path.is_file():
        pytest.skip("run scripts/reproduce_headline_results.py first")
    text = path.read_text(encoding="utf-8")
    assert "the published level" in text
    assert "NOT the published level" in text


def test_no_obsolete_sampling_text_anywhere():
    repo_root = Path(paths.REPO_ROOT)
    offenders: list[str] = []
    skip_dirs = {".git", ".venv", "__pycache__", ".pytest_cache"}
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix in {".parquet", ".pdf", ".png", ".pyc"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for needle in FORBIDDEN_SUBSTRINGS:
            if needle in text:
                offenders.append(f"{path.relative_to(repo_root)} contains {needle!r}")
    assert offenders == [], offenders
