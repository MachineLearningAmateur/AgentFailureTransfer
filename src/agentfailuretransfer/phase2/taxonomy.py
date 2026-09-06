"""The frozen ODC Defect Type rubric, loaded and checked.

Only the **Defect Type** dimension of Orthogonal Defect Classification is used
(Chillarege et al., IEEE TSE 18(11):943-956, 1992, DOI 10.1109/32.177364).
The eight ids below are the canonical ODC defect types. ``UNCLASSIFIABLE`` is a
study-level sentinel and is *not* an ODC defect type; the rubric marks it
``canonical: false`` and this module keeps it out of :data:`CANONICAL_DEFECT_TYPES`.

Nothing here decides which type a defect is. The module loads the YAML, checks
that the file still says what the protocol froze, and computes the fingerprint
that every seal records.

The taxonomy fingerprint
------------------------

:func:`taxonomy_fingerprint` is the SHA-256, over UTF-8, of the text::

    <sha256 of taxonomy/odc_defect_type_v1.yaml>:<sha256 of schemas/odc_review_result.schema.json>

that is, the two hex digests joined by a single ``:`` with no whitespace and no
trailing newline. Two files, because the rubric alone does not pin the record
contract: a reviewer who classified against these definitions also serialised
against that schema, and a change to either invalidates the comparison. The
prose rubric (``odc_defect_type_v1.md``) is deliberately *not* in the
fingerprint -- it is covered by the freeze manifest, and wording refinements to
the prose must not silently void a review whose machine-readable contract is
unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentfailuretransfer.hashing import sha256_bytes, sha256_file
from agentfailuretransfer.phase2 import Phase2Error

TAXONOMY_ID = "odc_defect_type_v1"

#: The eight canonical ODC Defect Types, in the order the protocol froze them.
CANONICAL_DEFECT_TYPES: tuple[str, ...] = (
    "FUNCTION",
    "INTERFACE",
    "CHECKING",
    "ASSIGNMENT",
    "TIMING_SERIALIZATION",
    "BUILD_PACKAGE_MERGE",
    "DOCUMENTATION",
    "ALGORITHM",
)

#: Study-level sentinel. NOT an ODC defect type. Recorded when none of the
#: eight can defensibly describe the observed defect; it is data about
#: taxonomy applicability, never a reviewer failure.
SENTINEL_DEFECT_TYPE = "UNCLASSIFIABLE"

#: The full ``odc_defect_type`` enum: the eight canonical types plus sentinel.
DEFECT_TYPES: tuple[str, ...] = CANONICAL_DEFECT_TYPES + (SENTINEL_DEFECT_TYPE,)

TAXONOMY_FITS: tuple[str, ...] = ("DIRECT", "AMBIGUOUS", "OUT_OF_SCOPE")
OUT_OF_SCOPE = "OUT_OF_SCOPE"

PATTERN_CONFIDENCES: tuple[str, ...] = ("HIGH", "MEDIUM", "LOW")

EXPECTED_CANONICAL_COUNT = 8


@dataclass(frozen=True)
class OdcTaxonomy:
    """The loaded rubric, reduced to the things the tooling enforces."""

    taxonomy_id: str
    dimension: str
    canonical_ids: tuple[str, ...]
    sentinel_id: str
    taxonomy_fits: tuple[str, ...]
    pattern_confidences: tuple[str, ...]
    definitions: dict[str, str]
    source: dict[str, Any]
    path: Path

    @property
    def defect_types(self) -> tuple[str, ...]:
        return self.canonical_ids + (self.sentinel_id,)

    def is_canonical(self, defect_type: str) -> bool:
        return defect_type in self.canonical_ids


def _as_str(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Phase2Error(f"{where}: expected a non-empty string, got {value!r}")
    return value


def load_taxonomy(path: Path | str) -> OdcTaxonomy:
    """Load ``odc_defect_type_v1.yaml`` and check its frozen structure.

    Raises :class:`Phase2Error` if the file no longer matches what the protocol
    froze: a different taxonomy id, a different number of canonical types, a
    canonical flag flipped, the sentinel claimed as canonical, or an enum that
    disagrees with this module's constants. Paraphrase wording may change (the
    prose is the docs' business); ids, flags and enums may not.
    """
    path = Path(path)
    if not path.is_file():
        raise Phase2Error(f"frozen ODC rubric not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise Phase2Error(f"{path}: not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise Phase2Error(f"{path}: the rubric must be a YAML mapping")

    taxonomy_id = _as_str(data.get("taxonomy_id"), f"{path}: taxonomy_id")
    if taxonomy_id != TAXONOMY_ID:
        raise Phase2Error(
            f"{path}: taxonomy_id is {taxonomy_id!r}, expected {TAXONOMY_ID!r}"
        )

    entries = data.get("defect_types")
    if not isinstance(entries, list) or not entries:
        raise Phase2Error(f"{path}: defect_types must be a non-empty list")

    canonical: list[str] = []
    definitions: dict[str, str] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise Phase2Error(f"{path}: defect_types[{index}] must be a mapping")
        identifier = _as_str(entry.get("id"), f"{path}: defect_types[{index}].id")
        if entry.get("canonical") is not True:
            raise Phase2Error(
                f"{path}: defect_types[{index}] ({identifier}) must be marked "
                "canonical: true -- the eight ODC defect types are canonical and "
                "the sentinel belongs under `sentinel:`, not in this list"
            )
        if identifier in definitions:
            raise Phase2Error(f"{path}: duplicate defect type id {identifier!r}")
        canonical.append(identifier)
        definitions[identifier] = _as_str(
            entry.get("definition"), f"{path}: defect_types[{index}].definition"
        )

    if len(canonical) != EXPECTED_CANONICAL_COUNT:
        raise Phase2Error(
            f"{path}: {len(canonical)} canonical defect types, expected "
            f"{EXPECTED_CANONICAL_COUNT}. The ODC Defect Type dimension is frozen; "
            "adding or removing a type is a new taxonomy, not an edit."
        )
    if tuple(canonical) != CANONICAL_DEFECT_TYPES:
        raise Phase2Error(
            f"{path}: canonical defect types {canonical} do not match the frozen "
            f"list {list(CANONICAL_DEFECT_TYPES)} (order is part of the freeze)"
        )

    sentinel = data.get("sentinel")
    if not isinstance(sentinel, dict):
        raise Phase2Error(f"{path}: `sentinel` must be a mapping")
    sentinel_id = _as_str(sentinel.get("id"), f"{path}: sentinel.id")
    if sentinel_id != SENTINEL_DEFECT_TYPE:
        raise Phase2Error(
            f"{path}: sentinel id is {sentinel_id!r}, expected "
            f"{SENTINEL_DEFECT_TYPE!r}"
        )
    if sentinel.get("canonical") is not False:
        raise Phase2Error(
            f"{path}: the sentinel must be marked canonical: false. "
            f"{SENTINEL_DEFECT_TYPE} is a study-level addition and is not an ODC "
            "defect type; recording it as canonical would misattribute it to ODC."
        )
    if sentinel_id in canonical:
        raise Phase2Error(f"{path}: the sentinel must not also be a defect type")

    fits = _enum_ids(data.get("taxonomy_fit"), f"{path}: taxonomy_fit")
    if tuple(fits) != TAXONOMY_FITS:
        raise Phase2Error(
            f"{path}: taxonomy_fit values {fits} do not match the frozen "
            f"{list(TAXONOMY_FITS)}"
        )
    confidences = _enum_ids(data.get("pattern_confidence"), f"{path}: pattern_confidence")
    if tuple(confidences) != PATTERN_CONFIDENCES:
        raise Phase2Error(
            f"{path}: pattern_confidence values {confidences} do not match the "
            f"frozen {list(PATTERN_CONFIDENCES)}"
        )

    source = data.get("source")
    if not isinstance(source, dict) or not source.get("doi"):
        raise Phase2Error(
            f"{path}: `source` must record the canonical ODC publication, "
            "including its DOI"
        )

    return OdcTaxonomy(
        taxonomy_id=taxonomy_id,
        dimension=str(data.get("dimension", "")),
        canonical_ids=tuple(canonical),
        sentinel_id=sentinel_id,
        taxonomy_fits=tuple(fits),
        pattern_confidences=tuple(confidences),
        definitions=definitions,
        source=source,
        path=path,
    )


def _enum_ids(value: Any, where: str) -> list[str]:
    """Read an enum written either as bare strings or as ``{id, definition}``."""
    if not isinstance(value, list) or not value:
        raise Phase2Error(f"{where}: expected a non-empty list")
    out: list[str] = []
    for index, item in enumerate(value):
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            out.append(_as_str(item.get("id"), f"{where}[{index}].id"))
        else:
            raise Phase2Error(f"{where}[{index}]: expected a string or a mapping")
    return out


def taxonomy_fingerprint(taxonomy_yaml: Path | str, schema: Path | str) -> str:
    """One hash covering the frozen rubric and the frozen record contract.

    See the module docstring for the exact construction.
    """
    taxonomy_yaml = Path(taxonomy_yaml)
    schema = Path(schema)
    for path, what in ((taxonomy_yaml, "ODC rubric"), (schema, "review-result schema")):
        if not path.is_file():
            raise Phase2Error(f"cannot fingerprint: the {what} is missing at {path}")
    joined = f"{sha256_file(taxonomy_yaml)}:{sha256_file(schema)}"
    return sha256_bytes(joined.encode("utf-8"))


#: Human-readable description of the fingerprint, emitted into artifacts so the
#: construction never has to be reverse-engineered from a hex string.
FINGERPRINT_ALGORITHM = (
    "sha256(utf8( sha256(taxonomy/odc_defect_type_v1.yaml) + ':' + "
    "sha256(schemas/odc_review_result.schema.json) ))"
)
