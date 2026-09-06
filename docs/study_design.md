# Study design

## Three-repository architecture

```text
AIBugAnalysis
real-agent source study
FROZEN
       \
        \
         -> AgentFailureTransfer
        /
       /
SWE-Smith-Bug-Analysis
synthetic source study
FROZEN
```

Two completed studies feed one integration study. The arrows are one-directional by design:
artifacts and hashes flow in, nothing flows back.

### What each source contributes

**AIBugAnalysis** (`85e4bf9caf0a63436a1a305592d82294536ccd8e`, role `real_agent_failure_source`)
contributes the real coding-agent side: 100 pull requests from real agent repair attempts,
each independently labelled by two blind LLM reviewers ("codex" and "claude") against the
frozen fine-grained taxonomy. It is also the origin of the taxonomy itself
(`aidev_failure_taxonomy_v1`), of the frozen fine → broad-family mapping, of the review rubric
both reviews were sealed against, and of the published dual-review calibration report and
machine-readable agreement metrics that this repository diffs its AIDev recomputation against.

**SWE-Smith-Bug-Analysis** (`0345139bf449f1fe9401f2a708d0d3b5961d14b2`, role
`synthetic_training_bug_source`) contributes the synthetic side: a frozen 100-case sample of
SWE-smith training bugs, labelled by two blind reviewers against a byte-identical copy of the
same taxonomy, plus the sampling configuration and selection record, the population provenance,
the seal chain (review manifest, frozen snapshot manifest, `COMPLETE` markers), and the
*hidden* generation-method crosswalk that makes RQ2 possible. It also holds one cross-repo
artifact about the *other* corpus: the language attribution for the 35 AIDev strict cases.

The taxonomy `.md` and the family-mapping `.yaml` are byte-identical in both studies
(`ecf76f0d…` and `1ce72320…`). The import refuses to run if they are not.

### Why the sources are frozen

They are the evidence. Their value is that the labels were produced blind, sealed, and
committed before this integration study existed, so nothing here can have influenced them.
Re-running a review, adjudicating a disagreement, or amending the taxonomy in place would
destroy exactly the property that makes the reproduction meaningful — and would do so
invisibly, since the result would still look like a valid artifact.

So the sources are treated as read-only evidence: no edits, no commits, no branch switching, no
re-running their scripts in place, and no use of a moving `main` as a reproducibility
reference. If a source working tree is dirty, the frozen state is ambiguous and the import
stops rather than guessing. Any future reclassification is a new, explicitly versioned
experiment inside *this* repository, never a change to a source.

## Phase status

**Phase 1A — reproduction: COMPLETE.** **Phase 1B — robustness: COMPLETE.**
**Phase 2 — external-taxonomy control: NOT STARTED.**

## Pipeline: import → validate → reproduce → robustness

**1. Import** (`scripts/import_sources.py`). Verifies each source path is a git repository,
that its working tree is clean, and that its HEAD equals the pinned commit; confirms the
expected frozen artifacts and the review `COMPLETE` markers exist; checks the known-good
SHA-256 values; confirms the two studies' taxonomy and mapping files are byte-identical; copies
only the approved artifacts into `data/aidev/**` and `data/swesmith/**`; computes SHA-256 for
every copied file; and writes `sources/aidev_source.json` and `sources/swesmith_source.json`.
It never writes into a source repository. Every ambiguity is a hard stop (message prefixed
`STOP:`) rather than a silent choice. The step is idempotent.

**2. Validate** (`scripts/validate_sources.py`). Runs entirely inside this repository with no
access to the sources — this is the check that the imported corpus stands on its own. It loads
both manifests, recomputes every file's SHA-256 and size, confirms the taxonomy version and the
cross-corpus identity of the taxonomy and mapping, confirms every observed fine label is a known
label, confirms the reviewer case counts (AIDev codex 100 / claude 100; SWE-smith codex 100 /
claude 100), confirms there are no duplicate case ids and that the two reviewers of each corpus
covered the same case-id set, and confirms the hidden crosswalk has 100 rows matching those ids
with only the four expected `method_family` values. 43 checks; nothing is ever repaired.

**3. Reproduce** (`scripts/reproduce_headline_results.py`). Recomputes every headline number
from the imported reviewer records. No value is read out of a Markdown report. The source
studies' own inclusion rules are applied, the frozen mapping is applied deterministically to
both reviewers' original labels, and the generation metadata is joined **only after** the
reviewer results are loaded — never before, so the crosswalk cannot influence the label
handling. `--check`, the default, asserts the results against the expected checkpoint (exact
counts must match exactly; κ within `5e-4`) and diffs against the imported AIDev
`agreement_metrics.json`. Those expectations are assertions only; no expected number is ever
written into an emitted artifact.

**4. Robustness** (`scripts/run_phase1b_robustness.py`, Phase 1B). Runs step 2 first and stops
if it fails, then re-uses the same sealed labels — no relabelling, no adjudication, no change
to the taxonomy or the mapping — to ask whether the Phase 1A picture depends on the denominator
choice or on a single point estimate. It reconstructs the AIDev all-100 sensitivity population
with the source study's own semantics (below), computes Wilson 95% intervals for every raw
agreement rate, bootstraps κ at the case level (seed 20260906, 10,000 replicates, percentile
interval, undefined replicates counted and excluded rather than mapped to 0), and runs the
procedural-vs-nonprocedural contrast with a two-sided Fisher's exact test, risk difference,
risk ratio and odds ratio with intervals, and an exploratory permutation check. `--check`, the
default, asserts the recomputed values against the checkpoint — including the Phase 1A counts,
which must be unchanged. It writes only into `analysis/taxonomy_transfer/phase1b_robustness/`,
emits no timestamp, and is byte-identical across runs.

After step 1, nothing depends on `../AIBugAnalysis` or `../SWE-Smith-Bug-Analysis` continuing to
exist.

## Identity model

Reproducibility identity is **commit SHA + SHA-256**. Every imported file carries its
`sha256` and byte size in the manifest; every source study carries its pinned `commit_sha`,
the branch it was on, and whether its worktree was clean. Validation recomputes all of it.

Timestamps are never identity. `imported_at_utc` is present in each manifest and is purely
informational; nothing keys off it, and it is not a version. Likewise "latest", `main`, and
file mtimes are never used to identify an artifact.

Manifest top-level keys: `name`, `repository`, `commit_sha`, `pinned_commit_sha`,
`commit_matches_pin`, `source_branch`, `source_path_at_import`, `source_worktree_clean`, `role`,
`taxonomy_version`, `corpus`, `review_completion`, `taxonomy_sha256`, `family_mapping_sha256`,
`review_result_sha256`, `reference_scripts`, `excluded_from_import`, `imported_at_utc`,
`identity_note`, `files`. The SWE-smith manifest additionally carries `snapshot_sha256` and
`review_manifest_sha256`.

## What is deliberately not imported, and why

The rule is: import the minimum needed to reproduce, plus the provenance needed to prove the
seal. Not whole repositories. 38 files totalling 687,339 bytes are imported (`data/` occupies
about 864 KB on disk).

- **Evidence and review packets** (`data/evidence_packets/**`, `data/review_packets/**`) — the
  material shown to the reviewers. Large, and not needed to recompute agreement from labels.
- **`reviews/*/cases/**`** on both sides — verified byte-for-byte duplicates of the canonical
  `review_results.jsonl`. Importing them would create a second copy of the labels that could
  drift.
- **Trajectories and execution artifacts** — agent logs, not inputs to any current computation.
- **The full SWE-smith population CSV** (~1.0 MB) — the 100-case results do not depend on it;
  `POPULATION_PROVENANCE.json` carries the counts and the population hash.
- **The 7.9 MB review-draft PDF**, `archive/` (parked work), `runs/`, and the source studies'
  own `tests/`.
- **Every source script.** They are cited by hash under `reference_scripts` in each manifest
  instead of being copied, because some of their literal output strings carry an obsolete
  sampling description that must not propagate into this repository's artifacts. Their
  *semantics* are reimplemented here; their identity is pinned by hash.
- **Source parquet files** other than `aidev_rq1_primary_cases.parquet`, which is imported as an
  **opaque hashed artifact**: it pins the identity of the 35-case strict corpus and is never
  parsed. No parquet reader is installed or needed.

The full excluded list, per source, is in the `excluded_from_import` field of each manifest.

## The two populations

The two headline numbers are **not computed on comparable populations**, and this is a property
of the source schemas, not a choice made here.

**AIDev: 49 of 100 reviewed cases.** The source study's rule, from
`AIBugAnalysis/scripts/analyze_dual_reviews.py` (`both_pattern`), is: include a case iff *both*
reviewers assigned a technical pattern, i.e. `failure_pattern != "UNASSIGNED"` on both sides.
That is the *only* filter. It is not conditioned on outcome classification, failure scope, or
reviewer confidence. `OTHER_TECHNICAL_PATTERN` is a valid technical pattern and is kept.
49 cases survive. One consequence worth noting: a case can be in the 49 even if the reviewers
disagreed about the outcome classification, as long as both still named a pattern.

**SWE-smith: all 100 frozen cases.** The SWE-smith review schema has no `UNASSIGNED` value at
all — every sampled case is an execution-validated bug state, so the non-technical escape hatch
does not exist and there is nothing to exclude. The source study's
`scripts/apply_frozen_families.py` applies no case filter either.

So "63.3% vs 41.0%" is not a like-for-like contrast. Both population definitions must be stated
side by side wherever the numbers are.

### The AIDev all-100 sensitivity population (Phase 1B)

Because that mismatch is a property of the schemas rather than a choice, Phase 1B reports a
third population alongside the two: **all 100 reviewed AIDev cases**, using the source study's
own rule from `AIBugAnalysis/scripts/compare_reviews.py` (the `cross_model` "pattern" row).
That rule iterates the 100 cases in `sorted(case_id)` order, compares the two reviewers' raw
`failure_pattern` strings for exact equality, and keeps `UNASSIGNED` as an **ordinary label**
rather than as missing data — so a case both reviewers left UNASSIGNED counts as an agreement
(34 of the 100). Under the AIDev review schema there is no separate policy for nontechnical
rejection, unclear, or merged-without-correction: all of them simply carry
`failure_pattern == "UNASSIGNED"`. No missing-value policy was invented here, and the
recomputation from the imported labels reproduces the source study's committed value exactly.

A family-level all-100 variant is also emitted, mapping non-UNASSIGNED labels through the frozen
mapping and carrying UNASSIGNED through unchanged. It is **derived**, is labelled as such
wherever it appears, and is not a source-study number.

### Fine labels vs broad families

Two levels are reported everywhere, always distinguished:

- **Fine-grained**: the 11 frozen fine-grained failure patterns, exactly as sealed.
- **Broad family**: the same sealed labels mapped deterministically through the frozen
  `fine → family` mapping (sha256 `1ce72320…`). Neither reviewer re-classified anything; the
  mapping is applied to both reviewers' original labels identically.

The mapping has 9 families over 11 fine labels. Only `REPOSITORY_UNDERSTANDING` is
multi-member (`false_premise_about_existing_code`, `misdiagnosed_root_cause`,
`masked_symptom_instead_of_fixing`); the other eight are single-member identity renames. So the
entire effect of the family level on agreement is that one three-way collapse. `UNASSIGNED` is
deliberately absent from the mapping and is excluded before any statistic.

The per-generation-family κ values published as the headline are the **family-level** ones.
They diverge from the fine-level ones — for `llm`, family κ 0.2976 vs fine κ 0.3364. Both are
emitted, each clearly labelled with which level it is.

## Unified kappa definition

The two source studies used different κ implementations: AIDev called
`sklearn.metrics.cohen_kappa_score` and stored full precision; SWE-smith used a hand-written
function rounded to 4 decimal places. They are numerically equivalent for the unweighted case,
but this repository picks one and says so.

Every κ here is a single hand-rolled **unweighted Cohen's kappa**:

- observed agreement `p_o` = fraction of cases where the two reviewers' labels are equal;
- expected agreement `p_e` = Σ over the **union of both raters' observed labels** of
  `p_left(label) · p_right(label)`;
- κ = `(p_o − p_e) / (1 − p_e)`.

Reported at full precision **and** rounded to 4 dp, side by side.

**Degenerate rule.** If `p_e == 1.0`, or `n == 0`, κ is `0.0` — unless observed agreement is
`1.0`, in which case κ is `1.0`. It never returns `nan` or `None`.

That rule exists so the published source-study tables reproduce, and it is wrong for a
bootstrap: a degenerate resample carries no information about κ, and folding it in as a hard
`0.0` would move the percentile interval by an artefact of the rule. So
`agentfailuretransfer.stats.cohen_kappa_or_none` returns `None` in exactly those cases, the
Phase 1B bootstrap excludes such replicates from the interval, and it reports how many there
were. The two implementations agree on every non-degenerate input, and the tests assert it.

Each subgroup κ uses that subgroup's **own** marginals, not the pooled ones. This matters for
the `combine` family: with n = 2 and disjoint label sets, expected agreement is 0 and observed
agreement is 0, so κ = (0 − 0)/(1 − 0) = **0.0** — a genuine value, not a degenerate collapse.
An implementation that emits `nan` for a two-case subgroup will not reproduce it. The
implementation is cross-checked in the tests against `sklearn.metrics.cohen_kappa_score` on toy
inputs and on 200 random non-degenerate inputs.

## SWE-smith sampling design

The frozen 100-case SWE-smith sample was drawn by **proportional stratified allocation over
`generation_method`**, with a **cap of 5 cases per repository** (a cap, not a quota), seed
**20260830**, target **n = 100**, from a population of **4,207 unique resolvable training-task
instances**. The realised sample covers **52 repositories**. The largest absolute allocation
deviation was 0.0045, with 5 recorded `REPOSITORY_CAP_APPLIED` distortions and 0 excluded
instances. Case ids (`SWESMITH_001`…`SWESMITH_100`) were assigned by seeded shuffle. The
sampling configuration records an explicit list of forbidden selection inputs: no taxonomy
label, no AIDev frequency, and no model preclassification could influence selection.

The parameters are verifiable from the imported artifacts: `data/swesmith/configs/sampling.yaml`
(seed, target, cap, forbidden inputs), `data/swesmith/hidden/selection_record.json` (population
4,207; 100 selected; 52 unique repositories; deviations and distortions),
`data/swesmith/population/POPULATION_PROVENANCE.json` (the pinned upstream dataset revisions and
the accounting down to 4,207 resolvable instances), and `data/swesmith/analysis/sample_balance.md`.

The **generation-method crosswalk was withheld from both reviewers** during review and is joined
only after the sealed labels have been loaded. The `generation_method → method_family` mapping
is the source study's own, materialised as the `method_family` column of
`data/swesmith/hidden/sample_metadata.csv`; the four families observed in the sample are `llm`
(36), `procedural` (34), `mirror` (28), and `combine` (2).

Every task in the SWE-smith sample is Python.
