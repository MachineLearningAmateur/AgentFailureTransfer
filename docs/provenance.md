# Provenance

Everything in this document is generated from `sources/aidev_source.json` and
`sources/swesmith_source.json`, which are written by `scripts/import_sources.py` and
re-verified in full by `scripts/validate_sources.py`. Regenerate it from those manifests
rather than editing hashes by hand.

## Identity note

> Identity is commit_sha + the per-file sha256 values. Timestamps are informational only.

Reproducibility identity is the source **commit SHA** plus the per-file **SHA-256**.
`imported_at_utc` is informational only and is never used as identity, as a version, or as a
tie-breaker. Neither a moving `main`, nor a file mtime, nor "latest" identifies anything here.
`validate_sources.py` recomputes every hash and every byte size below and fails on any mismatch.

## Pinned source revisions

| Study | Repository | Local path at import | Commit | Branch | Worktree clean | Review completion | Taxonomy version |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `AIBugAnalysis` | <https://github.com/MachineLearningAmateur/AIBugAnalysis> | `/home/disgustingtest/research/AIBugAnalysis` | `85e4bf9caf0a63436a1a305592d82294536ccd8e` | `main` | yes | codex 100/100, COMPLETE marker present; claude 100/100, COMPLETE marker present | `aidev_failure_taxonomy_v1` |
| `SWE-Smith-Bug-Analysis` | <https://github.com/MachineLearningAmateur/SWE-Smith-Bug-Analysis> | `/home/disgustingtest/research/SWE-Smith-Bug-Analysis` | `0345139bf449f1fe9401f2a708d0d3b5961d14b2` | `main` | yes | codex 100/100, COMPLETE marker present; claude 100/100, COMPLETE marker present | `aidev_failure_taxonomy_v1` |

Both manifests record `commit_matches_pin: true`: each source HEAD equalled its pinned commit
at import, and both worktrees were clean before and after. `scripts/import_sources.py` refuses
to run otherwise unless `--allow-unpinned` is passed, which records `commit_matches_pin: false`
and makes `scripts/validate_sources.py` fail by design.

Role: `AIBugAnalysis` = `real_agent_failure_source`, `SWE-Smith-Bug-Analysis` = `synthetic_training_bug_source`.

## Key hashes

| Artifact | SHA-256 | Notes |
| --- | --- | --- |
| Frozen taxonomy (`aidev_failure_taxonomy_v1`) | `ecf76f0d752afd2632d4a2825b648a36cce4c16926782aec18fd4e2637fe4cc7` | byte-identical in both studies (9359 B); `data/aidev/taxonomy/frozen_failure_taxonomy_v1.md` and `data/swesmith/taxonomy/frozen_failure_taxonomy_v1.md` |
| Frozen fine &rarr; family mapping | `1ce7232047437f87e7116d84b369e4f820e854481cbc744faf3b1d4c1af60985` | byte-identical in both studies (1842 B); AIDev filename `proposed_pattern_families.yaml`, SWE-smith filename `pattern_families.yaml` |
| SWE-smith frozen snapshot manifest | `981694c07ffcc9ee9bcf00527d71a0c94b15884ebfc7d8aa537363b3f646a6de` | `data/swesmith/review_snapshot_manifest.json`; the value both SWE-smith `COMPLETE` markers commit to |
| SWE-smith review manifest | `64e607800de2a08e4321b371d616841bbd4fbe6deaddb1321dfd355333caebfa` | `data/swesmith/review_manifest.csv`; the neutral manifest shown to reviewers |
| AIDev `review_results.jsonl` &mdash; codex | `bec4769de6d5e3ed8f9dbd0acf51cf83f526c8079c4fe2076db7151c76e1b6b9` | sealed Codex labels, 100 cases |
| AIDev `review_results.jsonl` &mdash; claude | `02957aef0de14dbb28e3b9b468693db508281da3a03a2ea175f31171e29cb402` | sealed Claude labels, 100 cases |
| SWE-smith `review_results.jsonl` &mdash; codex | `2a42458ad4bc3b727ca9c373c6e917ae12dc35a155088ad0d51619724e8912c2` | sealed Codex labels, 100 cases |
| SWE-smith `review_results.jsonl` &mdash; claude | `433638b95abcc5d1ef31575a62171081bf3468191a6427015ffb66c8b8e1441b` | sealed Claude labels, 100 cases |
| AIDev `COMPLETE` &mdash; codex | `39109bf52c7a7db3852ae6e9693f4166d7be41ff5652a8a79e0edd4968aacbc2` | seal marker; carries the rubric, manifest and evidence-snapshot hashes |
| AIDev `COMPLETE` &mdash; claude | `8cc5731f4243a050e33f88b7765bdf61393ff84b99cc0a30320b8afb86f88af6` | seal marker |
| SWE-smith `COMPLETE` &mdash; codex | `1ff0b40cdc7a15e78ca441836787d7892271b1ad108ff33c76944c30725437a5` | seal marker; carries the snapshot-manifest hash and the taxonomy fingerprint |
| SWE-smith `COMPLETE` &mdash; claude | `a15ffcf36f1165e04f2e47ec18b9ff09d0cf082c06f2081303cd1062d77fea7c` | seal marker |
| AIDev strict-corpus parquet | `49c1ae4bb7cbc7a3d7ec50bf9b7770cb91c89d5d27069e498d89a394405de032` | `data/aidev/derived/aidev_rq1_primary_cases.parquet` (70487 B) &mdash; OPAQUE hashed artifact, stored only to pin the 35-case strict corpus identity; never parsed, no parquet reader required |

Both manifests declare taxonomy version `aidev_failure_taxonomy_v1`; `validate_sources.py` confirms that the
taxonomy and mapping files are byte-identical across the two corpora and that these hashes match.

## Imported files &mdash; AIBugAnalysis @ `85e4bf9caf0a63436a1a305592d82294536ccd8e`

20 files, 382,440 bytes.

| Source path | Imported path | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `reviews/codex/review_results.jsonl` | `data/aidev/reviews/codex/review_results.jsonl` | 82,302 | `bec4769de6d5e3ed8f9dbd0acf51cf83f526c8079c4fe2076db7151c76e1b6b9` |
| `reviews/codex/COMPLETE` | `data/aidev/reviews/codex/COMPLETE` | 348 | `39109bf52c7a7db3852ae6e9693f4166d7be41ff5652a8a79e0edd4968aacbc2` |
| `reviews/codex/review_metadata.json` | `data/aidev/reviews/codex/review_metadata.json` | 587 | `d4c74b7623c74487bc1799362292e424a4b7d7e59404c0f1105628875241305d` |
| `reviews/claude/review_results.jsonl` | `data/aidev/reviews/claude/review_results.jsonl` | 145,676 | `02957aef0de14dbb28e3b9b468693db508281da3a03a2ea175f31171e29cb402` |
| `reviews/claude/COMPLETE` | `data/aidev/reviews/claude/COMPLETE` | 349 | `8cc5731f4243a050e33f88b7765bdf61393ff84b99cc0a30320b8afb86f88af6` |
| `reviews/claude/review_metadata.json` | `data/aidev/reviews/claude/review_metadata.json` | 597 | `9bc1c0f038af1a942b3fc204755ca78c6c2d076bc2871cbe64222b7525409c11` |
| `analysis/taxonomy/frozen_failure_taxonomy_v1.md` | `data/aidev/taxonomy/frozen_failure_taxonomy_v1.md` | 9,359 | `ecf76f0d752afd2632d4a2825b648a36cce4c16926782aec18fd4e2637fe4cc7` |
| `analysis/taxonomy/proposed_pattern_families.yaml` | `data/aidev/taxonomy/proposed_pattern_families.yaml` | 1,842 | `1ce7232047437f87e7116d84b369e4f820e854481cbc744faf3b1d4c1af60985` |
| `analysis/taxonomy/family_mapping_analysis.md` | `data/aidev/taxonomy/family_mapping_analysis.md` | 9,314 | `744af57ff7952d308da7daf0c1b14495cb27f2cd4dceca9a8326a0477db52578` |
| `analysis/dual_review/agreement_metrics.json` | `data/aidev/dual_review/agreement_metrics.json` | 1,975 | `dc2c8abe13844d0ddceeacdbd3c8f0d3d548114be44011d07f886ddd6395af67` |
| `analysis/dual_review/calibration_report.md` | `data/aidev/dual_review/calibration_report.md` | 7,501 | `efa79b7649c5b2d11852a21faaec6d23722d859ddf045cbaab20f21e04c25309` |
| `analysis/dual_review/pattern_confusion.csv` | `data/aidev/dual_review/pattern_confusion.csv` | 843 | `bbe9d8e666731b67e1b79d6ba291311901b378b488ed76d4c6dacc81bf227166` |
| `analysis/dual_review/pattern_family_confusion.csv` | `data/aidev/dual_review/pattern_family_confusion.csv` | 470 | `daf468dc65e245376b8883f6bc02bc3eeaca4ad167e4d78204e5c18bce2e330a` |
| `analysis/dual_review/pattern_disagreements.csv` | `data/aidev/dual_review/pattern_disagreements.csv` | 29,675 | `fecc19cc46a0591b262f4788014a2cb304158c99dbaa0d10f451bab76a6afea5` |
| `analysis/dual_review/pattern_family_disagreements.csv` | `data/aidev/dual_review/pattern_family_disagreements.csv` | 2,092 | `3296c61639ed223563fe0b7f78c522292f64644c024e3183614e62b2d128946b` |
| `data/derived/DERIVATION_METADATA.json` | `data/aidev/derived/DERIVATION_METADATA.json` | 1,221 | `28fd76013cda1468a42a3862c7d650f3942ceb1e2dfae96c6469d17db3df4e0b` |
| `data/derived/aidev_rq1_primary_cases.parquet` | `data/aidev/derived/aidev_rq1_primary_cases.parquet` | 70,487 | `49c1ae4bb7cbc7a3d7ec50bf9b7770cb91c89d5d27069e498d89a394405de032` |
| `docs/aidev_review_rubric.md` | `data/aidev/docs/aidev_review_rubric.md` | 5,729 | `af8f12449c3977b91d867684806e81407ba2fcb1a8cbd0c32d835d1e0b6c2acf` |
| `schemas/review_result.schema.json` | `data/aidev/schemas/review_result.schema.json` | 3,356 | `e2d853d75badc3ed3e5eb4116419b0aa9e922bec4d3a4d6deab39c252d4232f0` |
| `data/pr_manifest.csv` | `data/aidev/data/pr_manifest.csv` | 8,717 | `30318b513846580b450ec42eb1325418df66b6d734244d75d947d903aaf1bf26` |

Per-file notes:

- `data/aidev/reviews/codex/review_results.jsonl` &mdash; sealed Codex fine-grained labels (100 cases)
- `data/aidev/reviews/codex/COMPLETE` &mdash; Codex seal marker (rubric + manifest + evidence snapshot hashes)
- `data/aidev/reviews/codex/review_metadata.json` &mdash; Codex reviewer model identity and protocol version
- `data/aidev/reviews/claude/review_results.jsonl` &mdash; sealed Claude fine-grained labels (100 cases)
- `data/aidev/reviews/claude/COMPLETE` &mdash; Claude seal marker
- `data/aidev/reviews/claude/review_metadata.json` &mdash; Claude reviewer model identity and protocol version
- `data/aidev/taxonomy/frozen_failure_taxonomy_v1.md` &mdash; frozen fine-grained taxonomy of record
- `data/aidev/taxonomy/proposed_pattern_families.yaml` &mdash; frozen fine -> broad-family mapping
- `data/aidev/taxonomy/family_mapping_analysis.md` &mdash; how the family mapping was selected from AIDev disagreement data
- `data/aidev/dual_review/agreement_metrics.json` &mdash; published AIDev agreement metrics (diff target for recomputation)
- `data/aidev/dual_review/calibration_report.md` &mdash; prose of record for 31/49 and 36/49, incl. the in-sample caveat
- `data/aidev/dual_review/pattern_confusion.csv` &mdash; fine confusion matrix; cells sum to the 49-case population
- `data/aidev/dual_review/pattern_family_confusion.csv` &mdash; family confusion matrix; cells sum to the 49-case population
- `data/aidev/dual_review/pattern_disagreements.csv` &mdash; the 18 fine-label disagreements with both reviewers' reasoning
- `data/aidev/dual_review/pattern_family_disagreements.csv` &mdash; the 13 disagreements the family mapping does not absorb
- `data/aidev/derived/DERIVATION_METADATA.json` &mdash; hash bundle tying every sealed input to the source study's derived data
- `data/aidev/derived/aidev_rq1_primary_cases.parquet` &mdash; OPAQUE hashed artifact: pins the 35-case strict corpus identity. Never parsed by this repository (no parquet reader is required).
- `data/aidev/docs/aidev_review_rubric.md` &mdash; the rubric both AIDev reviews were sealed against
- `data/aidev/schemas/review_result.schema.json` &mdash; field/enum contract for the AIDev reviewer records
- `data/aidev/data/pr_manifest.csv` &mdash; case_id -> repo/pr_number/pr_url/source_agent; the source analysis joins onto it one-to-one

## Imported files &mdash; SWE-Smith-Bug-Analysis @ `0345139bf449f1fe9401f2a708d0d3b5961d14b2`

18 files, 304,899 bytes.

| Source path | Imported path | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `reviews/codex/review_results.jsonl` | `data/swesmith/reviews/codex/review_results.jsonl` | 56,108 | `2a42458ad4bc3b727ca9c373c6e917ae12dc35a155088ad0d51619724e8912c2` |
| `reviews/codex/COMPLETE` | `data/swesmith/reviews/codex/COMPLETE` | 226 | `1ff0b40cdc7a15e78ca441836787d7892271b1ad108ff33c76944c30725437a5` |
| `reviews/codex/review_metadata.json` | `data/swesmith/reviews/codex/review_metadata.json` | 258 | `85035173345ef8b5381f3d3133cecff6bf6b617cb515609a133feec9bd38cb62` |
| `reviews/claude/review_results.jsonl` | `data/swesmith/reviews/claude/review_results.jsonl` | 81,062 | `433638b95abcc5d1ef31575a62171081bf3468191a6427015ffb66c8b8e1441b` |
| `reviews/claude/COMPLETE` | `data/swesmith/reviews/claude/COMPLETE` | 227 | `a15ffcf36f1165e04f2e47ec18b9ff09d0cf082c06f2081303cd1062d77fea7c` |
| `reviews/claude/review_metadata.json` | `data/swesmith/reviews/claude/review_metadata.json` | 258 | `4fc70f699dd42e45faa26d4047cee31d8f40e63aa810a1bbbaf9386effe5e633` |
| `taxonomy/frozen_failure_taxonomy_v1.md` | `data/swesmith/taxonomy/frozen_failure_taxonomy_v1.md` | 9,359 | `ecf76f0d752afd2632d4a2825b648a36cce4c16926782aec18fd4e2637fe4cc7` |
| `taxonomy/pattern_families.yaml` | `data/swesmith/taxonomy/pattern_families.yaml` | 1,842 | `1ce7232047437f87e7116d84b369e4f820e854481cbc744faf3b1d4c1af60985` |
| `taxonomy/TAXONOMY_PROVENANCE.json` | `data/swesmith/taxonomy/TAXONOMY_PROVENANCE.json` | 3,232 | `212ac25aafb0b5cb03b09221515e8331eaaecded8cca629f7b2df8774dc3c98c` |
| `data/hidden/sample_metadata.csv` | `data/swesmith/hidden/sample_metadata.csv` | 25,526 | `0ef1a5720f9f2a24caefb5abf7076fbf636d027a1dfe54d90f3307180fde84a1` |
| `data/hidden/selection_record.json` | `data/swesmith/hidden/selection_record.json` | 18,037 | `f1519069ab698f6fa8a230e5911180a7a6f5b61098dd56ac9016468196a247ed` |
| `data/review_manifest.csv` | `data/swesmith/review_manifest.csv` | 13,554 | `64e607800de2a08e4321b371d616841bbd4fbe6deaddb1321dfd355333caebfa` |
| `data/review_snapshot_manifest.json` | `data/swesmith/review_snapshot_manifest.json` | 80,223 | `981694c07ffcc9ee9bcf00527d71a0c94b15884ebfc7d8aa537363b3f646a6de` |
| `configs/sampling.yaml` | `data/swesmith/configs/sampling.yaml` | 1,890 | `6a735b3d05e8e0f859d3f811d2ffd549d6854d6c836e0c80fa5c21f3dc267397` |
| `data/population/POPULATION_PROVENANCE.json` | `data/swesmith/population/POPULATION_PROVENANCE.json` | 2,468 | `b60f339e8fc478d208e114aa79492b29638a05e4ea9756851744f69665d74bd2` |
| `analysis/sample_balance.md` | `data/swesmith/analysis/sample_balance.md` | 2,841 | `a70014fbec00f4f1849a3c675b8ad631e4d7755b38973d6a9d1bfe60b5dadc63` |
| `analysis/aidev_strict_language_profile.json` | `data/swesmith/analysis/aidev_strict_language_profile.json` | 3,707 | `abf979351278b15b5e5034e12fd5ddede762420d7430ed78ceb13522c78ddc0b` |
| `schemas/review_result.schema.json` | `data/swesmith/schemas/review_result.schema.json` | 4,081 | `988c731609152f17530a915962479dae3e44be11268b5537b4e75873f7651be2` |

Per-file notes:

- `data/swesmith/reviews/codex/review_results.jsonl` &mdash; sealed Codex fine-grained labels (100 cases)
- `data/swesmith/reviews/codex/COMPLETE` &mdash; Codex seal marker (snapshot manifest hash + taxonomy fingerprint)
- `data/swesmith/reviews/codex/review_metadata.json` &mdash; binds the Codex JSONL by results_sha256
- `data/swesmith/reviews/claude/review_results.jsonl` &mdash; sealed Claude fine-grained labels (100 cases)
- `data/swesmith/reviews/claude/COMPLETE` &mdash; Claude seal marker
- `data/swesmith/reviews/claude/review_metadata.json` &mdash; binds the Claude JSONL by results_sha256
- `data/swesmith/taxonomy/frozen_failure_taxonomy_v1.md` &mdash; byte-identical copy of the AIDev frozen taxonomy
- `data/swesmith/taxonomy/pattern_families.yaml` &mdash; byte-identical copy of the AIDev family mapping (renamed on import)
- `data/swesmith/taxonomy/TAXONOMY_PROVENANCE.json` &mdash; records the byte-for-byte taxonomy handoff from AIDev
- `data/swesmith/hidden/sample_metadata.csv` &mdash; hidden crosswalk: case_id -> generation_method / method_family. Withheld from reviewers; joined only after labels are loaded.
- `data/swesmith/hidden/selection_record.json` &mdash; sample selection record (population 4207, 100 selected, 52 repos)
- `data/swesmith/review_manifest.csv` &mdash; the neutral manifest both COMPLETE markers commit to
- `data/swesmith/review_snapshot_manifest.json` &mdash; frozen packet snapshot; completes the seal chain end to end
- `data/swesmith/configs/sampling.yaml` &mdash; seed 20260830, target_n 100, max_per_repo 5, forbidden inputs
- `data/swesmith/population/POPULATION_PROVENANCE.json` &mdash; pinned dataset revisions and the 4207-instance population accounting
- `data/swesmith/analysis/sample_balance.md` &mdash; human-readable sample balance table
- `data/swesmith/analysis/aidev_strict_language_profile.json` &mdash; language attribution for the 35 AIDev strict cases (cross-repo artifact)
- `data/swesmith/schemas/review_result.schema.json` &mdash; 8-field contract; documents why UNASSIGNED is absent here

Total imported: 38 files, 687,339 bytes.

## Reference scripts (cited, not copied)

These source-study scripts define the canonical semantics this repository reimplements. They
are **not** imported: some of their literal output strings carry an obsolete sampling
description, and copying them would propagate it into this repository's artifacts. They are
pinned by hash instead, so the semantics they define remain identifiable.

| Study | Source path | Bytes | SHA-256 | What it defines |
| --- | --- | ---: | --- | --- |
| `AIBugAnalysis` | `scripts/analyze_dual_reviews.py` | 14,782 | `19934ffd54cbb1d391d89f7a2cddafe3ab45e9f609c1f7c3fe95444a17932f80` | canonical 49-case inclusion rule and fine kappa |
| `AIBugAnalysis` | `scripts/apply_pattern_families.py` | 5,858 | `cdf519ab26df6565848da42bada31d637a43ab050d8e2c6c11e957de8c8dda0a` | canonical family mapping application and family kappa |
| `AIBugAnalysis` | `scripts/build_rq1_aidev_dataset.py` | 3,463 | `808c53d4a161395d236ea42be5f99d5cc44dda88dded6d47a1c78e87db684f9c` | canonical 35-case strict corpus rule |
| `SWE-Smith-Bug-Analysis` | `scripts/apply_frozen_families.py` | 7,723 | `56e6c8aa0eda75edb5c06d51cc10c861f760542d5ef5cce779f126ab8c637c31` | pooled fine/family agreement and the hand-rolled kappa |
| `SWE-Smith-Bug-Analysis` | `scripts/compare_reviews.py` | 8,286 | `a1ae03a36b67052abcadc9fcf64ad69bbe9ec83c4eec6c41b4ff4374957927f3` | per-generation-family breakdown |
| `SWE-Smith-Bug-Analysis` | `ssr/swesmith.py` | 8,818 | `410f02408cc65d9d192a49b0c7da937afbe1fb584de2301ffda7530290756b5f` | authoritative generation_method -> method_family mapping |

## Excluded from import

Only the minimum needed to reproduce, plus the provenance needed to prove the seal, was
copied. Neither repository was copied wholesale.

**AIBugAnalysis**

- data/evidence_packets/** (100 evidence packets, not needed to recompute labels)
- data/execution_artifacts/** (agent logs)
- reviews/*/cases/** (verified byte-duplicates of the JSONL)
- data/derived/*.parquet except aidev_rq1_primary_cases.parquet
- scripts/** (cited by hash under reference_scripts instead)

**SWE-Smith-Bug-Analysis**

- data/review_packets/** (100 packet directories)
- reviews/*/cases/** (verified duplicates of the JSONL)
- data/population/swesmith_training_tasks.csv|.parquet (1.0 MB / 293 KB)
- archive/** (parked work, not part of the current design)
- runs/, tests/, the review-draft PDF
- scripts/** and ssr/** (cited by hash under reference_scripts instead)

Additionally not imported: `data/CORPUS_STATUS.json` from the SWE-smith study (it was not on
the approved list; the manifest hashes it carries are already covered by the two `COMPLETE`
markers and the snapshot manifest), and `analysis/rq1/README.md` from the AIDev study (the
strict-corpus rule it states in prose is restated in
`data/derived/aidev_strict_code_state_case_ids.json` and in the reproduce script's docstring).

## Derived reconstructions

`data/derived/aidev_both_assigned_case_ids.json` (49 ids) and
`data/derived/aidev_strict_code_state_case_ids.json` (35 ids) are written by
`scripts/reproduce_headline_results.py` from the imported sealed labels. They restate which
imported cases satisfy a source-study inclusion rule. They are derived reconstructions, not
new classifications, not adjudications, and not a new labelling exercise. The 35-case set is
expected to equal the rows of the imported (never-parsed) `aidev_rq1_primary_cases.parquet`.
