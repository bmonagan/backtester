import pandas as pd
import pytest

from backtester.main import build_parser, main


def _make_parquet(tmp_path):
    idx = pd.date_range("2020-01-02", periods=60, freq="D")
    closes = list(range(60))
    df = pd.DataFrame(
        {
            "Open": closes,
            "High": closes,
            "Low": closes,
            "Close": closes,
            "Volume": [100] * 60,
            "Symbol": ["AAPL"] * 60,
        },
        index=idx,
    )
    path = str(tmp_path / "synth.parquet")
    df.to_parquet(path)
    return path


def _make_parquet_closes(tmp_path, closes, name="series.parquet"):
    idx = pd.date_range("2020-01-02", periods=len(closes), freq="D")
    df = pd.DataFrame(
        {
            "Open": closes, "High": closes, "Low": closes, "Close": closes,
            "Volume": [100] * len(closes), "Symbol": ["AAPL"] * len(closes),
        },
        index=idx,
    )
    path = str(tmp_path / name)
    df.to_parquet(path)
    return path


def test_parser_defaults():
    args = build_parser().parse_args([])
    assert args.strategy == "sma"
    assert args.cash == 100000.0
    assert args.notional is None
    assert args.fraction is None
    assert args.allow_shorts is False


def _run_args(path, *extra):
    return [
        "--data", path, "--start", "2020-01-01", "--end", "2020-12-31",
        "--cash", "10000", *extra,
    ]


def test_main_runs_and_writes_csv(tmp_path, capsys):
    path = _make_parquet(tmp_path)
    out = str(tmp_path / "equity.csv")
    main(_run_args(path, "--out-csv", out))
    captured = capsys.readouterr()
    assert "Final equity" in captured.out
    assert "Sharpe" in captured.out
    with open(out) as f:
        header = f.readline()
    assert "total_equity" in header


def test_compare_prints_table(tmp_path, capsys):
    path = _make_parquet(tmp_path)
    main(_run_args(path, "--compare", "sma,buyhold"))
    out = capsys.readouterr().out
    assert "sma" in out and "buyhold" in out
    assert "sharpe" in out


def test_compare_writes_csv(tmp_path):
    path = _make_parquet(tmp_path)
    out = str(tmp_path / "compare.csv")
    main(_run_args(path, "--compare", "sma,rsi", "--out-csv", out))
    with open(out) as f:
        header = f.readline()
    assert "strategy" in header and "sharpe" in header


def test_compare_rejects_unknown(tmp_path):
    path = _make_parquet(tmp_path)
    with pytest.raises(SystemExit):
        main(["--data", path, "--compare", "nope"])


def test_compare_rejects_empty_names(tmp_path):
    path = _make_parquet(tmp_path)
    out = str(tmp_path / "empty.csv")
    with pytest.raises(SystemExit):
        main(["--data", path, "--compare", ",", "--out-csv", out])


def test_conflicting_sizing_flags_rejected(tmp_path):
    path = _make_parquet(tmp_path)
    with pytest.raises(SystemExit):
        main(["--data", path, "--notional", "1000", "--fraction", "0.5"])


def test_notional_sizing_runs(tmp_path, capsys):
    path = _make_parquet(tmp_path)
    main(_run_args(path, "--notional", "5000"))
    assert "Final equity" in capsys.readouterr().out


def test_fraction_sizing_runs(tmp_path, capsys):
    path = _make_parquet(tmp_path)
    main(_run_args(path, "--strategy", "buyhold", "--fraction", "0.5"))
    assert "Final equity" in capsys.readouterr().out


def _death_cross_path(tmp_path):
    # rising then falling forces a death-cross sell; the trailing bar is
    # where that queued order fills (next-open fill model)
    return _make_parquet_closes(tmp_path, [1.0, 2.0, 3.0, 2.0, 1.0, 1.0])


def test_allow_shorts_opens_short(tmp_path, capsys):
    path = _death_cross_path(tmp_path)
    main(_run_args(path, "--strategy", "sma", "--fast", "2", "--slow", "3", "--allow-shorts"))
    out = capsys.readouterr().out
    assert "'AAPL'" in out
    assert "quantity=-" in out


def test_shorts_rejected_without_flag(tmp_path, capsys):
    path = _death_cross_path(tmp_path)
    main(_run_args(path, "--strategy", "sma", "--fast", "2", "--slow", "3"))
    out = capsys.readouterr().out
    assert "quantity=-" not in out


def test_compare_allow_shorts(tmp_path, capsys):
    path = _death_cross_path(tmp_path)
    main(_run_args(
        path, "--fast", "2", "--slow", "3",
        "--compare", "sma", "--allow-shorts",
    ))
    assert "sma" in capsys.readouterr().out


def test_parser_order_type_defaults():
    args = build_parser().parse_args([])
    assert args.order_type == "market"
    assert args.order_price is None


def test_order_type_requires_price(tmp_path):
    path = _make_parquet(tmp_path)
    with pytest.raises(SystemExit):
        main(_run_args(path, "--order-type", "limit"))


def test_limit_order_fills(tmp_path, capsys):
    path = _make_parquet_closes(tmp_path, [100.0, 100.0, 90.0, 90.0])
    main(_run_args(
        path, "--strategy", "buyhold",
        "--order-type", "limit", "--order-price", "95",
    ))
    out = capsys.readouterr().out
    assert "'AAPL'" in out


def test_limit_order_never_fills(tmp_path, capsys):
    path = _make_parquet_closes(tmp_path, [100.0, 100.0, 90.0, 90.0])
    main(_run_args(
        path, "--strategy", "buyhold",
        "--order-type", "limit", "--order-price", "50",
    ))
    assert "Positions: {}" in capsys.readouterr().out


def test_compare_order_type_runs(tmp_path, capsys):
    path = _make_parquet_closes(tmp_path, [100.0, 100.0, 90.0, 90.0])
    main(_run_args(
        path, "--compare", "buyhold",
        "--order-type", "limit", "--order-price", "95",
    ))
    assert "buyhold" in capsys.readouterr().out
