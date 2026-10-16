"""Bootstrap, paired tests, and survey estimators (M5)."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


def paired_deltas(current: list[float], candidate: list[float]) -> list[float]:
    if len(current) != len(candidate):
        raise ValueError("paired scores length mismatch")
    return [c - b for b, c in zip(current, candidate, strict=True)]


def mean(xs: list[float]) -> float:
    if not xs:
        return 0.0
    return sum(xs) / len(xs)


def bootstrap_ci(
    deltas: list[float],
    *,
    alpha: float = 0.05,
    n_boot: int = 500,
    seed: int = 0,
) -> tuple[float, float, float]:
    """Return (mean_delta, lower, upper) for a two-sided (1-alpha) CI."""
    if not deltas:
        return 0.0, 0.0, 0.0
    rng = random.Random(seed)
    n = len(deltas)
    means: list[float] = []
    for _ in range(n_boot):
        sample = [deltas[rng.randrange(n)] for _ in range(n)]
        means.append(mean(sample))
    means.sort()
    lo_idx = max(0, int((alpha / 2) * n_boot))
    hi_idx = min(n_boot - 1, int((1 - alpha / 2) * n_boot))
    return mean(deltas), means[lo_idx], means[hi_idx]


def bootstrap_ci_lower(
    deltas: list[float],
    *,
    alpha: float = 0.05,
    n_boot: int = 500,
    seed: int = 0,
) -> tuple[float, float]:
    m, lo, _ = bootstrap_ci(deltas, alpha=alpha, n_boot=n_boot, seed=seed)
    return m, lo


def estimate_aa_sigma(scores_a: list[float], scores_b: list[float]) -> float:
    """Noise floor from two runs of the same harness on the same tasks (A/A)."""
    if len(scores_a) != len(scores_b):
        raise ValueError("A/A score lists length mismatch")
    if not scores_a:
        return 0.0
    diffs = [abs(b - a) for a, b in zip(scores_a, scores_b, strict=True)]
    return mean(diffs)


@dataclass(frozen=True)
class McNemarResult:
    flipped_to_pass: int
    flipped_to_fail: int
    discordant: int
    chi2: float | None


def mcmnemar(before_passed: list[bool], after_passed: list[bool]) -> McNemarResult:
    if len(before_passed) != len(after_passed):
        raise ValueError("McNemar requires paired outcomes")
    b = 0  # fail -> pass
    c = 0  # pass -> fail
    for before, after in zip(before_passed, after_passed, strict=True):
        if not before and after:
            b += 1
        elif before and not after:
            c += 1
    discordant = b + c
    chi2: float | None = None
    if discordant > 0:
        chi2 = (abs(b - c) - 1) ** 2 / discordant  # continuity correction
    return McNemarResult(
        flipped_to_pass=b,
        flipped_to_fail=c,
        discordant=discordant,
        chi2=chi2,
    )


def horvitz_thompson_mean(
    values: dict[str, float],
    inclusion_probs: dict[str, float],
    population_size: int,
) -> float:
    """
    HT estimator of the population mean when only a subset is observed.

    values: task_id -> metric for tasks included in the sample
    inclusion_probs: task_id -> P(task in sample)
    population_size: N (number of tasks in the full val set)
    """
    if population_size <= 0:
        return 0.0
    total = 0.0
    for tid, y in values.items():
        pi = inclusion_probs.get(tid)
        if pi is None or pi <= 0:
            raise ValueError(f"missing or invalid inclusion prob for {tid!r}")
        total += y / pi
    return total / population_size


def hajek_mean(
    values: dict[str, float],
    inclusion_probs: dict[str, float],
) -> float:
    """Hájek ratio estimator (stable when inclusion probs vary)."""
    num = 0.0
    den = 0.0
    for tid, y in values.items():
        pi = inclusion_probs.get(tid)
        if pi is None or pi <= 0:
            raise ValueError(f"missing or invalid inclusion prob for {tid!r}")
        num += y / pi
        den += 1.0 / pi
    if den == 0:
        return 0.0
    return num / den


def minimum_detectable_effect_half_width(
    n_tasks: int,
    *,
    discordant_fraction: float = 0.2,
    alpha: float = 0.05,
) -> float:
    """
    Conservative normal approx: half-width of 95% CI for a paired pass-rate delta.

    Uses z * sqrt(d / n) where d is an assumed discordant fraction.
    """
    if n_tasks <= 0:
        return 1.0
    z = 1.96 if alpha == 0.05 else 1.96
    d = max(discordant_fraction, 1e-9)
    return z * math.sqrt(d / n_tasks)


def uniform_inclusion_probs(task_ids: list[str], sample_ids: list[str]) -> dict[str, float]:
    """P(task in sample) under simple random sampling without replacement."""
    n = len(task_ids)
    m = len(sample_ids)
    if n == 0:
        return {}
    p = m / n
    return {tid: p if tid in sample_ids else 0.0 for tid in task_ids}
