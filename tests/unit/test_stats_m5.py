import pytest

from rsi_harness.core.stats import (
    bootstrap_ci,
    hajek_mean,
    horvitz_thompson_mean,
    mcmnemar,
    minimum_detectable_effect_half_width,
    uniform_inclusion_probs,
)


def test_mcmnemar_counts_flips() -> None:
    before = [False, True, False, True]
    after = [True, True, False, False]
    r = mcmnemar(before, after)
    assert r.flipped_to_pass == 1
    assert r.flipped_to_fail == 1
    assert r.discordant == 2
    assert r.chi2 == 0.5


def test_horvitz_thompson_uniform_sample() -> None:
    population = ["a", "b", "c", "d"]
    sample = {"a": 1.0, "c": 0.0}
    pis = uniform_inclusion_probs(population, list(sample))
    mean = horvitz_thompson_mean(sample, pis, population_size=len(population))
    assert abs(mean - 0.5) < 1e-9


def test_hajek_matches_ht_on_uniform() -> None:
    values = {"x": 2.0, "y": 4.0}
    pis = {"x": 0.5, "y": 0.5}
    assert hajek_mean(values, pis) == 3.0


def test_bootstrap_ci_brackets_mean() -> None:
    deltas = [1.0, 1.0, 1.0, 1.0]
    mean_d, lo, hi = bootstrap_ci(deltas, n_boot=100, seed=0)
    assert mean_d == 1.0
    assert lo <= mean_d <= hi


def test_mde_shrinks_with_n() -> None:
    assert minimum_detectable_effect_half_width(10) > minimum_detectable_effect_half_width(100)


def test_mcmnemar_length_mismatch() -> None:
    with pytest.raises(ValueError):
        mcmnemar([True], [True, False])
