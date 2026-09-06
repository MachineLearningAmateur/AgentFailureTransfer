# AgentFailureTransfer

A cross-corpus **integration study**. It asks whether a failure taxonomy derived from
*real* coding-agent repair attempts still means anything when it is applied to *synthetic*
SWE-smith training bugs.

This repository performs no labelling of its own. It imports the frozen artifacts of two
completed source studies, verifies them by hash, and independently recomputes their headline
agreement results from the sealed reviewer labels.

## The two source studies

| Study | Repository | Pinned commit | Branch | Role |
| --- | --- | --- | --- | --- |
| AIBugAnalysis | <https://github.com/MachineLearningAmateur/AIBugAnalysis> | `85e4bf9caf0a63436a1a305592d82294536ccd8e` | `main` | real coding-agent failures |
| SWE-Smith-Bug-Analysis | <https://github.com/MachineLearningAmateur/SWE-Smith-Bug-Analysis> | `0345139bf449f1fe9401f2a708d0d3b5961d14b2` | `main` | synthetic training bugs |

Both studies are **frozen, read-only scientific provenance**. Nothing in this project writes
to them, re-runs their reviews, re-labels their cases, adjudicates their disagreements, or
changes their frozen taxonomy. The import step reads them; it never writes. Reproducibility
identity here is *commit SHA + SHA-256*, never a timestamp and never a moving `main`.

Both corpora were labelled with the same frozen taxonomy, `aidev_failure_taxonomy_v1`, and the
same frozen fine → broad-family mapping. The taxonomy file and the mapping file are
byte-identical across the two studies; the import refuses to proceed if they are not.

## Research questions

**RQ1 — Taxonomy transfer.** How reliably does a failure taxonomy derived from real
coding-agent repair attempts transfer to synthetic SWE-smith training bugs?

**RQ2 — Generation mechanism.** How does taxonomy transfer vary with synthetic
bug-generation mechanism?

A potential RQ3 is recorded in [`docs/research_questions.md`](docs/research_questions.md) and
is explicitly **future work, not yet tested**.

## Quickstart

The system `python3` on this machine is 3.8, which is too old — `pyproject.toml` requires
`>=3.10`. Use `uv` to provision a 3.11 interpreter:

```bash
cd /home/disgustingtest/research/AgentFailureTransfer

export PATH="$HOME/.local/bin:$PATH"
uv venv --python 3.11 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

python scripts/import_sources.py
python scripts/validate_sources.py
python scripts/reproduce_headline_results.py

python -m pytest -q
```

If a Python 3.10+ interpreter is already on your `PATH`, the plain stdlib form works too:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

### The three steps

| Command | What it does |
| --- | --- |
| `python scripts/import_sources.py [--aidev-path P] [--swesmith-path P] [--allow-unpinned]` | Reads the two source repos (defaults: `../AIBugAnalysis`, `../SWE-Smith-Bug-Analysis`), verifies each is a clean git repo at its pinned commit, checks the review `COMPLETE` markers and the known-good hashes, copies only the approved frozen artifacts into `data/`, and writes `sources/*.json`. Idempotent. It never writes into a source repo. Any ambiguity is a hard stop with a message prefixed `STOP:` — a dirty source tree, an unpinned HEAD, a missing artifact, a hash mismatch, or the two studies' taxonomy/mapping files not being byte-identical. `--allow-unpinned` records `commit_matches_pin: false`, which then makes validation fail. |
| `python scripts/validate_sources.py` | Runs entirely inside this repo, with no access to the source repos. 43 checks: manifest schema, recomputed SHA-256 for every imported file, taxonomy version, cross-corpus identity of the taxonomy and family mapping, every observed fine label being a known label, reviewer case counts (AIDev 100/100, SWE-smith 100/100), no duplicate case ids, matching case-id sets per corpus, and the 100-row hidden crosswalk. Repairs nothing; exits 1 on any failure. |
| `python scripts/reproduce_headline_results.py [--check \| --no-check]` | Recomputes every headline number from the imported sealed labels — nothing is read out of a Markdown report. `--check` (the default) asserts the computed values against the expected checkpoint (exact counts must match exactly, kappas within `5e-4`) and additionally diffs against the imported AIDev `agreement_metrics.json`. Those targets are assertions only; no expected number is ever written into an output artifact. Writes `analysis/taxonomy_transfer/headline_results.{json,md}`, `analysis/generation_method/agreement_by_generation.{json,md}`, and the two derived case-id reconstructions under `data/derived/`. |

Once the artifacts are imported, `validate_sources.py`, `reproduce_headline_results.py` and the
test suite do not depend on `../AIBugAnalysis` or `../SWE-Smith-Bug-Analysis` continuing to exist.

## Reproduced results

All values below were recomputed by `scripts/reproduce_headline_results.py` from the imported
reviewer records. They are not copied from any source report.

**The two populations are not comparable.** The AIDev numbers are computed on the 49 cases
(of 100 reviewed) where *both* reviewers assigned a technical pattern — the source study's rule,
`failure_pattern != "UNASSIGNED"` on both sides. The SWE-smith numbers are computed on all 100
frozen cases, because the SWE-smith review schema has no `UNASSIGNED` value at all. Do not read
the two columns as a like-for-like contrast without that qualification.

| Level | Corpus | n | agreement | rate | Cohen's κ |
| --- | --- | ---: | ---: | ---: | ---: |
| Fine-grained | AIDev (both reviewers assigned a pattern) | 49 | 31 | 63.3% | 0.5828 |
| Fine-grained | SWE-smith (all frozen cases) | 100 | 41 | 41.0% | 0.2535 |
| Broad family | AIDev (both reviewers assigned a pattern) | 49 | 36 | 73.5% | 0.6575 |
| Broad family | SWE-smith (all frozen cases) | 100 | 41 | 41.0% | 0.2420 |

Agreement by synthetic bug-generation family, at the **broad-family** level (the published level):

| Generation family | n | agreement | rate | Cohen's κ |
| --- | ---: | ---: | ---: | ---: |
| llm | 36 | 20 | 55.6% | 0.2976 |
| mirror | 28 | 15 | 53.6% | 0.3933 |
| procedural | 34 | 6 | 17.6% | 0.1274 |
| combine | 2 | 0 | 0.0% | 0.0000 |

`combine` has n = 2 and supports no substantive conclusion. Its κ of 0 is a genuine value
(the two reviewers' label sets are disjoint, so both observed and expected agreement are 0),
not an undefined result. The fine-level per-family κ values differ from the family-level ones
— notably `llm`, fine κ 0.3364 vs family κ 0.2976 — and are emitted side by side, clearly
labelled, in `analysis/generation_method/agreement_by_generation.md`.

The broad-family mapping was developed from AIDev disagreement data, so the AIDev family-level
number is partly **in-sample**; the SWE-smith family-level number is the out-of-sample
application of the same frozen mapping. See
[`docs/threats_to_validity.md`](docs/threats_to_validity.md).

## Layout

```text
docs/         study design, research questions, provenance, threats to validity
sources/      the two source manifests: pinned commits + SHA-256 for every imported file
data/         the imported frozen artifacts (aidev/, swesmith/) and derived/ reconstructions
scripts/      import_sources.py, validate_sources.py, reproduce_headline_results.py
src/          the small library the scripts share (hashing, manifests, reviews, taxonomy, agreement)
analysis/     recomputed outputs: taxonomy_transfer/, generation_method/ (statistical_tests/, figures/ hold placeholders only)
experiments/  external_taxonomy_control/ — placeholder, nothing run
tests/        80 tests: manifest schema, hash verification, kappa, agreement, headline regression, hygiene
paper/        placeholder
```

## Status

**Setup phase. Reproduction is complete.** Both source studies are imported and hash-verified,
all 43 validation checks pass, every expected agreement count and κ reproduces within the
checkpoint tolerance, and the test suite passes. That is the whole of the current claim.

### Not yet tested

Nothing scientific beyond the reproduction has been done. In particular this repository does
**not** yet:

- create a taxonomy v2;
- adjudicate the Claude/Codex disagreements;
- label any new cases;
- run an external taxonomy;
- run BugPilot taxonomy classification;
- perform statistical significance tests;
- create new synthetic bugs;
- train any models;
- make causal claims;
- compare family-frequency distributions as though the current taxonomy were mechanism-neutral.

The point of this phase is a clean, verifiable foundation before any second experiment is added.

## Further reading

- [`docs/research_questions.md`](docs/research_questions.md) — RQ1, RQ2, and the future RQ3
- [`docs/study_design.md`](docs/study_design.md) — three-repo architecture, pipeline, identity model, sampling design
- [`docs/provenance.md`](docs/provenance.md) — pinned commits and the SHA-256 of every imported file
- [`docs/threats_to_validity.md`](docs/threats_to_validity.md) — what these numbers do not support
- [`AGENTS.md`](AGENTS.md) — working rules for anyone, human or agent, editing this repository
