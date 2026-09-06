"""The frozen ODC rubric, the sentinel, and the schema/code enum agreement.

These tests check the *structure* of the taxonomy, never a scientific outcome:
nothing here asserts how any case should be classified, or what any agreement
figure should be.
"""

from __future__ import annotations

import json

import pytest
import yaml

from agentfailuretransfer import paths as repo_paths
from agentfailuretransfer.hashing import sha256_bytes, sha256_file
from agentfailuretransfer.phase2 import Phase2Error
from agentfailuretransfer.phase2 import taxonomy as odc
from agentfailuretransfer.phase2.review_records import (
    PATTERN_CONFIDENCES,
    REASONING_MAX_CHARS,
    REASONING_MIN_CHARS,
    REVIEW_FIELDS,
    STUDY_CASE_ID_PATTERN,
    load_schema,
    schema_enum,
)


@pytest.fixture(scope="module")
def rubric():
    if not repo_paths.PHASE2_TAXONOMY_YAML.is_file():
        pytest.skip("the frozen ODC rubric has not been created yet")
    return odc.load_taxonomy(repo_paths.PHASE2_TAXONOMY_YAML)


@pytest.fixture(scope="module")
def schema():
    return load_schema(repo_paths.PHASE2_SCHEMA)


def test_exactly_eight_canonical_defect_types(rubric):
    assert len(rubric.canonical_ids) == 8
    assert len(set(rubric.canonical_ids)) == 8
    assert rubric.canonical_ids == odc.CANONICAL_DEFECT_TYPES


def test_unclassifiable_is_a_research_sentinel_not_canonical_odc(rubric):
    assert rubric.sentinel_id == "UNCLASSIFIABLE"
    assert rubric.sentinel_id not in rubric.canonical_ids
    assert not rubric.is_canonical(rubric.sentinel_id)
    raw = yaml.safe_load(repo_paths.PHASE2_TAXONOMY_YAML.read_text(encoding="utf-8"))
    assert raw["sentinel"]["canonical"] is False
    assert all(entry["canonical"] is True for entry in raw["defect_types"])


def test_only_the_defect_type_dimension_is_used(rubric):
    assert rubric.dimension == "defect_type"
    raw = yaml.safe_load(repo_paths.PHASE2_TAXONOMY_YAML.read_text(encoding="utf-8"))
    excluded = set(raw["dimensions_excluded"])
    assert {"defect_trigger", "development_activity", "impact", "source", "age"} <= excluded


def test_the_rubric_cites_the_canonical_odc_publication(rubric):
    assert rubric.source["doi"] == "10.1109/32.177364"
    assert rubric.source["year"] == 1992


def test_code_enums_match_the_schema_file(schema):
    """The schema is the documented contract; the code is the enforcement."""
    assert schema_enum(schema, "odc_defect_type") == list(odc.DEFECT_TYPES)
    assert schema_enum(schema, "taxonomy_fit") == list(odc.TAXONOMY_FITS)
    assert schema_enum(schema, "pattern_confidence") == list(PATTERN_CONFIDENCES)
    assert schema["properties"]["case_id"]["pattern"] == STUDY_CASE_ID_PATTERN
    reasoning = schema["properties"]["reasoning_summary"]
    assert reasoning["minLength"] == REASONING_MIN_CHARS
    assert reasoning["maxLength"] == REASONING_MAX_CHARS


def test_schema_declares_exactly_the_six_fields_and_forbids_extras(schema):
    assert schema["additionalProperties"] is False
    assert sorted(schema["required"]) == sorted(REVIEW_FIELDS)
    assert sorted(schema["properties"]) == sorted(REVIEW_FIELDS)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_schema_enforces_the_sentinel_rule_in_both_directions(schema):
    conditions = [
        (
            clause["if"]["properties"],
            clause["then"]["properties"],
        )
        for clause in schema["allOf"]
    ]
    assert (
        {"odc_defect_type": {"const": "UNCLASSIFIABLE"}},
        {"taxonomy_fit": {"const": "OUT_OF_SCOPE"}},
    ) in conditions
    assert (
        {"taxonomy_fit": {"const": "OUT_OF_SCOPE"}},
        {"odc_defect_type": {"const": "UNCLASSIFIABLE"}},
    ) in conditions


def test_supporting_evidence_ids_must_be_non_empty_and_unique(schema):
    field = schema["properties"]["supporting_evidence_ids"]
    assert field["type"] == "array"
    assert field["minItems"] == 1
    assert field["uniqueItems"] is True
    assert field["items"]["minLength"] == 1


def test_case_id_pattern_admits_exactly_the_hundred_study_ids():
    import re

    pattern = re.compile(STUDY_CASE_ID_PATTERN)
    accepted = [f"SWESMITH_{index:03d}" for index in range(1, 101)]
    assert all(pattern.fullmatch(case_id) for case_id in accepted)
    for rejected in ("SWESMITH_000", "SWESMITH_101", "SWESMITH_0001", "SWESMITH_01", "TOY_001"):
        assert not pattern.fullmatch(rejected)


def test_taxonomy_fingerprint_is_the_documented_two_file_hash():
    fingerprint = odc.taxonomy_fingerprint(
        repo_paths.PHASE2_TAXONOMY_YAML, repo_paths.PHASE2_SCHEMA
    )
    expected = sha256_bytes(
        (
            f"{sha256_file(repo_paths.PHASE2_TAXONOMY_YAML)}:"
            f"{sha256_file(repo_paths.PHASE2_SCHEMA)}"
        ).encode("utf-8")
    )
    assert fingerprint == expected
    assert len(fingerprint) == 64


def test_taxonomy_fingerprint_changes_when_either_input_changes(tmp_path):
    rubric = tmp_path / "rubric.yaml"
    schema = tmp_path / "schema.json"
    rubric.write_text("a: 1\n", encoding="utf-8")
    schema.write_text("{}\n", encoding="utf-8")
    before = odc.taxonomy_fingerprint(rubric, schema)
    schema.write_text("{ }\n", encoding="utf-8")
    assert odc.taxonomy_fingerprint(rubric, schema) != before
    schema.write_text("{}\n", encoding="utf-8")
    assert odc.taxonomy_fingerprint(rubric, schema) == before


def test_a_rubric_with_seven_types_is_refused(tmp_path):
    raw = yaml.safe_load(repo_paths.PHASE2_TAXONOMY_YAML.read_text(encoding="utf-8"))
    raw["defect_types"] = raw["defect_types"][:-1]
    path = tmp_path / "seven.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(Phase2Error, match="canonical defect types"):
        odc.load_taxonomy(path)


def test_a_sentinel_claimed_as_canonical_odc_is_refused(tmp_path):
    raw = yaml.safe_load(repo_paths.PHASE2_TAXONOMY_YAML.read_text(encoding="utf-8"))
    raw["sentinel"]["canonical"] = True
    path = tmp_path / "bad_sentinel.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(Phase2Error, match="canonical: false"):
        odc.load_taxonomy(path)


def test_a_reordered_type_list_is_refused(tmp_path):
    raw = yaml.safe_load(repo_paths.PHASE2_TAXONOMY_YAML.read_text(encoding="utf-8"))
    raw["defect_types"] = list(reversed(raw["defect_types"]))
    path = tmp_path / "reordered.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(Phase2Error, match="do not match the frozen list"):
        odc.load_taxonomy(path)


def test_the_schema_file_is_valid_json_and_self_describing():
    text = repo_paths.PHASE2_SCHEMA.read_text(encoding="utf-8")
    assert json.loads(text)["title"]
