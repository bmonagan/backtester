import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import make_coverage_badge  # noqa: E402


def test_render_svg_embeds_percentage():
    svg = make_coverage_badge.render_svg(92)
    assert svg.startswith("<svg")
    assert "coverage" in svg
    assert "92%" in svg


def test_color_thresholds():
    assert make_coverage_badge.color_for(95) == "#4c1"
    assert make_coverage_badge.color_for(85) == "#97ca00"
    assert make_coverage_badge.color_for(10) == "#e05d44"


@pytest.mark.skipif(
    not os.path.exists(".coverage"), reason="needs a prior pytest --cov run"
)
def test_main_writes_file(tmp_path):
    out = str(tmp_path / "cov.svg")
    make_coverage_badge.main(out)
    assert os.path.exists(out)
    assert open(out).read().startswith("<svg")
