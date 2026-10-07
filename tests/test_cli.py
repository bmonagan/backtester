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


def test_parser_defaults():
    args = build_parser().parse_args([])
    assert args.strategy == "sma"
    assert args.cash == 1000000.0


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
    with pytest.raises(ValueError):
        main(["--data", path, "--compare", "nope"])
