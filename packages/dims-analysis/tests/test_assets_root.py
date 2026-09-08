"""A private study's data lives outside the repository.

serve.py has always read data.local.json; the analysis did not, so running a
step from a private case directory found no input and reported every pair as
"file not found" -- with the data sitting on disk and the dashboard reading it
happily. These tests pin the resolution rules.
"""
import json
import os

from dims_analysis.common import assets


def _case(tmp_path, root=None):
    case = tmp_path / "case"
    (case / "assets" / "timeseries").mkdir(parents=True)
    if root is not None:
        (case / "data.local.json").write_text(json.dumps({"assetsRoot": str(root)}))
    return case


def test_no_marker_leaves_paths_alone(tmp_path):
    case = _case(tmp_path)
    assert assets.assets_root(str(case)) is None
    assert assets.resolve("assets/timeseries", str(case)) == "assets/timeseries"


def test_marker_redirects_asset_paths(tmp_path):
    data = tmp_path / "elsewhere" / "assets"
    (data / "timeseries").mkdir(parents=True)
    case = _case(tmp_path, data)
    assert assets.assets_root(str(case)) == str(data)
    assert assets.resolve("assets/timeseries", str(case)) == os.path.join(str(data), "timeseries")
    assert assets.resolve("assets", str(case)) == str(data)


def test_a_root_that_does_not_exist_is_ignored(tmp_path):
    """Better to look in the usual place than to fail on a stale path."""
    case = _case(tmp_path, tmp_path / "gone")
    assert assets.assets_root(str(case)) is None
    assert assets.resolve("assets/rqa", str(case)) == "assets/rqa"


def test_only_asset_paths_are_redirected(tmp_path):
    """An explicit --output-dir is the caller being specific: never rewrite it."""
    data = tmp_path / "elsewhere" / "assets"
    data.mkdir(parents=True)
    case = _case(tmp_path, data)
    assert assets.resolve("/tmp/somewhere", str(case)) == "/tmp/somewhere"
    assert assets.resolve("scratch/out", str(case)) == "scratch/out"
    assert assets.resolve("", str(case)) == ""


def test_malformed_marker_does_not_break_a_run(tmp_path):
    case = _case(tmp_path)
    (case / "data.local.json").write_text("{ not json")
    assert assets.assets_root(str(case)) is None
    (case / "data.local.json").write_text(json.dumps({"somethingElse": 1}))
    assert assets.assets_root(str(case)) is None


def test_describe_is_quiet_unless_it_matters(tmp_path):
    data = tmp_path / "elsewhere" / "assets"
    data.mkdir(parents=True)
    assert assets.describe(str(_case(tmp_path))) is None
    case2 = tmp_path / "case2"
    case2.mkdir()
    (case2 / "data.local.json").write_text(json.dumps({"assetsRoot": str(data)}))
    assert str(data) in assets.describe(str(case2))
