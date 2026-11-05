import pytest

from backtester.robustness import (
    block_bootstrap_mean_interval,
    block_bootstrap_mean_pvalue,
    bootstrap_strategy_summary,
    holm_adjusted_pvalues,
)


def test_block_bootstrap_interval_is_deterministic_and_contains_constant_mean():
    returns = [0.01] * 20

    first = block_bootstrap_mean_interval(
        returns, resamples=100, block_size=3, seed=17
    )
    second = block_bootstrap_mean_interval(
        returns, resamples=100, block_size=3, seed=17
    )

    assert first == second
    assert first == pytest.approx((0.01, 0.01))


def test_block_bootstrap_mean_pvalue_is_deterministic():
    values = [-0.02, 0.01, -0.01, 0.02] * 8
    assert block_bootstrap_mean_pvalue(
        values, resamples=100, block_size=2, seed=3
    ) == block_bootstrap_mean_pvalue(values, resamples=100, block_size=2, seed=3)


def test_holm_adjustment_preserves_input_order_and_monotonicity():
    assert holm_adjusted_pvalues([0.04, 0.01, 0.03]) == pytest.approx(
        [0.06, 0.03, 0.06]
    )


def test_bootstrap_summary_reports_all_candidates_without_reranking():
    summary = bootstrap_strategy_summary(
        {"frozen-rank-2": [0.02] * 10, "frozen-rank-1": [-0.01] * 10},
        resamples=100,
        block_size=2,
        seed=5,
    )

    assert [row["candidate"] for row in summary] == [
        "frozen-rank-2",
        "frozen-rank-1",
    ]
    assert summary[0]["mean_return"] == pytest.approx(0.02)
    assert summary[1]["mean_return"] == pytest.approx(-0.01)
    assert all("holm_adjusted_p_value" in row for row in summary)


@pytest.mark.parametrize(
    "values",
    [
        [],
        [float("nan")],
        [True],
    ],
)
def test_bootstrap_helpers_reject_invalid_returns(values):
    with pytest.raises(ValueError, match="returns"):
        block_bootstrap_mean_interval(values, resamples=10, block_size=1)


def test_holm_adjustment_rejects_invalid_p_values():
    with pytest.raises(ValueError, match="p-values"):
        holm_adjusted_pvalues([0.1, float("nan")])
