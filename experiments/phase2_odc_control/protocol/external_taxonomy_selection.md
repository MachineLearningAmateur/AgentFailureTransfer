# Why ODC, and what that choice does not buy

This file records the choice of external taxonomy for the Phase 2 control, and its limits. It
is written before any Phase 2 case is reviewed, so that the rationale cannot be reconstructed
after seeing the result.

## The requirement

Phase 1 applied a taxonomy derived from real coding-agent repair attempts to static synthetic
bug states, and inter-reviewer agreement was low. That result is consistent with two different
explanations, and Phase 1 alone cannot separate them (see
[`phase2_protocol.md`](phase2_protocol.md)). Separating them needs a second taxonomy applied to
the same cases by the same reviewer families — and the second taxonomy has to be one that could
not have been shaped by the Phase 1 result.

So the requirement is narrow: an independent, pre-existing, mechanism-neutral scheme for
classifying software defects, small enough that two reviewers can hold it in mind, and defined
in terms of the defect and its correction rather than in terms of who or what produced it.

## The choice

The **Defect Type** dimension of IBM's Orthogonal Defect Classification (ODC).

> Ram Chillarege, Inderpal S. Bhandari, Jarir K. Chaar, Michael J. Halliday, Diane S. Moebus,
> Bonnie K. Ray, and Man-Yuen Wong. "Orthogonal Defect Classification — A Concept for
> In-Process Measurements." *IEEE Transactions on Software Engineering*, 18(11):943–956, 1992.
> DOI `10.1109/32.177364`.

Canonical IBM Research page:
<https://research.ibm.com/publications/orthogonal-defect-classificationa-concept-for-in-process-measurements>

Full provenance is in [`../taxonomy/SOURCE_PROVENANCE.md`](../taxonomy/SOURCE_PROVENANCE.md).

## Five reasons

1. **It predates the subject matter.** ODC was published in 1992, before LLMs, coding agents,
   SWE-smith and AIDev existed.
2. **It was not derived from our study.** No part of it was fitted to these 100 cases, to either
   source study, or to the Phase 1 agreement result.
3. **It classifies the defect, not the reasoning.** The Defect Type dimension categorises
   software defects by the semantics of the defect and its correction, rather than by the
   process, beliefs, diagnosis or verification behavior of an agent. That is precisely the
   property the AIDev-derived taxonomy does not have, and precisely the property the control
   needs.
4. **It was designed for breadth.** Its categories were intended to be usable across software
   products and development processes, not for one product or one workflow.
5. **It is cleaner than inventing our own.** Any mechanism-neutral taxonomy written by us after
   seeing Phase 1 would be open to the objection that it was designed to produce a particular
   contrast. An externally published scheme is not.

## Limitation: Defect Type only, and no claim of universality

ODC is **not** claimed here to be a perfect or universal bug taxonomy. It was developed for
in-process software measurement in an industrial setting, it is a multi-dimensional scheme, and
this experiment uses one dimension of it.

Used: **Defect Type**.

Not used, not recorded, not shown to reviewers:

- defect trigger;
- development activity;
- impact;
- source;
- age;
- every other ODC process attribute.

Those dimensions describe how and when a defect was found or introduced. They would reintroduce
process information into an experiment whose whole purpose is to remove it, and the control does
not need them.

A consequence worth stating plainly: because only one dimension is used, this experiment is not
a test of ODC as a whole, and no result here should be read as evidence for or against ODC as a
measurement programme.

## The tie-break guidance is an operationalisation, not a modification

The nine numbered tie-break rules in [`../taxonomy/odc_defect_type_v1.md`](../taxonomy/odc_defect_type_v1.md)
are **this study's operationalisation of the published ODC defect types**. They are not a
modification of ODC and are not attributable to its authors.

What they do: fix the order in which two plausible categories are resolved, so that ambiguity is
resolved for a stated reason rather than by private preference, and so that both reviewers
resolve it the same way.

What they do not do: add a defect type, remove one, redefine one, or change the boundary between
two of them in a way the published definitions do not already support.

They were frozen before any reviewer saw a Phase 2 packet, and they were written without
inspecting any Phase 1 case-level label. If they turn out to be wrong for these cases, that is a
finding to report, not a thing to fix mid-review: no rule may be added, removed or reordered
after review begins unless a protocol amendment is formally recorded before any further case is
reviewed.

## The comparison this enables

```text
AIDev-derived agent-failure taxonomy
vs
ODC Defect Type taxonomy
```

on the **same frozen SWE-smith cases**, with the same evidence, the same two reviewer families
and the same blind independence. The taxonomy is the only thing that changes.
