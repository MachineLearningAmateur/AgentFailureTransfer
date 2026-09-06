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

**RQ3 — External-taxonomy control.** Does an independent mechanism-neutral software-defect
taxonomy yield higher inter-reviewer reproducibility on the same SWE-smith cases than the
AIDev-derived agent-failure taxonomy?

**RQ4 — Generation mechanism under the external taxonomy.** Under the external taxonomy, does
reviewer agreement still vary by SWE-smith generation mechanism, particularly procedural versus
nonprocedural generation?

RQ1 and RQ2 are answered by Phase 1. RQ3 and RQ4 belong to the Phase 2 ODC control, whose
protocol is drafted and pre-registered and whose review has **not been run**. All four are set
out in [`docs/research_questions.md`](docs/research_questions.md).

## Findings so far

**Phase 1A — the source results reproduce exactly.** Every headline number from both source
studies was recomputed from the sealed reviewer labels alone (never read out of a report) and
matched to the last digit: AIDev fine-grained agreement 31/49 (63.3%, κ 0.583) and
broad-family 36/49 (73.5%, κ 0.658); SWE-smith 41/100 (41.0%) at both levels (κ 0.254 fine,
κ 0.242 family); and the SWE-smith generation-family breakdown llm 20/36, mirror 15/28,
procedural 6/34, combine 0/2. All 38 imported artifacts hash-match the pinned source commits,
and the taxonomy and family-mapping files are byte-identical across the two studies.

**Phase 1B — the picture is robust to the obvious analysis choices.**

- *The AIDev-vs-SWE-smith gap is not a denominator artefact.* Re-analysing AIDev over all 100
  reviewed PRs with the source study's own all-100 rule gives 65/100 (65.0%, κ 0.553) —
  still far above SWE-smith's 41/100 (41.0%, κ 0.254). The bootstrap κ intervals of the two
  corpora do not overlap under either AIDev denominator (AIDev fine [0.42, 0.72], all-100
  [0.44, 0.66]; SWE-smith fine [0.16, 0.35]).
- *The procedural effect is large and survives uncertainty quantification.* Reviewer agreement
  was lower among procedurally generated SWE-smith cases: 6/34 (17.6%) against 35/66 (53.0%)
  for nonprocedural cases — a 35.4-percentage-point difference (Newcombe 95% CI [15.6, 50.2]),
  risk ratio 0.33, Fisher's exact OR 0.19, two-sided p = 0.0006; dropping `combine` (n = 2)
  changes nothing material.

Taken together, the evidence is consistent with taxonomy transfer being substantially weaker on
SWE-smith than on AIDev, and particularly weak for procedural mutations. Three caveats travel
with that sentence: agreement measures reproducibility between two LLM reviewers, not
correctness; the AIDev family-level number is partly in-sample; and the Fisher/permutation
tests are exploratory association tests, not causal evidence about the generation mechanism.
Whether the transfer failure is specific to this agent-process taxonomy (RQ3) is untested. It is
the subject of Phase 2, whose protocol is now drafted and whose review has not been run.

### Phase 2 — ODC external-taxonomy control (FROZEN_PRE_REVIEW)

Phase 2 re-measures the same 100 frozen SWE-smith cases with an independent instrument — the
Defect Type dimension of IBM's Orthogonal Defect Classification (1992) — so that the taxonomy is
the only thing that changes: same cases, same evidence, same two reviewer families, same blind
independence, different taxonomy. It is a measurement control experiment, and it modifies no
Phase 1 label.

**Its status is FROZEN_PRE_REVIEW: the protocol, rubric, schema, reviewer prompts and all 100
packets are hashed into a freeze manifest and tagged `phase2-odc-pre-review-frozen`; anyone with
a clone can export the two reviewer bundles with one command; no review has been run and no
Phase 2 result exists.** ODC is not treated as
ground truth, and a higher agreement figure would not be evidence of realism. See
[`experiments/phase2_odc_control/README.md`](experiments/phase2_odc_control/README.md), which also
holds the copy/paste launch text for each reviewer's fresh session once the freeze is done.

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
python scripts/run_phase1b_robustness.py

python -m pytest -q
```

If a Python 3.10+ interpreter is already on your `PATH`, the plain stdlib form works too:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

### The four steps

| Command | What it does |
| --- | --- |
| `python scripts/import_sources.py [--aidev-path P] [--swesmith-path P] [--allow-unpinned]` | Reads the two source repos (defaults: `../AIBugAnalysis`, `../SWE-Smith-Bug-Analysis`), verifies each is a clean git repo at its pinned commit, checks the review `COMPLETE` markers and the known-good hashes, copies only the approved frozen artifacts into `data/`, and writes `sources/*.json`. Idempotent. It never writes into a source repo. Any ambiguity is a hard stop with a message prefixed `STOP:` — a dirty source tree, an unpinned HEAD, a missing artifact, a hash mismatch, or the two studies' taxonomy/mapping files not being byte-identical. `--allow-unpinned` records `commit_matches_pin: false`, which then makes validation fail. |
| `python scripts/validate_sources.py` | Runs entirely inside this repo, with no access to the source repos. 43 checks: manifest schema, recomputed SHA-256 for every imported file, taxonomy version, cross-corpus identity of the taxonomy and family mapping, every observed fine label being a known label, reviewer case counts (AIDev 100/100, SWE-smith 100/100), no duplicate case ids, matching case-id sets per corpus, and the 100-row hidden crosswalk. Repairs nothing; exits 1 on any failure. |
| `python scripts/reproduce_headline_results.py [--check \| --no-check]` | Recomputes every headline number from the imported sealed labels — nothing is read out of a Markdown report. `--check` (the default) asserts the computed values against the expected checkpoint (exact counts must match exactly, kappas within `5e-4`) and additionally diffs against the imported AIDev `agreement_metrics.json`. Those targets are assertions only; no expected number is ever written into an output artifact. Writes `analysis/taxonomy_transfer/headline_results.{json,md}`, `analysis/generation_method/agreement_by_generation.{json,md}`, and the two derived case-id reconstructions under `data/derived/`. |

| `python scripts/run_phase1b_robustness.py [--check \| --no-check]` | **Phase 1B.** Re-uses the same sealed labels to test whether the Phase 1A picture survives reasonable alternative analysis choices: the AIDev all-100 denominator sensitivity analysis recomputed with the source study's own semantics, Wilson 95% intervals for every agreement rate, a case-level paired bootstrap of κ (seed 20260906, 10,000 replicates, undefined replicates counted and excluded rather than zeroed), and the procedural-vs-nonprocedural contrast with a two-sided Fisher's exact test, effect sizes with intervals, and an exploratory permutation check. Runs `validate_sources.py` first and stops if it fails. `--check` (the default) asserts the recomputed values against the checkpoint and exits non-zero on a mismatch. Writes only into `analysis/taxonomy_transfer/phase1b_robustness/`; it never touches `data/`, `sources/`, or the Phase 1A outputs, and its output is byte-identical across runs. |

Once the artifacts are imported, `validate_sources.py`, `reproduce_headline_results.py`,
`run_phase1b_robustness.py` and the
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

### Phase 1B robustness

Recomputed by `scripts/run_phase1b_robustness.py`; the full write-up is
[`analysis/taxonomy_transfer/phase1b_robustness/robustness_report.md`](analysis/taxonomy_transfer/phase1b_robustness/robustness_report.md),
with the method decisions in `notes.md` beside it.

**Denominator sensitivity.** Analysed over all 100 reviewed AIDev PRs instead of the 49
both-technical-pattern cases — the source study's own all-100 rule, comparing the raw
`failure_pattern` strings with `UNASSIGNED` kept as an ordinary label, so the 34
UNASSIGNED/UNASSIGNED cases count as agreements — AIDev fine agreement is 65/100 (65.0%,
κ 0.5531), against SWE-smith's 41/100 (41.0%, κ 0.2535). The gap does not depend on the
denominator choice. The two AIDev analyses answer different questions and both are reported.

**Uncertainty.** Wilson 95% intervals on the raw agreement rates and percentile bootstrap
intervals on κ (10,000 replicates, seed 20260906): AIDev fine κ 0.5828 [0.4213, 0.7224] and
all-100 κ 0.5531 [0.4369, 0.6636] against SWE-smith fine κ 0.2535 [0.1588, 0.3540].

**Generation mechanism.** Reviewer agreement was lower among procedurally generated cases:
6/34 (17.6%, Wilson [8.4%, 33.5%]) against 35/66 (53.0%, [41.2%, 64.6%]) for nonprocedural
cases — an absolute difference of 35.4 percentage points (Newcombe 95% CI [15.6, 50.2]),
risk ratio 0.333, Fisher's exact odds ratio 0.190, two-sided p = 0.00063. Dropping the two
`combine` cases leaves it at 37.0 points. These are **exploratory association tests**; nothing
here is a causal claim about the generation mechanism.

## Layout

```text
docs/         study design, research questions, provenance, threats to validity
sources/      the two source manifests: pinned commits + SHA-256 for every imported file
data/         the imported frozen artifacts (aidev/, swesmith/) and derived/ reconstructions
scripts/      Phase 1: import_sources.py, validate_sources.py, reproduce_headline_results.py, run_phase1b_robustness.py; Phase 2: import_phase2_packets.py, freeze_phase2.py, make_phase2_review_bundle.py, prepare_phase2_bundles.sh, check_phase2_ready.py, validate_phase2_review.py, analyze_phase2_odc.py
src/          the small library the scripts share (hashing, manifests, reviews, taxonomy, agreement, stats)
analysis/     recomputed outputs: taxonomy_transfer/ (incl. phase1b_robustness/), generation_method/ (statistical_tests/, figures/ hold placeholders only)
experiments/  phase2_odc_control/ — Phase 2 ODC control: protocol, frozen rubric, reviewer prompts (FROZEN_PRE_REVIEW, no review run); external_taxonomy_control/ — the original placeholder
tests/        313 tests: manifest schema, hash verification, kappa, agreement, headline regression, Phase 1B robustness, hygiene, and the Phase 2 tooling on toy records (taxonomy, schema, validator, bundle leakage, freeze, state machine, analysis)
paper/        placeholder
```

## Status

| Phase | State | What it covers |
| --- | --- | --- |
| Phase 1A — reproduction | **COMPLETE** | import, hash verification, 43 validation checks, independent recomputation of every headline number |
| Phase 1B — robustness | **COMPLETE** | denominator sensitivity, Wilson and bootstrap intervals, procedural-vs-nonprocedural exploratory tests |
| Phase 2 — ODC external-taxonomy control | **FROZEN_PRE_REVIEW** | protocol, frozen ODC Defect Type rubric, schema, reviewer prompts and packets hashed and tagged; bundles exportable with `scripts/prepare_phase2_bundles.sh`; no review run, no result |

Both source studies are imported and hash-verified, all 43 validation checks pass, every
expected agreement count and κ reproduces within the checkpoint tolerance, the Phase 1B
robustness analysis reproduces the source study's all-100 value exactly, and the test suite
passes. That is the whole of the current claim.

### Not yet tested

No scientific result beyond the reproduction and the robustness analysis exists. Phase 2 is
designed but unrun, so in particular this repository does **not** yet:

- create a taxonomy v2;
- adjudicate the Claude/Codex disagreements;
- label any new cases;
- run an external taxonomy — the Phase 2 ODC control is designed and pre-registered, but no
  reviewer has classified a single case under it and no Phase 2 number exists;
- run BugPilot taxonomy classification;
- perform any confirmatory significance test (Phase 1B's Fisher and permutation tests are
  exploratory association tests on one contrast, with no multiplicity correction);
- create new synthetic bugs;
- train any models;
- make causal claims;
- compare family-frequency distributions as though the current taxonomy were mechanism-neutral.

The point of Phase 1 is a clean, verifiable foundation before any second experiment is run.

## Further reading

- [`docs/research_questions.md`](docs/research_questions.md) — RQ1 and RQ2, and the Phase 2 RQ3 and RQ4
- [`experiments/phase2_odc_control/README.md`](experiments/phase2_odc_control/README.md) — the Phase 2 ODC control (FROZEN_PRE_REVIEW; includes the reviewer launch prompts)
- [`docs/study_design.md`](docs/study_design.md) — three-repo architecture, pipeline, identity model, sampling design
- [`docs/provenance.md`](docs/provenance.md) — pinned commits and the SHA-256 of every imported file
- [`docs/threats_to_validity.md`](docs/threats_to_validity.md) — what these numbers do not support
- [`AGENTS.md`](AGENTS.md) — working rules for anyone, human or agent, editing this repository
