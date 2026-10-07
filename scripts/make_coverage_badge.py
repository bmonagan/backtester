"""Render docs/coverage.svg from the .coverage data file.

Run after a coverage-enabled test run:
    uv run pytest -q --cov
    uv run python scripts/make_coverage_badge.py
"""

import os
import sys

from coverage import Coverage

COLORS = [
    (90, "#4c1"),      # brightgreen
    (80, "#97ca00"),   # green
    (70, "#a4a61d"),   # yellowgreen
    (60, "#dfb317"),   # yellow
    (50, "#fe7d37"),   # orange
    (0, "#e05d44"),    # red
]

TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="108" height="20" '
    'role="img" aria-label="coverage: {pct}%">'
    '<title>coverage: {pct}%</title>'
    '<linearGradient id="s" x2="0" y2="100%">'
    '<stop offset="0" stop-color="#bbb" stop-opacity=".1"/>'
    '<stop offset="1" stop-opacity=".1"/></linearGradient>'
    '<clipPath id="r"><rect width="108" height="20" rx="3" fill="#fff"/></clipPath>'
    '<g clip-path="url(#r)">'
    '<rect width="62" height="20" fill="#555"/>'
    '<rect x="62" width="46" height="20" fill="{color}"/>'
    '<rect width="108" height="20" fill="url(#s)"/></g>'
    '<g fill="#fff" text-anchor="middle" '
    'font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">'
    '<text x="31" y="15" fill="#010101" fill-opacity=".3">coverage</text>'
    '<text x="31" y="14">coverage</text>'
    '<text x="84" y="15" fill="#010101" fill-opacity=".3">{pct}%</text>'
    '<text x="84" y="14">{pct}%</text></g></svg>'
)


def color_for(pct: int) -> str:
    return next(c for threshold, c in COLORS if pct >= threshold)


def render_svg(pct: int) -> str:
    return TEMPLATE.format(pct=pct, color=color_for(pct))


def main(out: str = "docs/coverage.svg") -> str:
    if not os.path.exists(".coverage"):
        print("no .coverage file; run pytest --cov first", file=sys.stderr)
        raise SystemExit(1)
    cov = Coverage()
    cov.load()
    total = cov.report(show_missing=False, file=open(os.devnull, "w"))
    pct = int(round(total))
    if os.path.dirname(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(render_svg(pct))
    print(f"coverage {pct}% -> {out}")
    return out


if __name__ == "__main__":
    main()
