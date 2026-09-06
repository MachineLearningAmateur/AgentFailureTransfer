"""Phase 2 — ODC external-taxonomy control: the deterministic plumbing.

Nothing in the bundled part of this subpackage interprets a defect, scores a
reviewer, or computes an agreement statistic. It does six mechanical jobs:

``paths``           locate a Phase 2 root, in the repository or inside an
                    exported reviewer bundle, and name everything inside it.
``taxonomy``        load and check the frozen ODC Defect Type rubric, and
                    compute the taxonomy fingerprint recorded in every seal.
``packets``         the 100 frozen evidence packets: expected case ids, the
                    snapshot manifest, per-file hashes and the packet digest.
``review_records``  parse and validate one reviewer record (JSON or YAML)
                    against ``schemas/odc_review_result.schema.json``.
``state``           the workflow state machine, the reviewer write boundary,
                    the finalization lock, and finalization itself.
``bundle``          export a physically isolated single-reviewer bundle and
                    refuse to publish a contaminated one.
``freeze``          hash every protocol-critical artifact and detect drift.

One module is different in kind and is never bundled:

``analysis``        the post-review comparison (ODC agreement, the paired
                    McNemar and bootstrap against Phase 1, the generation-family
                    join). It refuses to load anything below ``BOTH_COMPLETE``
                    and is listed in ``bundle.BUNDLE_EXCLUDED_LIBRARY_MODULES``.

The bundled modules import only the standard library, ``pyyaml``, and the two
dependency-free helpers ``agentfailuretransfer.hashing`` and
``agentfailuretransfer.reviews``. That is deliberate: a reviewer bundle ships
those modules and must not need numpy, scipy, or any module whose text
describes a Phase 1 result.
"""

from __future__ import annotations

#: Raised for every hard failure in the Phase 2 tooling. The scripts print it
#: with a ``STOP:`` prefix and exit 1 without leaving a partial artifact.
class Phase2Error(RuntimeError):
    """A Phase 2 operation cannot proceed safely."""


__all__ = ["Phase2Error"]
