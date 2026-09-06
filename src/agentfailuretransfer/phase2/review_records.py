"""One reviewer record: parse it, and check it against the frozen contract.

The contract of record is ``schemas/odc_review_result.schema.json`` (JSON
Schema draft 2020-12). It is *not* evaluated by a JSON Schema library: this
repository adds no dependency for it. Instead every rule in that file is
implemented here in plain Python, and
``tests/test_phase2_review_records.py::test_code_enums_match_the_schema_file``
asserts that the enum lists, the case-id pattern and the length bounds in this
module are exactly the ones in the schema. The schema stays the documented,
tool-readable contract; the code stays the enforcement. They cannot drift apart
without a test failing.

Six fields, no more and no fewer::

    case_id                  the neutral frozen case id
    odc_defect_type          one of the eight ODC types, or the sentinel
    taxonomy_fit             DIRECT | AMBIGUOUS | OUT_OF_SCOPE
    pattern_confidence       HIGH | MEDIUM | LOW  (descriptive only)
    supporting_evidence_ids  non-empty, unique, all present in the packet
    reasoning_summary        10..2000 characters

and the two-way rule ``UNCLASSIFIABLE <-> OUT_OF_SCOPE``: the sentinel requires
the out-of-scope fit, and the out-of-scope fit requires the sentinel.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Sequence

import yaml

from agentfailuretransfer.phase2 import Phase2Error
from agentfailuretransfer.phase2.paths import (
    REVIEWER_FORMATS,
    Phase2Paths,
    require_reviewer,
)
from agentfailuretransfer.phase2.taxonomy import (
    DEFECT_TYPES,
    OUT_OF_SCOPE,
    PATTERN_CONFIDENCES,
    SENTINEL_DEFECT_TYPE,
    TAXONOMY_FITS,
)

#: The canonical field order. Every writer emits this order, so two records
#: differ only where their content differs.
REVIEW_FIELDS: tuple[str, ...] = (
    "case_id",
    "odc_defect_type",
    "taxonomy_fit",
    "pattern_confidence",
    "supporting_evidence_ids",
    "reasoning_summary",
)

REASONING_MIN_CHARS = 10
REASONING_MAX_CHARS = 2000

#: The study case-id pattern, identical to the schema's.
STUDY_CASE_ID_PATTERN = r"^SWESMITH_(0(0[1-9]|[1-9][0-9])|100)$"

#: A deliberately weaker pattern for a rehearsal root whose case ids are not
#: study cases (``TOY_001`` and the like). Never used on the study corpus: the
#: callers select it only when the root's own snapshot manifest lists
#: non-study ids, and they say so loudly when they do.
NON_STUDY_CASE_ID_PATTERN = r"^[A-Z][A-Z0-9]*_[0-9]{3}$"

_EXTENSIONS = {"json": ".json", "yaml": ".yaml"}


def format_for_reviewer(reviewer: str) -> str:
    return REVIEWER_FORMATS[require_reviewer(reviewer)]


def extension_for_reviewer(reviewer: str) -> str:
    return _EXTENSIONS[format_for_reviewer(reviewer)]


def ordered(record: dict[str, Any]) -> dict[str, Any]:
    """The record in canonical field order; anything unexpected stays visible."""
    out = {key: record[key] for key in REVIEW_FIELDS if key in record}
    out.update({key: value for key, value in record.items() if key not in out})
    return out


def dump_record(record: dict[str, Any], fmt: str) -> str:
    """Serialise one record in the reviewer's format."""
    if fmt == "json":
        return json.dumps(ordered(record), indent=2, ensure_ascii=False) + "\n"
    if fmt == "yaml":
        return yaml.safe_dump(
            ordered(record),
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
            width=88,
        )
    raise Phase2Error(f"unknown record format {fmt!r}")


def parse_record(text: str, fmt: str, *, where: str = "record") -> dict[str, Any]:
    """Parse one record from JSON (codex) or YAML (claude)."""
    if fmt == "json":
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise Phase2Error(f"{where}: not valid JSON: {exc}") from exc
    elif fmt == "yaml":
        try:
            value = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise Phase2Error(f"{where}: not valid YAML: {exc}") from exc
    else:
        raise Phase2Error(f"unknown record format {fmt!r}")
    if not isinstance(value, dict):
        raise Phase2Error(f"{where}: a review record must be a mapping/object")
    return value


def load_case_file(path: Path | str, reviewer: str) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise Phase2Error(f"{path} does not exist")
    return parse_record(
        path.read_text(encoding="utf-8"), format_for_reviewer(reviewer), where=str(path)
    )


def case_id_of_filename(name: str) -> str:
    return Path(name).stem


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------
def validate_record(
    record: Any,
    *,
    case_id_pattern: str = STUDY_CASE_ID_PATTERN,
    evidence_ids: Iterable[str] | None = None,
    expected_case_ids: Iterable[str] | None = None,
    filename: str | None = None,
) -> list[str]:
    """Every schema rule plus the packet cross-checks. Returns problem strings.

    ``evidence_ids`` is the cited-evidence universe from that case's frozen
    packet; when given, every cited id must be in it. ``expected_case_ids``
    restricts the case id to the frozen sample. ``filename`` requires the
    record's ``case_id`` to equal the file's stem.
    """
    problems: list[str] = []
    if not isinstance(record, dict):
        return ["a review record must be a mapping/object"]

    # -- shape: exactly the six fields (additionalProperties: false) --------
    missing = [field for field in REVIEW_FIELDS if field not in record]
    for field in missing:
        problems.append(f"missing required field: {field}")
    unexpected = [key for key in record if key not in REVIEW_FIELDS]
    for key in sorted(unexpected):
        problems.append(
            f"unexpected field: {key!r} (the record contract is exactly "
            f"{list(REVIEW_FIELDS)})"
        )

    # -- case_id ------------------------------------------------------------
    case_id = record.get("case_id")
    if "case_id" in record:
        if not isinstance(case_id, str):
            problems.append("case_id must be a string")
        elif not re.fullmatch(case_id_pattern, case_id):
            problems.append(f"case_id {case_id!r} does not match {case_id_pattern}")
        elif expected_case_ids is not None and case_id not in set(expected_case_ids):
            problems.append(f"case_id {case_id!r} is not one of the frozen cases")
        if isinstance(case_id, str) and filename is not None:
            stem = case_id_of_filename(filename)
            if case_id != stem:
                problems.append(
                    f"case_id {case_id!r} does not match the file name {filename!r}"
                )

    # -- enums ---------------------------------------------------------------
    defect_type = record.get("odc_defect_type")
    if "odc_defect_type" in record and defect_type not in DEFECT_TYPES:
        problems.append(
            f"odc_defect_type {defect_type!r} is not one of {list(DEFECT_TYPES)}"
        )
    fit = record.get("taxonomy_fit")
    if "taxonomy_fit" in record and fit not in TAXONOMY_FITS:
        problems.append(f"taxonomy_fit {fit!r} is not one of {list(TAXONOMY_FITS)}")
    confidence = record.get("pattern_confidence")
    if "pattern_confidence" in record and confidence not in PATTERN_CONFIDENCES:
        problems.append(
            f"pattern_confidence {confidence!r} is not one of "
            f"{list(PATTERN_CONFIDENCES)}"
        )

    # -- the two-way sentinel rule -------------------------------------------
    if defect_type == SENTINEL_DEFECT_TYPE and fit != OUT_OF_SCOPE:
        problems.append(
            f"odc_defect_type {SENTINEL_DEFECT_TYPE} requires taxonomy_fit "
            f"{OUT_OF_SCOPE}, got {fit!r}"
        )
    if fit == OUT_OF_SCOPE and defect_type != SENTINEL_DEFECT_TYPE:
        problems.append(
            f"taxonomy_fit {OUT_OF_SCOPE} requires odc_defect_type "
            f"{SENTINEL_DEFECT_TYPE}, got {defect_type!r}"
        )

    # -- supporting_evidence_ids ----------------------------------------------
    cited = record.get("supporting_evidence_ids")
    if "supporting_evidence_ids" in record:
        if not isinstance(cited, list) or isinstance(cited, (str, bytes)):
            problems.append("supporting_evidence_ids must be an array")
        elif not cited:
            problems.append("supporting_evidence_ids must cite at least one evidence id")
        else:
            if any(not isinstance(item, str) or not item for item in cited):
                problems.append(
                    "supporting_evidence_ids must contain non-empty strings only"
                )
            elif len(set(cited)) != len(cited):
                duplicates = sorted({item for item in cited if cited.count(item) > 1})
                problems.append(
                    f"supporting_evidence_ids contains duplicates: {duplicates}"
                )
            if evidence_ids is not None:
                available = set(evidence_ids)
                unknown = sorted(
                    {item for item in cited if isinstance(item, str)} - available
                )
                if unknown:
                    problems.append(
                        f"supporting_evidence_ids cites ids that are not in the "
                        f"packet: {unknown}; available: {sorted(available)}"
                    )

    # -- reasoning_summary ------------------------------------------------------
    reasoning = record.get("reasoning_summary")
    if "reasoning_summary" in record:
        if not isinstance(reasoning, str):
            problems.append("reasoning_summary must be a string")
        elif not REASONING_MIN_CHARS <= len(reasoning) <= REASONING_MAX_CHARS:
            problems.append(
                f"reasoning_summary is {len(reasoning)} characters; the contract is "
                f"{REASONING_MIN_CHARS}..{REASONING_MAX_CHARS}"
            )

    return problems


def duplicate_case_ids(records: Sequence[dict[str, Any]]) -> list[str]:
    """Reuses the Phase 1 helper so 'duplicate' means one thing in this repo."""
    from agentfailuretransfer.reviews import duplicate_case_ids as _duplicates

    return _duplicates(record for record in records if isinstance(record.get("case_id"), str))


def validate_case_file(
    paths: Phase2Paths,
    reviewer: str,
    path: Path,
    *,
    case_id_pattern: str = STUDY_CASE_ID_PATTERN,
    expected_case_ids: Iterable[str] | None = None,
    check_packet: bool = True,
) -> tuple[dict[str, Any], list[str]]:
    """Load and validate one case file, including the packet cross-check."""
    from agentfailuretransfer.phase2.packets import packet_evidence_ids

    record = load_case_file(path, reviewer)
    evidence: set[str] | None = None
    if check_packet and isinstance(record.get("case_id"), str):
        try:
            evidence = packet_evidence_ids(paths, record["case_id"])
        except Phase2Error as exc:
            return record, [str(exc)]
    problems = validate_record(
        record,
        case_id_pattern=case_id_pattern,
        evidence_ids=evidence,
        expected_case_ids=expected_case_ids,
        filename=path.name,
    )
    return record, problems


# ---------------------------------------------------------------------------
# the schema file, read back as the documented contract
# ---------------------------------------------------------------------------
def load_schema(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise Phase2Error(f"the review-result schema is missing: {path}")
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase2Error(f"{path}: not valid JSON: {exc}") from exc
    if not isinstance(schema, dict):
        raise Phase2Error(f"{path}: a JSON Schema must be an object")
    return schema


def schema_enum(schema: dict[str, Any], field: str) -> list[str]:
    try:
        return list(schema["properties"][field]["enum"])
    except (KeyError, TypeError) as exc:
        raise Phase2Error(f"the schema declares no enum for {field!r}") from exc
