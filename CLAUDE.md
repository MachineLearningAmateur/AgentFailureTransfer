# CLAUDE.md

**Read [`AGENTS.md`](AGENTS.md) first — it holds the full rules for this repository.** This
file is a short summary of the ones that are easiest to break by accident.

This is an **analysis / integration repository, not a source-labeling repository**. It imports
frozen artifacts from two completed source studies, verifies them by hash, and recomputes their
results. It never produces labels of its own.

> Never modify or reinterpret the imported reviewer labels. Any future reclassification must be a new explicitly versioned experiment.

> The original source repositories are scientific provenance and must remain read-only from this project.

Quick checklist:

- **Pinned commits.** AIBugAnalysis `85e4bf9caf0a63436a1a305592d82294536ccd8e`,
  SWE-Smith-Bug-Analysis `0345139bf449f1fe9401f2a708d0d3b5961d14b2`. Never resolve to a moving
  `main`.
- **Never write to `../AIBugAnalysis` or `../SWE-Smith-Bug-Analysis`.** No edits, no commits,
  no checkouts, no in-place script runs. Read-only during import; that is all.
- **Before committing**, run `python scripts/validate_sources.py`,
  `python scripts/reproduce_headline_results.py`, and `python -m pytest -q`. All must pass.
- **Expected values are checkpoints, not outputs.** Assert against the known counts and κ
  values; never hard-code them as results or steer a computation towards them. If something
  fails to reproduce, stop and report what disagreed.
- **Do not introduce the obsolete sampling description.** A repo-wide test
  (`tests/test_reports_and_hygiene.py::test_no_obsolete_sampling_text_anywhere`) scans every
  text file, including docs, and fails if it appears. Describe the SWE-smith design only as
  proportional stratified allocation over `generation_method`, max 5 cases per repository,
  seed 20260830, n = 100 from 4,207 resolvable training-task instances, 52 repositories in the
  sample.
- **Environment: `uv` with Python 3.11.** The system `python3` is 3.8 and will not work.

```bash
export PATH="$HOME/.local/bin:$PATH"
uv venv --python 3.11 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

- **Identity is commit SHA + SHA-256**, never a timestamp. `imported_at_utc` is informational.
- **Scope**: Phase 1 is reproduction only. No taxonomy v2, no adjudication, no relabelling of
  Phase 1 cases, no BugPilot taxonomy, no confirmatory significance tests, no new synthetic bugs,
  no models, no causal claims, no family-frequency comparison. The one external taxonomy in scope
  is the Phase 2 ODC control under `experiments/phase2_odc_control/`, which is **complete and
  analysed** (state: `ANALYZED`). Current stage: manuscript synthesis / optional human validation
  — see `docs/current_research_findings.md`; the optional human-validation study there has not
  been started and is not authorized. **Never launch a Phase 2 review without explicit
  authorization**, never inspect Phase 1 case-level labels while editing the ODC rubric, and never
  run a reviewer inside this checkout — bundles are exported outside the repository.
- **The Phase 2 sealed reviews and generated analysis artifacts are frozen research outputs.**
  `experiments/phase2_odc_control/reviews/**` and
  `experiments/phase2_odc_control/analysis/**` are read-only in the same sense as the imported
  Phase 1 labels and the `analysis/` outputs: no edits, no hand-corrected numbers, no regeneration
  from altered inputs.
- **Do not claim specific model identities for the SWE-smith reviewers.** Their metadata names
  none; "Codex" and "Claude" are directory names there.
