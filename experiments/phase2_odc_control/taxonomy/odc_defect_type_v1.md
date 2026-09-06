# Frozen ODC Defect Type rubric — `odc_defect_type_v1`

This is the complete rubric for the Phase 2 external-taxonomy control. A reviewer reads
this file in full, once, before classifying any case, and consults nothing else about ODC.

The machine-readable form is [`odc_defect_type_v1.yaml`](odc_defect_type_v1.yaml) in this
directory. The two files are kept in exact agreement on identifiers, definitions and rule
order; the YAML is what the tooling reads, this file is what a reviewer reads. If they ever
disagree, that is a defect in the freeze and must be reported, not resolved by preference.

Provenance and citation are in [`SOURCE_PROVENANCE.md`](SOURCE_PROVENANCE.md).

## Scope

Only the **Defect Type** dimension of Orthogonal Defect Classification is used. Defect
Trigger, development activity, impact, source, age and every other ODC process attribute are
deliberately excluded; they would introduce process information the control does not need.

The eight defect types below are the canonical ODC defect types, paraphrased. `UNCLASSIFIABLE`
is a study-level sentinel and is **not** an ODC defect type.

## The operational question

For each case, ask exactly this:

> What kind of software correction is required to repair the observed defect?

ODC Defect Type is based on the semantics of the defect and of its correction. It is not based
on how the defect got there, and not on anyone's intent.

## The eight ODC Defect Types

### FUNCTION

A defect affecting a significant capability, feature, or high-level behavior whose correction
requires a substantial design-level functional change rather than only a local implementation
repair.

### INTERFACE

A defect in interaction between modules, components, APIs, users, external systems, calls,
parameters, control structures between components, or other software boundaries.

### CHECKING

A defect in validation or checking of data/values before or during use, including missing or
incorrect guards, validation conditions, range checks, or related checking logic.

### ASSIGNMENT

A defect involving an incorrect, missing, or inappropriate value assignment or initialization,
generally localized to a small amount of code.

### TIMING_SERIALIZATION

A defect involving timing, ordering, synchronization, concurrency, serialization, or management
of shared/real-time resources.

### BUILD_PACKAGE_MERGE

A defect involving build systems, packaging, library/version management, merging, configuration
of shipped components, or change-management integration.

### DOCUMENTATION

A defect whose primary correction is to documentation or maintenance/publication material rather
than executable program behavior.

### ALGORITHM

A correctness or efficiency defect in an algorithm or local data structure whose correction can
be made by changing the implementation without requiring a major formal design change.

## The `UNCLASSIFIABLE` sentinel

ODC itself defines the eight defect types above and no more. For this experiment one
**study-level sentinel** is added:

```text
UNCLASSIFIABLE
```

It is **not** claimed to be an ODC defect type. Use it only when none of the eight ODC Defect
Types can defensibly describe the observed defect from the provided evidence.

The sentinel exists so that forced classification cannot artificially inflate apparent taxonomy
coverage. Choosing it is not a reviewer failure; it is data about how far the taxonomy reaches.

## `taxonomy_fit`

Every record also carries `taxonomy_fit`, with exactly three allowed values:

| Value | Meaning |
| --- | --- |
| `DIRECT` | One ODC type clearly fits. |
| `AMBIGUOUS` | More than one ODC type is plausible, but the reviewer selects the best primary type. |
| `OUT_OF_SCOPE` | None of the eight types can be defensibly assigned; `odc_defect_type` must be `UNCLASSIFIABLE`. |

The consistency rule holds in both directions:

- `odc_defect_type: UNCLASSIFIABLE` requires `taxonomy_fit: OUT_OF_SCOPE`;
- `taxonomy_fit: OUT_OF_SCOPE` requires `odc_defect_type: UNCLASSIFIABLE`.

No other combination is valid, and the validator rejects it.

## Evidence rules

Classify from the frozen evidence in the packet, and from nothing else:

- `BUG_DIFF`;
- `CODE_CONTEXT_NN` — the code context supplied with the case;
- `SPECIFICATION`;
- `TEST_FAILURE_NN` — the failing-test evidence;
- `REFERENCE_REPAIR`.

For these cases specifically:

> BUG_DIFF introduces the bug. REFERENCE_REPAIR reverses it.

The reference repair is the exact reverse of the mutation and restores the prior working state.
It is therefore direct evidence of what the correction *is*, which is what the operational
question asks about.

> Do not classify what the synthetic bug generator "thought" or "intended." ODC Defect Type
> concerns the software defect and the semantics of the correction.

The generator is not an agent with intentions, beliefs, diagnoses, or verification behavior. Do
not infer why the bug was made, do not reason about how it was generated, and do not treat the
shape of a diff as evidence of a generation mechanism. Classify the software defect and
correction semantics only.

Cite only evidence IDs that the packet actually lists. Keep `reasoning_summary` short and
grounded in the cited evidence; it is a justification, not a transcript, and it must not record
private chain-of-thought.

## Tie-breaking guidance

This guidance is frozen before any reviewer sees a Phase 2 packet. It is **this study's
operationalisation of the published ODC types, not a modification of ODC**. It exists so that
two reviewers facing the same genuinely ambiguous case resolve it the same way for a stated
reason rather than by private preference.

Apply the rules in order. The first rule that applies decides the primary type.

1. If the defect is fundamentally about build/version/package/merge state, prefer
   `BUILD_PACKAGE_MERGE`.
2. If it is fundamentally about timing, concurrency, synchronization, or shared-resource
   ordering, prefer `TIMING_SERIALIZATION`.
3. If it is fundamentally about communication across a software boundary/API/component
   interface, prefer `INTERFACE`.
4. If the direct correction is a missing or incorrect assignment/initialization, prefer
   `ASSIGNMENT`.
5. If the direct correction is validation/checking/guard logic, prefer `CHECKING`.
6. If the defect requires a local algorithm/data-structure implementation correction, prefer
   `ALGORITHM`.
7. Reserve `FUNCTION` for significant capability or design-level functional defects rather than
   ordinary local implementation mistakes.
8. Use `DOCUMENTATION` only when documentation itself is the primary defective artifact.
9. If none can be defended, use `UNCLASSIFIABLE`.

Using rule 1–8 to resolve a genuine two-way ambiguity means `taxonomy_fit: AMBIGUOUS`, not
`DIRECT`. Reaching rule 9 means `odc_defect_type: UNCLASSIFIABLE` and `taxonomy_fit:
OUT_OF_SCOPE`.

No tie-break rule may be added, removed or reordered after review begins unless a protocol
amendment is formally recorded **before** any further case is reviewed. Amendment after review
has started is strongly discouraged and would have to be reported as a deviation.

## Confidence

`pattern_confidence` is one of `HIGH`, `MEDIUM`, `LOW`. It is descriptive only. It is never used
as an inclusion criterion, never used to weight a case, and never used to filter the analysis
population. All 100 cases are analysed regardless of confidence.
