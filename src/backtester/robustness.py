"""Resampling and multiple-testing utilities for strategy validation."""

import math
import random
from collections.abc import Iterable, Mapping


def _validated_returns(returns: Iterable[float]) -> list[float]:
    values = list(returns)
    if not values:
        raise ValueError("returns must contain at least one observation")
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        for value in values
    ):
        raise ValueError("returns must be finite numbers")
    return [float(value) for value in values]


def _validate_resampling(
    confidence_level: float,
    resamples: int,
    block_size: int,
) -> None:
    if (
        isinstance(confidence_level, bool)
        or not isinstance(confidence_level, (int, float))
        or not math.isfinite(confidence_level)
        or not 0 < confidence_level < 1
    ):
        raise ValueError("confidence_level must be between zero and one")
    if isinstance(resamples, bool) or not isinstance(resamples, int) or resamples < 1:
        raise ValueError("resamples must be a positive integer")
    if isinstance(block_size, bool) or not isinstance(block_size, int) or block_size < 1:
        raise ValueError("block_size must be a positive integer")


def _sample_circular_blocks(
    values: list[float],
    block_size: int,
    rng: random.Random,
) -> list[float]:
    sample = []
    while len(sample) < len(values):
        start = rng.randrange(len(values))
        sample.extend(values[(start + offset) % len(values)] for offset in range(block_size))
    return sample[: len(values)]


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    lower = math.floor(index)
    upper = math.ceil(index)
    fraction = index - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def block_bootstrap_mean_interval(
    returns: Iterable[float],
    *,
    confidence_level: float = 0.95,
    resamples: int = 2_000,
    block_size: int = 5,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile confidence interval for mean return using circular blocks."""
    values = _validated_returns(returns)
    _validate_resampling(confidence_level, resamples, block_size)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    rng = random.Random(seed)
    means = [
        math.fsum(_sample_circular_blocks(values, block_size, rng)) / len(values)
        for _ in range(resamples)
    ]
    tail = (1 - confidence_level) / 2
    return _quantile(means, tail), _quantile(means, 1 - tail)


def block_bootstrap_mean_pvalue(
    returns: Iterable[float],
    *,
    resamples: int = 2_000,
    block_size: int = 5,
    seed: int = 0,
) -> float:
    """Two-sided bootstrap p-value for zero mean, using centered block samples."""
    values = _validated_returns(returns)
    _validate_resampling(0.95, resamples, block_size)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    observed_mean = math.fsum(values) / len(values)
    centered = [value - observed_mean for value in values]
    rng = random.Random(seed)
    extreme = 0
    for _ in range(resamples):
        sample_mean = math.fsum(
            _sample_circular_blocks(centered, block_size, rng)
        ) / len(centered)
        if abs(sample_mean) >= abs(observed_mean):
            extreme += 1
    return (extreme + 1) / (resamples + 1)


def holm_adjusted_pvalues(pvalues: Iterable[float]) -> list[float]:
    """Return Holm step-down adjusted p-values in the input order."""
    values = list(pvalues)
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0 <= value <= 1
        for value in values
    ):
        raise ValueError("p-values must be finite numbers in [0, 1]")
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    adjusted = [0.0] * len(values)
    running_max = 0.0
    count = len(values)
    for rank, (original_index, pvalue) in enumerate(ordered):
        running_max = max(running_max, (count - rank) * pvalue)
        adjusted[original_index] = min(1.0, running_max)
    return adjusted


def bootstrap_strategy_summary(
    candidate_returns: Mapping[str, Iterable[float]],
    *,
    confidence_level: float = 0.95,
    resamples: int = 2_000,
    block_size: int = 5,
    seed: int = 0,
) -> list[dict]:
    """Summarize every candidate and Holm-adjust bootstrap mean tests.

    Candidate insertion order is retained; this function does not rank or
    select strategies. Resampling confidence intervals and p-values are
    diagnostics and do not correct for selection before the supplied period.
    """
    if not candidate_returns:
        raise ValueError("candidate_returns must not be empty")
    summaries = []
    raw_pvalues = []
    for index, (candidate, returns) in enumerate(candidate_returns.items()):
        values = _validated_returns(returns)
        candidate_seed = seed + index
        lower, upper = block_bootstrap_mean_interval(
            values,
            confidence_level=confidence_level,
            resamples=resamples,
            block_size=block_size,
            seed=candidate_seed,
        )
        pvalue = block_bootstrap_mean_pvalue(
            values,
            resamples=resamples,
            block_size=block_size,
            seed=candidate_seed,
        )
        raw_pvalues.append(pvalue)
        summaries.append(
            {
                "candidate": candidate,
                "observations": len(values),
                "mean_return": math.fsum(values) / len(values),
                "confidence_lower": lower,
                "confidence_upper": upper,
                "p_value": pvalue,
            }
        )
    adjusted = holm_adjusted_pvalues(raw_pvalues)
    for summary, adjusted_pvalue in zip(summaries, adjusted):
        summary["holm_adjusted_p_value"] = adjusted_pvalue
    return summaries
