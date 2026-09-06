"""Exact agreement and an auditable unweighted Cohen's kappa.

The two source studies used two different kappa implementations:

* ``AIBugAnalysis`` used ``sklearn.metrics.cohen_kappa_score`` (unweighted, no
  explicit ``labels=``), stored at full precision.
* ``SWE-Smith-Bug-Analysis`` used a hand-written kappa rounded to 4 decimals,
  with a degenerate guard for ``expected_agreement >= 1.0``.

They are numerically equivalent for the unweighted case. This repository uses a
single hand-rolled implementation (below) so that the computation is auditable
in place with no dependency on a library version, and reports the value at full
precision alongside a 4-decimal rounding. The tests cross-check it against
``sklearn.metrics.cohen_kappa_score`` on non-degenerate inputs.

Degenerate-case rule (documented, deliberate):

* ``n == 0``            -> kappa is defined as ``0.0``.
* ``expected == 1.0``   -> kappa is defined as ``1.0`` if observed agreement is
  1.0, otherwise ``0.0``. (This is the same guard the SWE-smith study used; it
  avoids a 0/0 division when both raters used exactly one label each and those
  label sets coincide.)

Note that a subgroup with disjoint label sets (for example the ``combine``
subgroup, n=2) has expected agreement 0.0 and observed agreement 0.0, so kappa
is a genuine ``(0 - 0) / (1 - 0) = 0.0`` and NOT an undefined value. An
implementation that returns ``nan`` or ``None`` there will not reproduce the
published number.
"""

from __future__ import annotations

from collections import Counter
from typing import Sequence


def cohen_kappa(left: Sequence[str], right: Sequence[str]) -> float:
    """Unweighted Cohen's kappa over the union of both raters' observed labels."""
    if len(left) != len(right):
        raise ValueError(
            f"rater sequences differ in length: {len(left)} vs {len(right)}"
        )
    total = len(left)
    if total == 0:
        return 0.0

    observed = sum(a == b for a, b in zip(left, right)) / total
    left_counts = Counter(left)
    right_counts = Counter(right)
    expected = sum(
        (left_counts[label] / total) * (right_counts[label] / total)
        for label in sorted(set(left) | set(right))  # sorted: deterministic float sum
    )
    if expected >= 1.0:
        return 1.0 if observed >= 1.0 else 0.0
    return (observed - expected) / (1.0 - expected)


def agreement(left: Sequence[str], right: Sequence[str]) -> dict:
    """Exact-agreement counts plus kappa at full precision and 4 decimals."""
    if len(left) != len(right):
        raise ValueError(
            f"rater sequences differ in length: {len(left)} vs {len(right)}"
        )
    total = len(left)
    exact = int(sum(a == b for a, b in zip(left, right)))
    kappa = cohen_kappa(left, right)
    return {
        "n": total,
        "exact_agreements": exact,
        "agreement_rate": (exact / total) if total else None,
        "agreement_rate_4dp": round(exact / total, 4) if total else None,
        "cohens_kappa": kappa,
        "cohens_kappa_4dp": round(kappa, 4),
    }
