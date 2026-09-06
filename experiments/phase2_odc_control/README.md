# Phase 2 — ODC external-taxonomy control

**Status: FROZEN_PRE_REVIEW.** The protocol, rubric, schema, reviewer prompts and all 100 packets
are hashed into `FREEZE_MANIFEST.json` and tagged `phase2-odc-pre-review-frozen`; one bundle per
reviewer has been exported outside the repository. **No Phase 2 review has been run** and no
Phase 2 analysis exists. The study owner authorized the reviews on 2026-09-06.

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
| `SETUP` | protocol, rubric, schema, scripts and tests being written |
| `FROZEN_PRE_REVIEW` | every protocol-critical artifact hashed into the freeze manifest; pre-review commit made and tagged `phase2-odc-pre-review-frozen` — **current state** |
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

The protocol is frozen (`FREEZE_MANIFEST.json`, tag `phase2-odc-pre-review-frozen`). From a
fresh clone, one command prepares everything a reviewer needs:

```bash
git clone https://github.com/MachineLearningAmateur/AgentFailureTransfer.git
cd AgentFailureTransfer
bash scripts/prepare_phase2_bundles.sh
```

It builds the repository's Python 3.11 environment (needs `uv` or `python3.11`; the system
`python3` may be too old), verifies the working tree is clean and every frozen artifact still
hashes to the freeze manifest, exports one physically isolated bundle per reviewer **outside**
the clone, gives the bundles their own minimal interpreter, and runs the preflight inside each:

```text
../phase2_review_bundles/
├── .venv/            Python 3.11 + pyyaml, nothing else
├── phase2_claude/    the Claude bundle
└── phase2_codex/     the Codex bundle
```

(Pass a different directory as the script's first argument if you want the bundles elsewhere.
It never overwrites an existing bundle.)

Each bundle is self-contained: it does not need this repository, `numpy`, or `scipy`. A reviewer
session must be **started inside its bundle**, not inside this repository — a session that starts
here can reach the Phase 1 labels, and the reviewer prompt tells it to stop if it finds them.
Use a fresh session, never a continuation of a Phase 1 or setup session, and do not tell the
reviewer anything beyond the block below.

### Claude (Opus)

Open the session inside the bundle:

```bash
cd ../phase2_review_bundles/phase2_claude && source ../.venv/bin/activate && claude
```

Paste:

```text
You are the Claude reviewer for a blind software-defect classification study. Your current
working directory is a self-contained review bundle. Do not leave it, do not read anything
outside it, and do not use web access or any external source for anything, including ODC.

Do this, in order:
1. Confirm BUNDLE_MANIFEST.json and FREEZE_MANIFEST.json exist in the current directory and
   that there is no .git directory. If not, you are not in a bundle: stop and tell me.
2. Read README.md in full. It is your complete instructions.
3. Read taxonomy/odc_defect_type_v1.md in full before classifying anything.
4. Run: python scripts/check_phase2_ready.py --reviewer claude
   If it reports any problem, stop and tell me. Do not start.
5. Review all 100 cases, SWESMITH_001 to SWESMITH_100, one at a time. For each case read only
   data/review_packets/<case_id>/, then write exactly one YAML file
   reviews/claude/cases/<case_id>.yaml with exactly these six fields:
   case_id, odc_defect_type, taxonomy_fit, pattern_confidence, supporting_evidence_ids,
   reasoning_summary. Immediately after writing each file run:
   python scripts/validate_phase2_review.py --reviewer claude --case <case_id>
   and fix anything it rejects before moving on. Never batch cases. Do not stop to ask me
   anything between cases; work through all 100.
6. When all 100 files exist and validate, run:
   python scripts/validate_phase2_review.py --reviewer claude --finalize
7. Stop. Report that the review is complete and the hashes the preflight printed. Do not compute
   agreement, do not compare taxonomies, do not look for any other reviewer's output.

Rules: classify the software defect and the semantics of its correction only. BUG_DIFF
introduces the bug; REFERENCE_REPAIR reverses it. Do not reason about what the bug generator
intended. If two ODC types are plausible, apply the frozen tie-break rules in order and record
taxonomy_fit: AMBIGUOUS. If none is defensible, use UNCLASSIFIABLE with taxonomy_fit:
OUT_OF_SCOPE. Write only under reviews/claude/. If you find a hidden/ or analysis/ directory,
a Phase 1 label, generation metadata, or another reviewer's files, stop and tell me.
```

### GPT / Codex

Open the session inside the bundle, using whatever launches your Codex or GPT coding session
(`codex` shown):

```bash
cd ../phase2_review_bundles/phase2_codex && source ../.venv/bin/activate && codex
```

Paste:

```text
You are the Codex reviewer for a blind software-defect classification study. Your current
working directory is a self-contained review bundle. Do not leave it, do not read anything
outside it, and do not use web access or any external source for anything, including ODC.

Do this, in order:
1. Confirm BUNDLE_MANIFEST.json and FREEZE_MANIFEST.json exist in the current directory and
   that there is no .git directory. If not, you are not in a bundle: stop and tell me.
2. Read README.md in full. It is your complete instructions.
3. Read taxonomy/odc_defect_type_v1.md in full before classifying anything.
4. Run: python scripts/check_phase2_ready.py --reviewer codex
   If it reports any problem, stop and tell me. Do not start.
5. Review all 100 cases, SWESMITH_001 to SWESMITH_100, one at a time. For each case read only
   data/review_packets/<case_id>/, then write exactly one JSON file
   reviews/codex/cases/<case_id>.json with exactly these six fields:
   case_id, odc_defect_type, taxonomy_fit, pattern_confidence, supporting_evidence_ids,
   reasoning_summary. Immediately after writing each file run:
   python scripts/validate_phase2_review.py --reviewer codex --case <case_id>
   and fix anything it rejects before moving on. Never batch cases. Do not stop to ask me
   anything between cases; work through all 100.
6. When all 100 files exist and validate, run:
   python scripts/validate_phase2_review.py --reviewer codex --finalize
7. Stop. Report that the review is complete and the hashes the preflight printed. Do not compute
   agreement, do not compare taxonomies, do not look for any other reviewer's output.

Rules: classify the software defect and the semantics of its correction only. BUG_DIFF
introduces the bug; REFERENCE_REPAIR reverses it. Do not reason about what the bug generator
intended. If two ODC types are plausible, apply the frozen tie-break rules in order and record
taxonomy_fit: AMBIGUOUS. If none is defensible, use UNCLASSIFIABLE with taxonomy_fit:
OUT_OF_SCOPE. Write only under reviews/codex/. If you find a hidden/ or analysis/ directory,
a Phase 1 label, generation metadata, or another reviewer's files, stop and tell me.
```

The two blocks differ only in reviewer name, output directory and file format.

### After both reviewers report complete

Copy each reviewer's sealed output back into this repository, one commit per reviewer, without
ever placing one reviewer's output into the other's bundle:

```bash
cp -r ../phase2_review_bundles/phase2_claude/reviews/claude experiments/phase2_odc_control/reviews/
cp -r ../phase2_review_bundles/phase2_codex/reviews/codex  experiments/phase2_odc_control/reviews/
python scripts/check_phase2_ready.py --reviewer claude   # workflow state should read BOTH_COMPLETE
python scripts/analyze_phase2_odc.py
```

If a bundle must ever be regenerated, it must come from the tagged freeze commit, and a review
that has already begun against an earlier bundle is void unless every hash matches.

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
