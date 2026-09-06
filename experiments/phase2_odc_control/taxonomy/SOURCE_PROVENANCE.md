# Source provenance for the Phase 2 external taxonomy

The taxonomy used in the Phase 2 control is not ours. This file records exactly what it is,
where it comes from, which part of it is used, and which parts are deliberately not used.

## Citation

> Ram Chillarege, Inderpal S. Bhandari, Jarir K. Chaar, Michael J. Halliday, Diane S. Moebus,
> Bonnie K. Ray, and Man-Yuen Wong. "Orthogonal Defect Classification — A Concept for
> In-Process Measurements." *IEEE Transactions on Software Engineering*, 18(11):943–956, 1992.

- DOI: `10.1109/32.177364`
- IBM Research page:
  <https://research.ibm.com/publications/orthogonal-defect-classificationa-concept-for-in-process-measurements>

## Which dimension is used

**Only the ODC Defect Type dimension.** The eight canonical defect types are `FUNCTION`,
`INTERFACE`, `CHECKING`, `ASSIGNMENT`, `TIMING_SERIALIZATION`, `BUILD_PACKAGE_MERGE`,
`DOCUMENTATION` and `ALGORITHM`, reproduced as paraphrases in
[`odc_defect_type_v1.md`](odc_defect_type_v1.md) and
[`odc_defect_type_v1.yaml`](odc_defect_type_v1.yaml).

## Which dimensions are excluded

ODC is a multi-dimensional scheme developed for in-process software measurement. The following
dimensions are **not** used, are not recorded, and are not shown to reviewers:

- defect trigger;
- development activity;
- impact;
- source;
- age;
- every other ODC process attribute.

Those dimensions carry process information about how and when a defect was found or introduced.
The Phase 2 control does not need that information, and collecting it would reintroduce exactly
the kind of process-dependence the control is designed to remove.

## The study-level sentinel

`UNCLASSIFIABLE` is an addition made by this study. It is **not** an ODC defect type and must
never be described as one. It is recorded as `canonical: false` in the YAML so that no tool or
reader can mistake it for part of the published scheme. See `odc_defect_type_v1.md` for its
rules.

## The tie-break guidance is ours

The nine numbered tie-break rules in the rubric are this study's **operationalisation** of the
published defect types, frozen before any reviewer sees a Phase 2 packet. They are not a
modification of ODC, not an extension of it, and not attributable to the cited authors. They
resolve ambiguity in a stated, reproducible way; they do not add, remove or redefine a defect
type.

## Setup may consult the publication; review may not

The **setup phase** — writing this rubric, the protocol and the reviewer prompts — may consult
the canonical publication and its descriptions of the Defect Type dimension.

The **review phase** may not. Reviewers work from the frozen rubric in the bundle and have no
web access during review. This is not a formality: if one reviewer consulted a later ODC
revision, a tutorial, or a vendor adaptation while the other did not, the two reviewers would be
applying different instruments, and the agreement number would measure that difference rather
than the taxonomy. See [`../protocol/blinding_protocol.md`](../protocol/blinding_protocol.md).

## Why this source is a usable external control

ODC was published in 1992. It predates large language models, coding agents, SWE-smith and
AIDev, and it was not derived from this study, from either source study, or from any of the 100
cases under review. Nothing about it could have been fitted to the Phase 1 result, because
neither existed when it was written.

That is the whole of the claim being made for it. ODC is not asserted here to be ground truth,
a complete taxonomy of software defects, or the correct instrument for classifying modern
repair tasks. It is an independent, pre-existing, mechanism-neutral scheme, which is what a
control requires. See [`../protocol/external_taxonomy_selection.md`](../protocol/external_taxonomy_selection.md)
for the selection rationale and its limits.
