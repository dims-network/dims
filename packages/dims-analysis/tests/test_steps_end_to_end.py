"""Run the shipped steps the way a study runs them, against data on disk.

Nothing else in this suite calls a step's main() or Step.run(). Everything the
steps get wrong lives there: which directory they read, whether they merge or
clobber, whether an empty run reports success. A unit test of a helper cannot
see any of it.

The fixture deliberately puts the data OUTSIDE the project, at the path
data.local.json names, because that is the shape of every private study and it
is where the failure was: rqa and crqa resolved their output directory through
the marker and read their input from a relative path that does not exist -- then
printed "assets resolved" and exited 0 having produced nothing.
"""
import json
import os
import subprocess
import sys

import numpy as np
import pytest

STEPS = ["rqa", "crqa", "crosswavelet"]


def _series(path, n=400, dt=0.02, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n) * dt
    v = np.sin(2 * np.pi * 0.7 * t) + 0.2 * rng.standard_normal(n)
    with open(path, "w") as fh:
        fh.write("Time,value\n")
        for a, b in zip(t, v):
            fh.write(f"{a:.6f},{b:.6f}\n")


def _study(tmp_path, external):
    """A project whose data is either inside it or at an external assetsRoot."""
    project = tmp_path / "study"
    project.mkdir()
    assets = (tmp_path / "elsewhere" / "assets") if external else (project / "assets")
    ts = assets / "timeseries"
    ts.mkdir(parents=True)
    for i, dt_name in enumerate(("alpha", "beta")):
        _series(ts / f"v1_{dt_name}.csv", seed=i)

    config = {
        "videoIDs": ["v1"],
        "dataTypes": {"v1": ["alpha", "beta"]},
        "include_RQA": ["alpha", "beta"],
        "include_cRQA": [["alpha", "beta"]],
        "include_crosswavelet": [["alpha", "beta"]],
    }
    (project / "config.json").write_text(json.dumps(config, indent=2))
    if external:
        (project / "data.local.json").write_text(json.dumps({"assetsRoot": str(assets)}))
    return project, assets


def _run(step, project, extra=()):
    return subprocess.run(
        [sys.executable, "-m", f"dims_analysis.steps.{step}",
         "--config", "config.json", *extra],
        cwd=str(project), capture_output=True, text=True,
    )


@pytest.mark.parametrize("step", STEPS)
@pytest.mark.parametrize("external", [False, True], ids=["data-in-project", "data-outside"])
def test_step_finds_its_input_and_writes_output(tmp_path, step, external):
    project, assets = _study(tmp_path, external)
    proc = _run(step, project)
    assert proc.returncode == 0, proc.stdout + proc.stderr

    out_dir = assets / {"rqa": "rqa", "crqa": "crqa", "crosswavelet": "crosswavelet"}[step]
    produced = sorted(out_dir.glob("*.json")) if out_dir.exists() else []
    assert produced, (
        f"{step} produced no JSON.\n"
        f"looked in {out_dir}\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    )
    payload = json.loads(produced[0].read_text())
    assert payload, f"{step} wrote an empty payload"


@pytest.mark.parametrize("step", STEPS)
def test_the_resolved_input_is_where_the_data_actually_is(tmp_path, step):
    """The banner must not be printable while the step reads somewhere else.

    rqa printed 'assets resolved through data.local.json' and then read a
    relative path, which is a worse failure than not resolving at all: the log
    says the mechanism worked.
    """
    project, assets = _study(tmp_path, external=True)
    proc = _run(step, project)
    assert "assets resolved through data.local.json" in proc.stdout, proc.stdout
    assert "File not found" not in proc.stdout, (
        f"{step} announced it resolved the assets root, then failed to read from it:\n"
        + proc.stdout
    )
    assert "Missing:" not in proc.stdout, proc.stdout
