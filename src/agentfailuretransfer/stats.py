"""Uncertainty and association statistics for the Phase 1B robustness analysis.

Nothing here interprets, reclassifies or adjudicates a label. These are plain
estimators applied to the already-sealed reviewer labels:

* :func:`wilson_interval` -- score (Wilson) interval for a binomial proportion.
  A naive normal (Wald) interval is deliberately not provided: the agreement
  proportions here include small subgroups where Wald is badly behaved.
* :func:`cohen_kappa_or_none` -- the SAME unweighted kappa as
  :func:`agentfailuretransfer.agreement.cohen_kappa`, except that the degenerate
  case returns ``None`` instead of being collapsed to ``0.0``/``1.0``.
* :func:`bootstrap_kappa` -- case-level paired nonparametric bootstrap of kappa.
* :func:`risk_difference_newcombe`, :func:`risk_ratio_wald`,
  :func:`odds_ratio_woolf` -- effect sizes with intervals.
* :func:`permutation_difference_test` -- exploratory permutation check on a
  difference of two proportions.

Why two kappa degenerate rules exist
------------------------------------

``agreement.cohen_kappa`` reproduces the *published* source-study numbers, and
both source studies needed a defined value for every reported cell, so a
degenerate replicate (expected agreement exactly 1.0, or ``n == 0``) is mapped
to ``0.0`` unless observed agreement is 1.0.

That rule is wrong for a bootstrap. A resample in which both reviewers happen to
use exactly one label, and the same one, carries no information about kappa;
folding it in as a hard ``0.0`` (or ``1.0``) would shift the percentile interval
by an artefact of the degenerate rule rather than by the data. So the bootstrap
uses :func:`cohen_kappa_or_none`, *excludes* undefined replicates from the
percentile interval, and reports how many there were. The two rules agree on
every non-degenerate input; the tests assert that.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
from scipy import stats

#: Two-sided 95% normal quantile, computed rather than typed.
Z_95 = float(stats.norm.ppf(0.975))


def _z(confidence: float) -> float:
    return float(stats.norm.ppf(1.0 - (1.0 - confidence) / 2.0))


def wilson_interval(
    successes: int, n: int, confidence: float = 0.95
) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Returns ``(low, high)``, clipped to ``[0, 1]``. ``n == 0`` yields
    ``(0.0, 1.0)`` -- an interval carrying no information, never a point.
    """
    if successes < 0 or n < 0 or successes > n:
        raise ValueError(f"invalid binomial counts: {successes}/{n}")
    if n == 0:
        return (0.0, 1.0)
    z = _z(confidence)
    p = successes / n
    denominator = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / denominator
    half_width = (
        z * np.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denominator
    )
    # 0 and n successes have exactly 0 and 1 as the corresponding endpoint;
    # pinning them avoids a 1e-17 float residue in the emitted artifacts.
    low = 0.0 if successes == 0 else max(0.0, float(centre - half_width))
    high = 1.0 if successes == n else min(1.0, float(centre + half_width))
    return (low, high)


def cohen_kappa_or_none(
    left: Sequence[str], right: Sequence[str]
) -> float | None:
    """Unweighted Cohen's kappa, or ``None`` when it is undefined.

    Undefined means ``n == 0`` or expected agreement exactly ``1.0`` (the 0/0
    case). Contrast with :func:`agentfailuretransfer.agreement.cohen_kappa`,
    which collapses those to a defined value so that the published source-study
    tables reproduce.
    """
    if len(left) != len(right):
        raise ValueError(
            f"rater sequences differ in length: {len(left)} vs {len(right)}"
        )
    total = len(left)
    if total == 0:
        return None
    observed = sum(a == b for a, b in zip(left, right)) / total
    labels = sorted(set(left) | set(right))
    left_counts = {label: 0 for label in labels}
    right_counts = {label: 0 for label in labels}
    for value in left:
        left_counts[value] += 1
    for value in right:
        right_counts[value] += 1
    expected = sum(
        (left_counts[label] / total) * (right_counts[label] / total)
        for label in labels  # sorted: deterministic float summation order
    )
    if expected >= 1.0:
        return None
    return (observed - expected) / (1.0 - expected)


def _encode_pairs(
    left: Sequence[str], right: Sequence[str]
) -> tuple[np.ndarray, np.ndarray, int]:
    labels = sorted(set(left) | set(right))
    codes = {label: index for index, label in enumerate(labels)}
    encoded_left = np.array([codes[value] for value in left], dtype=np.int64)
    encoded_right = np.array([codes[value] for value in right], dtype=np.int64)
    return encoded_left, encoded_right, len(labels)


def bootstrap_kappa(
    left: Sequence[str],
    right: Sequence[str],
    *,
    seed: int | Sequence[int],
    replicates: int = 10000,
    confidence: float = 0.95,
) -> dict:
    """Case-level paired nonparametric bootstrap of unweighted Cohen's kappa.

    Cases (rows) are resampled with replacement; the two reviewers' labels for a
    resampled case always travel together, so the pairing is never broken. A
    replicate whose kappa is undefined (expected agreement exactly 1.0) is
    counted in ``undefined_replicates`` and excluded from the percentile
    interval -- it is never silently mapped to 0.

    ``seed`` is passed to ``numpy.random.default_rng``; callers wanting
    independent streams per population should pass a distinct seed sequence.
    """
    if len(left) != len(right):
        raise ValueError(
            f"rater sequences differ in length: {len(left)} vs {len(right)}"
        )
    if replicates <= 0:
        raise ValueError("replicates must be positive")
    n = len(left)
    point = cohen_kappa_or_none(left, right)

    estimates: list[float] = []
    undefined = 0
    if n > 0:
        encoded_left, encoded_right, n_labels = _encode_pairs(left, right)
        rng = np.random.default_rng(seed)
        for _ in range(replicates):
            index = rng.integers(0, n, size=n)
            sample_left = encoded_left[index]
            sample_right = encoded_right[index]
            observed = float(np.count_nonzero(sample_left == sample_right)) / n
            left_p = np.bincount(sample_left, minlength=n_labels) / n
            right_p = np.bincount(sample_right, minlength=n_labels) / n
            expected = float(np.dot(left_p, right_p))
            if expected >= 1.0:
                undefined += 1
                continue
            estimates.append((observed - expected) / (1.0 - expected))
    else:
        undefined = replicates

    lower_pct = 100.0 * (1.0 - confidence) / 2.0
    upper_pct = 100.0 - lower_pct
    if estimates:
        array = np.array(estimates, dtype=float)
        ci_low = float(np.percentile(array, lower_pct))
        ci_high = float(np.percentile(array, upper_pct))
        mean = float(array.mean())
        std = float(array.std(ddof=1)) if len(array) > 1 else None
    else:
        ci_low = ci_high = mean = std = None

    return {
        "point_estimate": point,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "ci_method": f"percentile bootstrap ({confidence:.0%})",
        "replicates": replicates,
        "valid_replicates": len(estimates),
        "undefined_replicates": undefined,
        "bootstrap_mean": mean,
        "bootstrap_sd": std,
        "seed": seed,
        "n": n,
    }


def risk_difference_newcombe(
    successes_1: int,
    n_1: int,
    successes_2: int,
    n_2: int,
    confidence: float = 0.95,
) -> dict:
    """Difference of two independent proportions, Newcombe hybrid score interval.

    Newcombe (1998) "method 10": the interval for ``p1 - p2`` is built from the
    two separate Wilson score intervals, which behaves far better than a Wald
    interval at the small subgroup sizes here.
    """
    p1 = successes_1 / n_1 if n_1 else float("nan")
    p2 = successes_2 / n_2 if n_2 else float("nan")
    low_1, high_1 = wilson_interval(successes_1, n_1, confidence)
    low_2, high_2 = wilson_interval(successes_2, n_2, confidence)
    difference = p1 - p2
    lower = difference - np.sqrt((p1 - low_1) ** 2 + (high_2 - p2) ** 2)
    upper = difference + np.sqrt((high_1 - p1) ** 2 + (p2 - low_2) ** 2)
    return {
        "risk_difference": float(difference),
        "ci_low": float(max(-1.0, lower)),
        "ci_high": float(min(1.0, upper)),
        "ci_method": "Newcombe hybrid score interval (Wilson-based)",
    }


def risk_ratio_wald(
    successes_1: int,
    n_1: int,
    successes_2: int,
    n_2: int,
    confidence: float = 0.95,
) -> dict:
    """Risk ratio ``p1 / p2`` with a log-scale (Katz) Wald interval."""
    p1 = successes_1 / n_1 if n_1 else float("nan")
    p2 = successes_2 / n_2 if n_2 else float("nan")
    if successes_1 == 0 or successes_2 == 0 or n_1 == 0 or n_2 == 0:
        return {
            "risk_ratio": float(p1 / p2) if p2 else None,
            "ci_low": None,
            "ci_high": None,
            "ci_method": (
                "log risk ratio Wald interval (undefined: a zero cell in a "
                "numerator; no continuity correction is applied)"
            ),
        }
    z = _z(confidence)
    ratio = p1 / p2
    standard_error = np.sqrt(
        1.0 / successes_1 - 1.0 / n_1 + 1.0 / successes_2 - 1.0 / n_2
    )
    return {
        "risk_ratio": float(ratio),
        "ci_low": float(np.exp(np.log(ratio) - z * standard_error)),
        "ci_high": float(np.exp(np.log(ratio) + z * standard_error)),
        "ci_method": "log risk ratio Wald (Katz) interval",
    }


def odds_ratio_woolf(
    a: int, b: int, c: int, d: int, confidence: float = 0.95
) -> dict:
    """Sample odds ratio ``(a*d)/(b*c)`` with a Woolf log-scale interval."""
    if min(a, b, c, d) == 0:
        return {
            "odds_ratio": None if (b == 0 or c == 0) else float(a * d) / (b * c),
            "ci_low": None,
            "ci_high": None,
            "ci_method": (
                "Woolf log odds ratio interval (undefined: a zero cell; no "
                "continuity correction is applied)"
            ),
        }
    z = _z(confidence)
    ratio = (a * d) / (b * c)
    standard_error = np.sqrt(1.0 / a + 1.0 / b + 1.0 / c + 1.0 / d)
    return {
        "odds_ratio": float(ratio),
        "ci_low": float(np.exp(np.log(ratio) - z * standard_error)),
        "ci_high": float(np.exp(np.log(ratio) + z * standard_error)),
        "ci_method": "Woolf log odds ratio interval",
    }


def permutation_difference_test(
    indicators: Sequence[int],
    group_size: int,
    *,
    seed: int | Sequence[int],
    permutations: int = 10000,
) -> dict:
    """Two-sided permutation test on a difference of two group proportions.

    ``indicators`` are the per-case binary outcomes of the pooled population and
    ``group_size`` is the size of the first group. Group membership is permuted
    with the observed group sizes held fixed; the statistic is
    ``mean(group 1) - mean(group 2)``. The reported p-value uses the add-one
    convention ``(1 + #{|permuted| >= |observed|}) / (1 + permutations)``, which
    is never exactly 0.
    """
    values = np.asarray(indicators, dtype=float)
    total = values.size
    if not 0 < group_size < total:
        raise ValueError(
            f"group_size {group_size} must be strictly inside 0..{total}"
        )
    if permutations <= 0:
        raise ValueError("permutations must be positive")

    other_size = total - group_size
    grand_total = float(values.sum())

    # The caller supplies the indicators already ordered group-1-first.
    group_1_total = float(values[:group_size].sum())
    observed = group_1_total / group_size - (grand_total - group_1_total) / other_size

    rng = np.random.default_rng(seed)
    at_least_as_extreme = 0
    differences = np.empty(permutations, dtype=float)
    for index in range(permutations):
        permuted = rng.permutation(values)
        first = float(permuted[:group_size].sum())
        difference = first / group_size - (grand_total - first) / other_size
        differences[index] = difference
        if abs(difference) >= abs(observed) - 1e-12:
            at_least_as_extreme += 1

    return {
        "observed_difference": observed,
        "permutations": permutations,
        "count_at_least_as_extreme": at_least_as_extreme,
        "p_value_two_sided": (1.0 + at_least_as_extreme) / (1.0 + permutations),
        "p_value_convention": (
            "(1 + #{|permuted difference| >= |observed difference|}) / "
            "(1 + permutations)"
        ),
        "permutation_mean_difference": float(differences.mean()),
        "seed": seed,
    }
