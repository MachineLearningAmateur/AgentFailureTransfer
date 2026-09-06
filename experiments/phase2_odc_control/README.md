# Phase 2 — ODC external-taxonomy control

**Status: SETUP.** The protocol is drafted and the tooling is built and tested on toy records only. **No Phase 2 review
has been run**, no reviewer bundle has been generated, and no Phase 2 analysis exists. Neither
review may be launched without explicit authorization from the study owner.

## What this experiment is

Phase 1 found that the frozen AIDev-derived failure taxonomy transferred much less reproducibly
to SWE-smith than to AIDev, and that agreement was especially low on procedural SWE-smith
mutations. That result has two candidate explanations and Phase 1 cannot separate them:

- **Explanation A — measurement mismatch.** The AIDev taxonomy is a useful taxonomy of
  coding-agent failures, but it is the wrong measuring instrument for static synthetic bugs.
- **Explanation B — synthetic-bug difficulty / mismatch.** Even under an independent code-defect
  taxonomy, SWE-smith bugs — especially procedural mutations — remain hard to classify
  reproducibly.

Phase 2 re-measures the same 100 frozen SWE-smith cases with an external instrument — the
**Defect Type** dimension of IBM's Orthogonal Defect Classification (ODC, 1992) — so that the
taxonomy is the only thing that changes:

```text
same 100 cases
same evidence
same two reviewer families
same blind independence
different taxonomy
```

It is a **measurement control experiment**. It produces new labels under a new taxonomy; it
does not relabel, reinterpret or modify anything from Phase 1.

> No Phase 1 reviewer classification is modified during Phase 2.

## Research questions

**RQ3** — Does an independent mechanism-neutral software-defect taxonomy yield higher
inter-reviewer reproducibility on the same SWE-smith cases than the AIDev-derived agent-failure
taxonomy?

**RQ4** — Under the external taxonomy, does reviewer agreement still vary by SWE-smith
generation mechanism, particularly procedural versus nonprocedural generation?

## Read these first

| File | What it is |
| --- | --- |
| [`protocol/phase2_protocol.md`](protocol/phase2_protocol.md) | the full pre-registered protocol: design, endpoints, paired tests, interpretation matrix, freeze procedure, standing rules |
| [`protocol/external_taxonomy_selection.md`](protocol/external_taxonomy_selection.md) | why ODC, and what the choice does not buy |
| [`protocol/blinding_protocol.md`](protocol/blinding_protocol.md) | what each reviewer may and may not see, and how that is enforced |
| [`taxonomy/odc_defect_type_v1.md`](taxonomy/odc_defect_type_v1.md) | the frozen rubric a reviewer reads in full |
| [`taxonomy/odc_defect_type_v1.yaml`](taxonomy/odc_defect_type_v1.yaml) | the machine-readable form of the same rubric |
| [`taxonomy/SOURCE_PROVENANCE.md`](taxonomy/SOURCE_PROVENANCE.md) | citation, DOI, which ODC dimension is used and which are excluded |
| [`protocol/reviewer_prompt_claude.md`](protocol/reviewer_prompt_claude.md) · [`protocol/reviewer_prompt_codex.md`](protocol/reviewer_prompt_codex.md) | the two reviewer prompts, semantically identical |

## Layout

```text
experiments/phase2_odc_control/
├── README.md                       this file
├── protocol/
│   ├── phase2_protocol.md          the pre-registered protocol
│   ├── external_taxonomy_selection.md
│   ├── blinding_protocol.md
│   ├── reviewer_prompt_claude.md
│   └── reviewer_prompt_codex.md
├── taxonomy/
│   ├── odc_defect_type_v1.md       the rubric, prose
│   ├── odc_defect_type_v1.yaml     the rubric, machine-readable
│   └── SOURCE_PROVENANCE.md
├── data/
│   ├── review_packets/             the same frozen SWESMITH_001-100 evidence
│   ├── review_manifest.csv
│   └── review_snapshot_manifest.json
├── schemas/
│   └── odc_review_result.schema.json
├── reviews/
│   ├── claude/cases/               claude writes here, and nowhere else
│   └── codex/cases/                codex writes here, and nowhere else
├── analysis/                       written only after BOTH_COMPLETE
│   ├── odc_agreement.{json,md}
│   ├── odc_confusion.csv
│   ├── taxonomy_comparison.{json,md}
│   └── generation_method_analysis.csv
└── bundles/
    └── README.md                   bundles are generated outside the repo; only this README lives here
```

## Workflow states

| State | Meaning |
| --- | --- |
| `SETUP` | protocol, rubric, schema, scripts and tests being written — **current state** |
| `FROZEN_PRE_REVIEW` | every protocol-critical artifact hashed into the freeze manifest; pre-review commit made and tagged `phase2-odc-pre-review-frozen` |
| `CLAUDE_COMPLETE` | Claude's 100 records validate, are finalised and are sealed |
| `CODEX_COMPLETE` | Codex's 100 records validate, are finalised and are sealed |
| `BOTH_COMPLETE` | both `COMPLETE` markers exist |
| `ANALYZED` | the Phase 2 analysis has run and written `analysis/` |

`CLAUDE_COMPLETE` and `CODEX_COMPLETE` are independent and may happen in either order. Neither
reviewer's output becomes visible to the other before that other reviewer is complete. **The
analysis refuses to run before `BOTH_COMPLETE`**, and the hidden generation crosswalk is joined
only after that point.

## How to run it

The entry points, in the order they run. Activate the environment first:

```bash
export PATH="$HOME/.local/bin:$PATH"
source .venv/bin/activate
```

**1. Import the packets** (`SETUP`). Read-only with respect to the pinned SWE-smith source; it
copies the same frozen `SWESMITH_001`–`SWESMITH_100` evidence used in Phase 1 and verifies every
file against the frozen snapshot and review manifests. Nothing is resampled or regenerated.

```bash
python scripts/import_phase2_packets.py
```

**2. Freeze** (`SETUP` → `FROZEN_PRE_REVIEW`). Hashes every protocol-critical artifact into a
machine-readable freeze manifest, ready for the pre-review commit and the
`phase2-odc-pre-review-frozen` tag. The tag is created only at freeze time and is never moved.

```bash
python scripts/freeze_phase2.py
```

**3. Build one bundle per reviewer**, both from the frozen commit, into a path **outside** this
repository. The bundle creator refuses to export a contaminated bundle.

```bash
python scripts/make_phase2_review_bundle.py --reviewer claude --out <path outside this repo>
python scripts/make_phase2_review_bundle.py --reviewer codex  --out <path outside this repo>
```

**4. Preflight, inside a bundle**, before that reviewer starts. If any hash differs from the
freeze manifest, the review is not launched.

```bash
python scripts/check_phase2_ready.py --reviewer <claude|codex>
```

**5. Review** (requires explicit authorization). Each reviewer works in a fresh session, in its
own bundle, writing one record per case and validating it immediately:

```bash
python scripts/validate_phase2_review.py --reviewer <name> --case SWESMITH_nnn
```

and finalising only once all 100 records exist and validate:

```bash
python scripts/validate_phase2_review.py --reviewer <name> --finalize
```

Claude writes `reviews/claude/cases/SWESMITH_nnn.yaml`; Codex writes
`reviews/codex/cases/SWESMITH_nnn.json`. Both finalise to `review_results.jsonl`,
`review_metadata.json` and a `COMPLETE` marker.

**6. Analyse** (`BOTH_COMPLETE` → `ANALYZED`). Refuses to run before both `COMPLETE` markers
exist. Computes ODC agreement and κ, the confusion matrix, taxonomy-fit and sentinel rates, the
paired McNemar comparison against the Phase 1 result, the paired bootstrap (seed 20260906,
10,000 replicates), and the generation-family and procedural/nonprocedural breakdowns; writes
`analysis/`.

```bash
python scripts/analyze_phase2_odc.py
```

## Launching a reviewer: copy/paste for a clean session

Only after the freeze (`FROZEN_PRE_REVIEW`, tag `phase2-odc-pre-review-frozen`) and only with
explicit authorization. First export the bundle **outside** this repository:

```bash
python scripts/make_phase2_review_bundle.py --reviewer claude --out /home/disgustingtest/review_bundles/phase2_claude
python scripts/make_phase2_review_bundle.py --reviewer codex  --out /home/disgustingtest/review_bundles/phase2_codex
```

Then open a **fresh** session (not a continuation of any Phase 1 or setup session) with its
working directory set to the bundle, and paste the matching block below. Nothing else is said
to the reviewer: no Phase 1 result, no generation metadata, no mention of the other reviewer's
progress.

### Claude (Opus) — paste into a fresh session started in `phase2_claude/`

```text
You are the Claude reviewer for a blind software-defect classification study. Your working
directory is a self-contained review bundle. Do not leave it, and do not use web access or any
external source for anything, including ODC.

Do this, in order:
1. Read README.md in full. It is your complete instructions.
2. Read taxonomy/odc_defect_type_v1.md in full before classifying anything.
3. Run: python scripts/check_phase2_ready.py --reviewer claude
   If it reports any problem, stop and tell me. Do not start.
4. Review all 100 cases, SWESMITH_001 to SWESMITH_100, one at a time. For each case read only
   data/review_packets/<case_id>/, then write exactly one YAML file
   reviews/claude/cases/<case_id>.yaml with exactly these six fields:
   case_id, odc_defect_type, taxonomy_fit, pattern_confidence, supporting_evidence_ids,
   reasoning_summary. Immediately after writing each file run:
   python scripts/validate_phase2_review.py --reviewer claude --case <case_id>
   and fix anything it rejects before moving on. Never batch cases.
5. When all 100 files exist and validate, run:
   python scripts/validate_phase2_review.py --reviewer claude --finalize
6. Stop. Report that the review is complete and the hashes the preflight printed. Do not compute
   agreement, do not compare taxonomies, do not look for any other reviewer's output.

Rules: classify the software defect and the semantics of its correction only. BUG_DIFF
introduces the bug; REFERENCE_REPAIR reverses it. Do not reason about what the bug generator
intended. If two ODC types are plausible, apply the frozen tie-break rules in order and record
taxonomy_fit: AMBIGUOUS. If none is defensible, use UNCLASSIFIABLE with taxonomy_fit:
OUT_OF_SCOPE. Write only under reviews/claude/. If you find a hidden/ or analysis/ directory,
a Phase 1 label, generation metadata, or another reviewer's files, stop and tell me.
```

### GPT / Codex — paste into a fresh session started in `phase2_codex/`

```text
You are the Codex reviewer for a blind software-defect classification study. Your working
directory is a self-contained review bundle. Do not leave it, and do not use web access or any
external source for anything, including ODC.

Do this, in order:
1. Read README.md in full. It is your complete instructions.
2. Read taxonomy/odc_defect_type_v1.md in full before classifying anything.
3. Run: python scripts/check_phase2_ready.py --reviewer codex
   If it reports any problem, stop and tell me. Do not start.
4. Review all 100 cases, SWESMITH_001 to SWESMITH_100, one at a time. For each case read only
   data/review_packets/<case_id>/, then write exactly one JSON file
   reviews/codex/cases/<case_id>.json with exactly these six fields:
   case_id, odc_defect_type, taxonomy_fit, pattern_confidence, supporting_evidence_ids,
   reasoning_summary. Immediately after writing each file run:
   python scripts/validate_phase2_review.py --reviewer codex --case <case_id>
   and fix anything it rejects before moving on. Never batch cases.
5. When all 100 files exist and validate, run:
   python scripts/validate_phase2_review.py --reviewer codex --finalize
6. Stop. Report that the review is complete and the hashes the preflight printed. Do not compute
   agreement, do not compare taxonomies, do not look for any other reviewer's output.

Rules: classify the software defect and the semantics of its correction only. BUG_DIFF
introduces the bug; REFERENCE_REPAIR reverses it. Do not reason about what the bug generator
intended. If two ODC types are plausible, apply the frozen tie-break rules in order and record
taxonomy_fit: AMBIGUOUS. If none is defensible, use UNCLASSIFIABLE with taxonomy_fit:
OUT_OF_SCOPE. Write only under reviews/codex/. If you find a hidden/ or analysis/ directory,
a Phase 1 label, generation metadata, or another reviewer's files, stop and tell me.
```

The two blocks differ only in reviewer name, output directory and file format. The bundle needs
Python 3.10+ with `pyyaml` importable; nothing else. After both reviewers have finalised, copy
each `reviews/<reviewer>/` directory back into `experiments/phase2_odc_control/reviews/` in this
repository (one commit per reviewer, never letting one reviewer's output into the other's
bundle), then run `python scripts/analyze_phase2_odc.py`.

## Standing rules

- No Phase 1 reviewer classification is modified. Phase 1 labels are read-only inputs to the
  paired comparison, loaded from the frozen artifacts rather than hard-coded.
- Phase 1 **case-level** labels must not be inspected while designing or editing the ODC rubric.
  Aggregate Phase 1 findings may be cited as motivation.
- The source repositories stay read-only.
- Reviewer bundles are generated outside the repository.
- No review may be launched without explicit authorization.
- Nothing here claims ODC is ground truth, and higher agreement would not mean greater realism.
  See [`protocol/phase2_protocol.md`](protocol/phase2_protocol.md) §14 and
  [`../../docs/threats_to_validity.md`](../../docs/threats_to_validity.md).
