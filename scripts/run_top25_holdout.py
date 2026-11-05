"""Run the frozen top-25 candidates on the predeclared holdout.

The discovery snapshot is hash-verified and is combined with a separately
supplied holdout parquet. Instrument and cost assumptions must be explicit in
the JSON configuration; this command never invents them.
"""

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from backtester.datafeed import Bar
from backtester.holdout import run_frozen_top25_holdout
from backtester.instruments import (
    ExecutionCostModel,
    FeeSchedule,
    InstrumentSpec,
    MarginSchedule,
)

DEFAULT_MANIFEST = ROOT / "docs/top-25-strict-backtest-manifest.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_assumptions(path: Path):
    config = json.loads(path.read_text())
    specs = {}
    for symbol, values in config["instrument_specs"].items():
        values = dict(values)
        if values.get("fee_schedule") is not None:
            values["fee_schedule"] = FeeSchedule(**values["fee_schedule"])
        if values.get("margin_schedule") is not None:
            values["margin_schedule"] = MarginSchedule(**values["margin_schedule"])
        specs[symbol] = InstrumentSpec(symbol=symbol, **values)
    models = {
        symbol: ExecutionCostModel(**values)
        for symbol, values in config["execution_models"].items()
    }
    return config, specs, models


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--discovery-data", type=Path)
    parser.add_argument("--holdout-data", type=Path, required=True)
    parser.add_argument("--assumptions", type=Path, required=True)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "docs/top25-holdout-results.csv",
    )
    args = parser.parse_args(argv)

    import pandas as pd

    manifest = json.loads(args.manifest.read_text())
    discovery_path = args.discovery_data or ROOT / manifest["selection"]["market_data_snapshot"]
    results_path = ROOT / manifest["selection"]["results_csv"]
    if _sha256(results_path) != manifest["selection"]["results_csv_sha256"]:
        parser.error("frozen results CSV hash does not match the manifest")
    if _sha256(discovery_path) != manifest["selection"]["market_data_snapshot_sha256"]:
        parser.error("frozen discovery data hash does not match the manifest")
    if not args.holdout_data.is_file():
        parser.error(f"holdout data file not found: {args.holdout_data}")

    assumptions, specs, models = _load_assumptions(args.assumptions)
    discovery = pd.read_parquet(discovery_path)
    holdout = pd.read_parquet(args.holdout_data)
    data = pd.concat([discovery, holdout]).sort_index()
    if "Symbol" not in data.columns:
        parser.error("combined parquet data must contain a Symbol column")
    if data.index.has_duplicates:
        duplicate_keys = data.reset_index().duplicated(
            subset=[data.index.name or "index", "Symbol"]
        )
        if duplicate_keys.any():
            parser.error("combined data contains duplicate symbol/timestamp bars")

    candidate_symbols = {
        candidate["symbol"] for candidate in manifest["selection"]["rows"]
    }
    bars = [
        Bar(
            timestamp=timestamp,
            symbol=row.Symbol,
            open=row.Open,
            high=row.High,
            low=row.Low,
            close=row.Close,
            volume=row.Volume,
        )
        for timestamp, row in data.iterrows()
        if row.Symbol in candidate_symbols
    ]
    report_rows = run_frozen_top25_holdout(
        bars,
        manifest,
        instrument_specs=specs,
        execution_models=models,
        starting_cash=assumptions.get("starting_cash", 100_000.0),
        bootstrap_resamples=assumptions.get("bootstrap_resamples", 2_000),
        bootstrap_block_size=assumptions.get("bootstrap_block_size", 5),
        bootstrap_seed=assumptions.get("bootstrap_seed", 0),
    )
    provenance = {
        "manifest_sha256": _sha256(args.manifest),
        "discovery_data_sha256": _sha256(discovery_path),
        "holdout_data_sha256": _sha256(args.holdout_data),
        "assumptions_sha256": _sha256(args.assumptions),
        "holdout_start": manifest["holdout"]["start"],
        "holdout_end": manifest["holdout"]["end"],
    }
    for row in report_rows:
        row.update(provenance)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(report_rows[0]))
        writer.writeheader()
        writer.writerows(report_rows)
    print(f"Wrote {len(report_rows)} candidate/scenario rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
