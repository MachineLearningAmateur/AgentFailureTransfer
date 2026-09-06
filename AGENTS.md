# Working rules for AgentFailureTransfer

Read this before changing anything here. It applies equally to human contributors and to
coding agents.

## What this repository is

This is an **analysis / integration repository**, not a source-labeling repository.

It imports the frozen artifacts of two completed source studies, verifies them by hash, and
recomputes their results. It does not produce labels, does not review cases, and does not
resolve disagreements. Every label in `data/` arrived here sealed and stays sealed.

## The two rules that override everything else

> Never modify or reinterpret the imported reviewer labels. Any future reclassification must be a new explicitly versioned experiment.

> The original source repositories are scientific provenance and must remain read-only from this project.

If a task appears to require breaking either rule, stop and report it instead. A "small fix"
to a reviewer label is not a fix; it is a silent new labelling exercise with no provenance.

## Practical rules

**Source repositories.** The two sources are pinned by commit SHA:

| Study | Path | Pinned commit |
| --- | --- | --- |
| AIBugAnalysis | `/home/disgustingtest/research/AIBugAnalysis` | `85e4bf9caf0a63436a1a305592d82294536ccd8e` |
| SWE-Smith-Bug-Analysis | `/home/disgustingtest/research/SWE-Smith-Bug-Analysis` | `0345139bf449f1fe9401f2a708d0d3b5961d14b2` |

Never write to `../AIBugAnalysis` or `../SWE-Smith-Bug-Analysis` — no edits, no commits, no
`git checkout`, no branch switching, no re-running their scripts in place. Read-only access
during import is the only permitted interaction. Never resolve a source reference to a moving
`main`; the pins are constants in `scripts/import_sources.py`, and the script refuses to run
if a source HEAD differs. `--allow-unpinned` exists for diagnosis only: it records
`commit_matches_pin: false`, and `validate_sources.py` then fails by design. Do not use it to
get past an unexpected HEAD — investigate the HEAD instead. If a source working tree is dirty,
the frozen state is ambiguous: stop and report, do not clean it.

**Before committing**, always run, in this order:

```bash
export PATH="$HOME/.local/bin:$PATH"
source .venv/bin/activate
python scripts/validate_sources.py
python scripts/reproduce_headline_results.py
python scripts/run_phase1b_robustness.py
python -m pytest -q
```

All four must pass. Do not commit with a failing check.

**Expected values are checkpoints, not outputs.** The known agreement counts and κ values
(AIDev 31/49 and 36/49; SWE-smith 41/100 and 41/100; the per-generation-family breakdown) are
*validation targets*. They may be asserted against; they must never be hard-coded as a result,
written into an emitted artifact, or used to steer a computation towards them. If a number
fails to reproduce, stop and report exactly what disagreed — investigate source semantics
rather than forcing the expected value. Likewise, the κ implementation must not depend on any
hard-coded result: it is cross-checked against `sklearn.metrics.cohen_kappa_score` in the tests.

**Never introduce the obsolete sampling description.** The parked SSR sampling design that
appears in some source-repo strings is obsolete and must not enter this repository in any form.
A repo-wide test (`tests/test_reports_and_hygiene.py::test_no_obsolete_sampling_text_anywhere`)
scans every text file, including documentation, and fails if it appears. Describe the SWE-smith
design only as what it actually is: proportional stratified allocation over `generation_method`
with a cap of 5 cases per repository, seed 20260830, target n = 100, drawn from a population of
4,207 resolvable training-task instances, yielding 52 repositories in the sample.

**Environment.** Use `uv` with Python 3.11 (`pyproject.toml` requires `>=3.10`; the system
`python3` is 3.8 and will not work):

```bash
export PATH="$HOME/.local/bin:$PATH"
uv venv --python 3.11 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

`pyarrow` is deliberately not a dependency. `data/aidev/derived/aidev_rq1_primary_cases.parquet`
is an opaque hashed artifact, stored only to pin the identity of the 35-case strict corpus. It
is never parsed. Do not add a parquet reader to read it.

## Scope discipline

Phases 1A (reproduction) and 1B (robustness) are complete. **Phase 2 — the ODC
external-taxonomy control — is now an explicitly versioned experiment under
`experiments/phase2_odc_control/`, in the `SETUP` state**: its protocol, frozen ODC Defect Type
rubric and reviewer prompts exist; no review has been run, no reviewer bundle has been
generated, and no Phase 2 result exists. Its rules are in
`experiments/phase2_odc_control/protocol/phase2_protocol.md` and
`.../blinding_protocol.md`, and they bind anyone touching that directory:

- **Never launch a Phase 2 review without explicit authorization** from the study owner. Writing
  protocol, tooling or tests is setup work; running the Claude or Codex ODC review is not, and it
  may not begin until the setup report has been reviewed and the review is separately authorized.
- **Never inspect Phase 1 case-level labels while designing or editing the ODC rubric.** The
  rubric must not be tuned around either reviewer's old labels, `OTHER` cases, false-premise
  disagreements, or procedural cases known to disagree. Aggregate Phase 1 findings are already
  known and may be cited as motivation. Loading the sealed labels programmatically inside the
  Phase 2 analysis script, after both reviews are complete, is a different thing and is fine.
- **The source repositories remain read-only**, including for Phase 2 packet import: the importer
  reads the pinned SWE-smith source and never writes to it.
- **Reviewer bundles must be generated outside this repository.** This checkout contains Phase 1
  results, so a reviewer must never work inside it. The bundle creator refuses to export a
  contaminated bundle, and a refusal is a stop condition to report, not an obstacle to route
  around.

No Phase 1 reviewer classification may be modified by any of this. Phase 2 produces new labels
under a new taxonomy; the Phase 1 labels stay sealed.

Beyond that, do not, without an explicit new instruction:

- create a taxonomy v2, adjudicate disagreements, or relabel any Phase 1 case;
- run any external taxonomy other than the pre-registered Phase 2 ODC control, or a BugPilot
  taxonomy;
- run statistical significance tests beyond the exploratory association tests
  Phase 1B was explicitly commissioned to run (`scripts/run_phase1b_robustness.py`:
  procedural vs nonprocedural Fisher's exact test, effect sizes, and a permutation
  robustness check, all on the SWE-smith generation families and none of them
  confirmatory);
- create new synthetic bugs or train models;
- make causal claims;
- compare family-frequency distributions as though the current taxonomy were mechanism-neutral.

Any of those is a **new, explicitly versioned experiment** with its own directory under
`experiments/`, its own inputs, and its own write-up. It never edits the imported data.

## Provenance discipline

- Identity is `commit_sha` plus per-file `sha256`. `imported_at_utc` is informational only and
  is never identity. Do not use timestamps, file mtimes, or "latest" to identify anything.
- If you add an imported artifact, it goes through `scripts/import_sources.py` so that its hash
  lands in `sources/*.json`, and `docs/provenance.md` is regenerated from those manifests rather
  than typed by hand.
- Do not copy source-study scripts into this repository. They are cited by hash under
  `reference_scripts` in each manifest, because some of their literal output strings carry the
  obsolete sampling description.
- Do not claim specific model identities for the SWE-smith reviewers. The AIDev
  `review_metadata.json` names models; the SWE-smith one does not. "Codex" and "Claude" are
  directory names on the SWE-smith side.
- Keep the frozen imported artifacts in version control. Only caches, environments, and
  generated junk belong in `.gitignore`.
