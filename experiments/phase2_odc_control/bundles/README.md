# Reviewer bundles

**Nothing in this directory but this file.** Bundles are generated artifacts, not source, and
they are not committed.

A bundle is a physically isolated working directory for one Phase 2 reviewer. There is one per
reviewer, both generated from the same frozen commit by:

```bash
python scripts/make_phase2_review_bundle.py --reviewer <claude|codex> --out <path outside this repo>
```

The output path is **outside this repository**, because the repository contains Phase 1 results
and the point of the bundle is that a reviewer cannot reach them.

## What a bundle contains

```text
ODC reviewer instructions
frozen ODC taxonomy
review schema
validator
the 100 frozen evidence packets
review manifest / packet hashes
empty reviewer output directory
```

## What a bundle physically excludes

```text
Phase 1 reviewer labels
Phase 1 reports
generation metadata
hidden sample mapping
other reviewer's Phase 2 output
AIDev data
cross-corpus analysis
```

There is no `hidden/` and no `analysis/` directory inside a bundle, by design.

The bundle creator scans for forbidden paths and forbidden content and **refuses to export a
contaminated bundle**. A refusal is a stop condition to report, not an obstacle to work around
by deleting the offending file and re-exporting.

Both bundles must come from the same frozen commit, so that any difference between the two
reviews cannot be a difference between the two instruments. Before a review starts,
`scripts/check_phase2_ready.py --reviewer <name>` re-verifies the bundle against the freeze
manifest; if any hash differs, no review is launched.

See [`../protocol/blinding_protocol.md`](../protocol/blinding_protocol.md) for the full rules.

## Version control

This directory is gitignored except for this README. Generated bundles are reproducible from the
frozen commit and carry no information that is not already in the repository, so there is nothing
to preserve by committing them — and committing one would put a reviewer-facing copy of the
evidence in a second place that could drift from the first.
