"""A study can set the recurrence window and rate without editing a script.

`docs/contracts/config.schema.json` documents `analysis.<step>.window` and
`.step`, and for a long time neither recurrence step read them: the window was
an argparse flag the Step adapter never passed, so the documented setting did
nothing at all. The contract's own rule (step.md) is that tuning which can only
be changed by editing the source is how a fork ends up maintaining its own copy
of an analysis.
"""
import json
import os
import subprocess
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))


def study(tmp_path, tuning=None, n=2000, dt=0.02):
    """A minimal study with one recording and two measures."""
    ts = tmp_path / "assets" / "timeseries"
    ts.mkdir(parents=True)
    t = np.arange(n) * dt
    for name, series in (("a", np.sin(2 * np.pi * 0.5 * t)),
                         ("b", np.sin(2 * np.pi * 0.5 * (t - 0.4)))):
        with open(ts / f"v1_{name}.csv", "w") as fh:
            fh.write("Time,value\n")
            for ti, vi in zip(t, series):
                fh.write(f"{ti:.4f},{vi:.6f}\n")
    config = {"videoIDs": ["v1"], "dataTypes": {"v1": ["a", "b"]},
              "include_RQA": ["a"], "include_cRQA": [["a", "b"]]}
    if tuning:
        config["analysis"] = tuning
    (tmp_path / "config.json").write_text(json.dumps(config, indent=2))
    return str(tmp_path)


def run(project, steps):
    r = subprocess.run([sys.executable, "-m", "dims_analysis.cli", "run",
                        "--config", "config.json", "--steps", steps],
                       cwd=project, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    return r.stdout


def entry(project, analysis, container, name):
    path = os.path.join(project, "assets", analysis, f"v1_{analysis}_data.json")
    with open(path) as fh:
        return json.load(fh)[container][name]


@pytest.mark.parametrize("step,container,name,key", [
    ("rqa", "rqa_data", "a", "rqa"),
    ("crqa", "crqa_data", "a_vs_b", "crqa"),
])
def test_the_window_comes_from_config(tmp_path, step, container, name, key):
    """40 s of recording, so a 20 s window is not the one the adaptation picks
    and a change to it is visible."""
    default = study(tmp_path / "default")
    run(default, step)
    before = entry(default, step, container, name)["window"]

    tuned = study(tmp_path / "tuned", tuning={key: {"window": 6.0, "step": 2.0}})
    run(tuned, step)
    after = entry(tuned, step, container, name)["window"]

    assert after["length_requested_sec"] == 6.0, (
        f"the config asked for a 6 s window and the payload reports "
        f"{after['length_requested_sec']}; the setting is not read")
    assert after["step_requested_sec"] == 2.0
    assert after["length_used_sec"] != before["length_used_sec"], (
        "the window the analysis used did not change with the config")


def test_the_target_recurrence_rate_comes_from_config(tmp_path):
    """DET and LAM depend strongly on the rate, so it is the other setting a
    study needs and could not reach."""
    tuned = study(tmp_path / "tuned", tuning={"rqa": {"targetRecurrence": 0.15}})
    run(tuned, "rqa")
    e = entry(tuned, "rqa", "rqa_data", "a")
    assert e["target_recurrence"] == 0.15
    assert abs(e["recurrence_rate"] - 0.15) < 0.01, (
        f"asked for 15% recurrence and got {e['recurrence_rate']:.4f}")


def test_the_provenance_records_the_rate_that_was_used(tmp_path):
    """Asked-for and achieved are both recorded (analysis-output A6), so the
    provenance must say the rate this run used rather than the module default."""
    tuned = study(tmp_path / "tuned", tuning={"rqa": {"targetRecurrence": 0.15}})
    run(tuned, "rqa")
    path = os.path.join(tuned, "assets", "rqa", "v1_rqa_data.json")
    with open(path) as fh:
        assert json.load(fh)["provenance"]["target_recurrence"] == 0.15


def test_an_unset_analysis_block_changes_nothing(tmp_path):
    """The defaults must survive: a study that sets no tuning is the common
    case and must not move because the mechanism exists."""
    plain = study(tmp_path / "plain")
    run(plain, "rqa")
    empty = study(tmp_path / "empty", tuning={"rqa": {}})
    run(empty, "rqa")
    a = entry(plain, "rqa", "rqa_data", "a")
    b = entry(empty, "rqa", "rqa_data", "a")
    assert a["window"] == b["window"]
    assert a["threshold"] == b["threshold"]
