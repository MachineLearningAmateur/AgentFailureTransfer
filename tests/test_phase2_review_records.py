"""Record validation: the six fields, the enums, and the packet cross-checks.

Every record here uses toy case ids. No study case is ever given a label by
this suite.
"""

from __future__ import annotations

import pytest

from agentfailuretransfer.phase2 import Phase2Error
from agentfailuretransfer.phase2.packets import packet_evidence_ids
from agentfailuretransfer.phase2.paths import Phase2Paths
from agentfailuretransfer.phase2.review_records import (
    NON_STUDY_CASE_ID_PATTERN,
    dump_record,
    duplicate_case_ids,
    extension_for_reviewer,
    format_for_reviewer,
    parse_record,
    validate_case_file,
    validate_record,
)
from agentfailuretransfer.phase2.state import save_case
from phase2_fixtures import TOY_CASE_IDS, build_toy_root, toy_record

TOY_EVIDENCE = {
    "BUG_DIFF",
    "CODE_CONTEXT_01",
    "REFERENCE_REPAIR",
    "SPECIFICATION",
    "TEST_FAILURE_01",
}


@pytest.fixture
def toy(tmp_path):
    return Phase2Paths(build_toy_root(tmp_path / "toy"))


def check(record, **kwargs):
    kwargs.setdefault("case_id_pattern", NON_STUDY_CASE_ID_PATTERN)
    kwargs.setdefault("evidence_ids", TOY_EVIDENCE)
    return validate_record(record, **kwargs)


def test_a_well_formed_record_has_no_problems():
    assert check(toy_record("TOY_001")) == []


def test_unexpected_field_is_rejected():
    record = toy_record("TOY_001")
    record["confidence_notes"] = "extra"
    problems = check(record)
    assert any("unexpected field" in problem for problem in problems)


def test_missing_field_is_rejected():
    record = toy_record("TOY_001")
    del record["reasoning_summary"]
    assert any("missing required field: reasoning_summary" in p for p in check(record))


@pytest.mark.parametrize(
    "field,value",
    [
        ("odc_defect_type", "PERFORMANCE"),
        ("taxonomy_fit", "UNCLEAR"),
        ("pattern_confidence", "VERY_HIGH"),
    ],
)
def test_values_outside_the_frozen_enums_are_rejected(field, value):
    problems = check(toy_record("TOY_001", **{field: value}))
    assert any(field in problem for problem in problems)


def test_sentinel_requires_out_of_scope():
    problems = check(
        toy_record("TOY_001", odc_defect_type="UNCLASSIFIABLE", taxonomy_fit="DIRECT")
    )
    assert any("requires taxonomy_fit OUT_OF_SCOPE" in problem for problem in problems)


def test_out_of_scope_requires_the_sentinel():
    problems = check(
        toy_record("TOY_001", odc_defect_type="ALGORITHM", taxonomy_fit="OUT_OF_SCOPE")
    )
    assert any("requires odc_defect_type UNCLASSIFIABLE" in problem for problem in problems)


def test_the_consistent_sentinel_pair_is_accepted():
    assert (
        check(
            toy_record(
                "TOY_001",
                odc_defect_type="UNCLASSIFIABLE",
                taxonomy_fit="OUT_OF_SCOPE",
                supporting_evidence_ids=["TEST_FAILURE_01"],
            )
        )
        == []
    )


def test_evidence_ids_must_exist_in_the_packet():
    problems = check(toy_record("TOY_001", supporting_evidence_ids=["CODE_CONTEXT_09"]))
    assert any("not in the packet" in problem for problem in problems)


def test_evidence_ids_must_be_non_empty_and_unique():
    assert any("at least one" in p for p in check(toy_record("TOY_001", supporting_evidence_ids=[])))
    assert any(
        "duplicates" in p
        for p in check(toy_record("TOY_001", supporting_evidence_ids=["BUG_DIFF", "BUG_DIFF"]))
    )


@pytest.mark.parametrize("length", [0, 9, 2001])
def test_reasoning_summary_length_bounds(length):
    problems = check(toy_record("TOY_001", reasoning_summary="x" * length))
    assert any("reasoning_summary" in problem for problem in problems)


@pytest.mark.parametrize("length", [10, 2000])
def test_reasoning_summary_bounds_are_inclusive(length):
    assert check(toy_record("TOY_001", reasoning_summary="x" * length)) == []


def test_case_id_must_match_the_file_name():
    problems = check(toy_record("TOY_001"), filename="TOY_002.yaml")
    assert any("does not match the file name" in problem for problem in problems)


def test_case_id_must_be_one_of_the_frozen_cases():
    problems = check(toy_record("TOY_009"), expected_case_ids=TOY_CASE_IDS)
    assert any("not one of the frozen cases" in problem for problem in problems)


def test_study_pattern_rejects_a_toy_id():
    problems = validate_record(toy_record("TOY_001"), evidence_ids=TOY_EVIDENCE)
    assert any("does not match" in problem for problem in problems)


def test_duplicate_case_ids_are_detected():
    records = [toy_record("TOY_001"), toy_record("TOY_001"), toy_record("TOY_002")]
    assert duplicate_case_ids(records) == ["TOY_001"]


def test_each_reviewer_writes_its_own_serialization(toy):
    assert format_for_reviewer("claude") == "yaml"
    assert format_for_reviewer("codex") == "json"
    assert extension_for_reviewer("claude") == ".yaml"
    assert extension_for_reviewer("codex") == ".json"

    record = toy_record("TOY_001")
    for reviewer in ("claude", "codex"):
        path = save_case(toy, reviewer, record)
        assert path.suffix == extension_for_reviewer(reviewer)
        loaded = parse_record(path.read_text(encoding="utf-8"), format_for_reviewer(reviewer))
        assert loaded == record

    # Different bytes, identical semantics.
    claude_text = toy.reviewer_case_file("claude", "TOY_001").read_text(encoding="utf-8")
    codex_text = toy.reviewer_case_file("codex", "TOY_001").read_text(encoding="utf-8")
    assert claude_text != codex_text


def test_round_trip_preserves_the_canonical_field_order():
    for fmt in ("json", "yaml"):
        text = dump_record(toy_record("TOY_001"), fmt)
        assert list(parse_record(text, fmt)) == list(toy_record("TOY_001"))


def test_malformed_serialization_is_a_hard_failure():
    with pytest.raises(Phase2Error, match="not valid JSON"):
        parse_record("{not json", "json")
    with pytest.raises(Phase2Error, match="must be a mapping"):
        parse_record("- a\n- b\n", "yaml")


def test_validate_case_file_cross_checks_against_the_real_toy_packet(toy):
    save_case(toy, "claude", toy_record("TOY_001"))
    path = toy.reviewer_case_file("claude", "TOY_001")
    _, problems = validate_case_file(
        toy, "claude", path, case_id_pattern=NON_STUDY_CASE_ID_PATTERN,
        expected_case_ids=TOY_CASE_IDS,
    )
    assert problems == []
    assert packet_evidence_ids(toy, "TOY_001") == TOY_EVIDENCE


def test_a_record_for_a_case_with_no_packet_is_refused(toy):
    save_case(toy, "claude", toy_record("TOY_009"))
    path = toy.reviewer_case_file("claude", "TOY_009")
    _, problems = validate_case_file(
        toy, "claude", path, case_id_pattern=NON_STUDY_CASE_ID_PATTERN
    )
    assert any("no frozen packet" in problem for problem in problems)
