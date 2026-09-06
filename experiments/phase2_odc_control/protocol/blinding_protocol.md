# Phase 2 blinding and isolation protocol

Phase 2 asks whether two independent reviewers classify the same 100 cases the same way under a
different taxonomy. That question only has an answer if the two reviews are genuinely
independent, and if neither reviewer can see anything that would tell it what the "expected"
answer is. This file says how that is enforced.

Isolation here is **physical**, not advisory. A rule that depends on a reviewer choosing not to
look at a file it can read is not a control.

## 1. What a reviewer may see

- the neutral `SWESMITH_nnn` case ID;
- the repository/code context already present in the frozen packet;
- `BUG_DIFF`;
- the specification;
- the failing-test evidence;
- `REFERENCE_REPAIR`;
- the frozen ODC rubric (`odc_defect_type_v1.md` and `.yaml`) and its source provenance;
- its own reviewer prompt;
- the review result schema and the validator;
- the review manifest and packet hashes;
- its own, initially empty, output directory.

## 2. What a reviewer may not see

Not in a file, not in a filename, not in a path, not in a string:

- the Phase 1 Claude label;
- the Phase 1 Codex label;
- Phase 1 agreement/disagreement status;
- the AIDev taxonomy category or broad family;
- the generation method or generation family;
- the source model;
- the trajectory;
- the attempt count;
- the population frequency;
- the hidden instance mapping;
- any previous analysis output;
- the other reviewer's Phase 2 output;
- any AIDev data;
- any cross-corpus analysis.

## 3. Physical bundle isolation

This repository now contains Phase 1 results, so **the reviewers are not run in the repository
checkout.** `scripts/make_phase2_review_bundle.py` builds one bundle per reviewer, from the
frozen commit, into a path **outside** the repository.

Each bundle contains only:

```text
ODC reviewer instructions
frozen ODC taxonomy
review schema
validator
the 100 frozen evidence packets
review manifest / packet hashes
empty reviewer output directory
```

Each bundle physically excludes:

```text
Phase 1 reviewer labels
Phase 1 reports
generation metadata
hidden sample mapping
other reviewer's Phase 2 output
AIDev data
cross-corpus analysis
```

There is no `hidden/` directory and no `analysis/` directory inside a bundle, by design. Their
absence is the control; a reviewer that goes looking for them has found nothing, and should stop
and report rather than reconstruct anything.

**The bundle creator scans for forbidden paths and forbidden content and refuses to export a
contaminated bundle.** A refusal is a stop condition. It is never worked around by deleting the
offending file by hand and re-exporting without understanding why it was there.

Both bundles are generated from the **same frozen commit**, so that a difference between the two
reviews cannot be a difference between the two instruments.

## 4. Fresh sessions

Each reviewer runs in a **fresh session**. Phase 1 reviewer sessions are not continued, resumed
or referenced. No reviewer is told:

- how it labelled these cases in Phase 1;
- what the Phase 1 case-level disagreements were;
- the Phase 1 generation-family result;
- anything about the other Phase 2 reviewer's progress or output.

Aggregate Phase 1 results are documented in this repository and are part of the public record of
the study, but they are not placed in a reviewer bundle and are not given to a reviewer during
labelling.

## 5. No web access during review

Reviewers must not use live web access during the review. They must not search for ODC
interpretations, later ODC revisions, tutorials, vendor adaptations, or explanations of any
individual defect type.

All reviewers receive the **same frozen ODC rubric**, and that rubric is the only source of ODC
semantics for the review. The risk being controlled is concrete: if one reviewer silently
consulted a different version or a different explanation of ODC, the two reviewers would be
applying different instruments and the agreement number would measure that difference instead of
the taxonomy.

The **setup phase may consult the canonical publication**. The **review phase may not.**

## 6. Reviewer write boundaries

A reviewer writes **only** under `reviews/<reviewer>/` in its own bundle:

```text
reviews/claude/cases/SWESMITH_nnn.yaml
reviews/codex/cases/SWESMITH_nnn.json
reviews/<reviewer>/review_results.jsonl
reviews/<reviewer>/review_metadata.json
reviews/<reviewer>/COMPLETE
```

No reviewer writes to the packets, the manifests, the rubric, the protocol, the schema, the
validator, or any path belonging to the other reviewer. The write boundary is enforced in code,
not by convention: a write outside the reviewer's own directory is refused.

Reviewers also never *read* the other reviewer's `reviews/` directory. In a correctly built
bundle it is not present at all.

## 7. Preflight hash check

Before a review starts, `scripts/check_phase2_ready.py --reviewer <name>` verifies that the
bundle matches the freeze manifest: the rubric, the schema, the reviewer prompt, the review
manifest, the review snapshot manifest and all 100 packet files hash to the values recorded at
freeze time.

**If any preflight hash differs, the review is not launched.** A hash difference means the
instrument changed after it was frozen, and no result computed from it would be a pre-registered
result.

During the review the snapshot manifest hash is checked again at finalisation. Finalisation
refuses if it has changed since the review started, if any of the 100 cases is missing, or if
any record is invalid.

## 8. Stop conditions during review

Stop and report — do not improvise a fix — if any of the following occurs:

- a preflight hash differs from the freeze manifest;
- a packet is missing, unreadable, or does not match its recorded hash;
- the bundle contains anything from the exclusion list in §3, including a `hidden/` or
  `analysis/` directory;
- generation metadata, a Phase 1 label, or a Phase 1 report appears anywhere in the bundle;
- either reviewer can see the other reviewer's output;
- a review appears to have begun before the protocol freeze;
- a write outside the reviewer's own `reviews/<reviewer>/` directory is attempted or observed;
- the reviewer is asked, or is tempted, to consult the web for ODC interpretation;
- correcting a problem would require changing Phase 1 evidence or Phase 1 labels;
- the rubric appears to need a new tie-break rule.

The last one deserves emphasis. If the frozen rubric turns out to fit these cases badly, that is
**data about the taxonomy**, and it is recorded through `UNCLASSIFIABLE` and `taxonomy_fit`, not
repaired by amending the rubric mid-review. An amendment after review begins would have to be
formally recorded before any further case is reviewed, and would have to be reported as a
deviation from pre-registration.

## 9. After finalisation

A reviewer stops after finalising its own 100 records. It does not run comparative analysis,
does not compute agreement, does not look at the other review, and does not join anything to
generation metadata.

Comparison is locked until both `COMPLETE` markers exist. `scripts/analyze_phase2_odc.py`
refuses to run before `BOTH_COMPLETE`, and the hidden generation crosswalk is joined only after
that point.
