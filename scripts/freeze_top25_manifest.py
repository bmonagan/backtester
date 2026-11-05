"""Create or verify the frozen top-25 selection manifest."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = Path("docs/cross-asset-strategy-results-2025-11-to-2026-10.csv")
SNAPSHOT_PATH = Path("docs/sample-cross-asset-2025-06-to-2026-10.parquet")
MANIFEST_PATH = Path("docs/top-25-strict-backtest-manifest.json")

DISCOVERY_START = "2025-11-01"
DISCOVERY_END = "2026-10-31"
HOLDOUT_START = "2026-11-03"
HOLDOUT_END = "2027-11-02"
SELECTION_PARAMETERS = {
    ("VWAP mean reversion", "10:1.0"): {"period": 10, "num_std": 1.0},
    ("RSI", "14:30/70"): {"period": 14, "oversold": 30, "overbought": 70},
    ("VWAP mean reversion", "20:1.5"): {"period": 20, "num_std": 1.5},
    ("RSI", "7:30/70"): {"period": 7, "oversold": 30, "overbought": 70},
    ("Williams %R", "14:-90/-10"): {"period": 14, "oversold": -90, "overbought": -10},
    ("CCI", "20:-150/150"): {"period": 20, "entry_level": -150, "exit_level": 150},
    ("Bollinger", "20:1.5"): {"period": 20, "num_std": 1.5},
    ("RSI", "14:40/60"): {"period": 14, "oversold": 40, "overbought": 60},
    ("Stochastic", "14:20/80"): {"period": 14, "oversold": 20, "overbought": 80},
    ("Williams %R", "14:-80/-20"): {"period": 14, "oversold": -80, "overbought": -20},
    ("Bollinger", "20:2.0"): {"period": 20, "num_std": 2.0},
    ("Bollinger", "10:2.0"): {"period": 10, "num_std": 2.0},
    ("CCI", "20:-100/100"): {"period": 20, "entry_level": -100, "exit_level": 100},
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: Path = ROOT) -> dict:
    results_path = root / RESULTS_PATH
    snapshot_path = root / SNAPSHOT_PATH
    with results_path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    if len(rows) < 25:
        raise ValueError(f"{results_path} contains fewer than 25 ranked results")

    top_rows = []
    for rank, row in enumerate(rows[:25], start=1):
        key = (row["strategy"], row["variant"])
        if key not in SELECTION_PARAMETERS:
            raise ValueError(f"No frozen parameters for strategy variant {key}")
        top_rows.append(
            {
                "rank": rank,
                "asset_class": row["asset_class"],
                "symbol": row["symbol"],
                "strategy": row["strategy"],
                "variant": row["variant"],
                "parameters": SELECTION_PARAMETERS[key],
                "source_metrics": {
                    name: value
                    for name, value in row.items()
                    if name not in {"asset_class", "symbol", "strategy", "variant"}
                },
            }
        )

    snapshot_index = pd.read_parquet(snapshot_path, columns=["Symbol"]).index
    snapshot_last_date = str(pd.Timestamp(snapshot_index.max()).date())
    if snapshot_last_date >= HOLDOUT_START:
        raise ValueError(
            f"Snapshot ends on {snapshot_last_date}, which overlaps holdout "
            f"starting {HOLDOUT_START}"
        )

    return {
        "schema_version": 1,
        "frozen_date": "2026-11-05",
        "selection": {
            "ranking": "descending source CSV Sharpe; original tie-break order retained",
            "count": 25,
            "discovery_start": DISCOVERY_START,
            "discovery_end": DISCOVERY_END,
            "results_csv": RESULTS_PATH.as_posix(),
            "results_csv_sha256": _sha256(results_path),
            "market_data_snapshot": SNAPSHOT_PATH.as_posix(),
            "market_data_snapshot_sha256": _sha256(snapshot_path),
            "market_data_last_date": snapshot_last_date,
            "rows": top_rows,
        },
        "holdout": {
            "start": HOLDOUT_START,
            "end": HOLDOUT_END,
            "status": "predeclared_not_run",
            "selection_locked": True,
            "rule": (
                "Do not change top-25 membership, strategy variants, or parameters "
                "based on any observation from this period."
            ),
        },
        "limitations": [
            (
                "The discovery universe is the original five selected instruments per "
                "asset class, not a survivorship-aware historical universe."
            ),
            "The continuous Yahoo futures symbols are not individual tradable expiries.",
            (
                "The frozen ranking is an exploratory unit-notional P&L Sharpe proxy, "
                "not funded-account performance."
            ),
        ],
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="write the frozen manifest instead of verifying the checked-in copy",
    )
    args = parser.parse_args(argv)
    manifest_path = ROOT / MANIFEST_PATH
    expected = build_manifest()
    if args.write:
        manifest_path.write_text(json.dumps(expected, indent=2) + "\n")
        print(f"Wrote {manifest_path.relative_to(ROOT)}")
        return

    actual = json.loads(manifest_path.read_text())
    if actual != expected:
        raise SystemExit(
            f"{manifest_path.relative_to(ROOT)} differs from the frozen source inputs; "
            "inspect changes before regenerating with --write"
        )
    print(f"Verified {manifest_path.relative_to(ROOT)}: 25 rows and frozen input hashes match")


if __name__ == "__main__":
    main()
