"""Exit-code semantics for `dims-analysis run`.

cli.py had no tests, which is unfortunate for a module whose docstring is about
failing loudly. The failure it was written to prevent -- "a crashed analysis
scrolled past in the log and the build reported success" -- was still reachable
by the commonest route: every step catches its own unreadable-input case, prints
a warning and returns, so nothing raises and the run exited 0 having written
nothing at all.
"""
import json
import os
import subprocess
import sys

import numpy as np
import pytest

from dims_analysis import cli
from dims_analysis.base import Step


# --- helpers ---------------------------------------------------------------

def _series(path, n=300, dt=0.02, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n) * dt
    v = np.sin(2 * np.pi * 0.7 * t) + 0.2 * rng.standard_normal(n)
    path.write_text("Time,value\n" + "".join(f"{a:.6f},{b:.6f}\n" for a, b in zip(t, v)))


def _project(tmp_path, with_data):
    p = tmp_path / "study"
    (p / "assets" / "timeseries").mkdir(parents=True)
    if with_data:
        for i, name in enumerate(("alpha", "beta")):
            _series(p / "assets" / "timeseries" / f"v1_{name}.csv", seed=i)
    (p / "config.json").write_text(json.dumps({
        "videoIDs": ["v1"],
        "dataTypes": {"v1": ["alpha", "beta"]},
        "include_RQA": ["alpha"],
    }))
    return p


def _run_cli(project, *extra):
    return subprocess.run(
        [sys.executable, "-m", "dims_analysis.cli", "run", "--config", "config.json", *extra],
        cwd=str(project), capture_output=True, text=True,
    )


class _FakeStep(Step):
    id = "fake"
    config_key = "include_RQA"
    output_dir = "assets/fake"
    output_name = "{video_id}_fake.json"

    def __init__(self, behaviour="write"):
        self.behaviour = behaviour

    def run(self, config, ctx):
        if self.behaviour == "raise":
            raise RuntimeError("deliberate")
        if self.behaviour == "silent":
            return                      # the real failure mode: warn and return
        ctx.write_result(self, "v1", {"ok": True})


@pytest.fixture
def only_fake(monkeypatch):
    """Replace discovery so the exit-code logic is tested, not the analyses."""
    def install(behaviour="write", problems=()):
        def fake_discover(problem_list=None):
            if problem_list is not None:
                problem_list.extend(problems)
            return {"fake": _FakeStep(behaviour)}
        monkeypatch.setattr(cli, "discover", fake_discover)
    return install


# --- the failure this module exists to prevent -----------------------------

def test_a_step_that_writes_nothing_is_a_failure(tmp_path, only_fake, capsys):
    only_fake("silent")
    project = _project(tmp_path, with_data=False)
    code = cli.main(["run", "--config", str(project / "config.json")])
    out = capsys.readouterr()
    assert code == 1, "a run that produced no output reported success"
    assert "wrote no output" in out.err
    assert "fake" in out.err


def test_a_real_step_with_no_input_fails_the_run(tmp_path):
    """End to end, through the console entry point, with the shipped rqa."""
    project = _project(tmp_path, with_data=False)
    proc = _run_cli(project, "--keep-going")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "PRODUCED NOTHING" in proc.stderr
    assert not list((project / "assets" / "rqa").glob("*.json")) \
        if (project / "assets" / "rqa").exists() else True


def test_a_real_step_with_input_succeeds(tmp_path):
    project = _project(tmp_path, with_data=True)
    proc = _run_cli(project)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert list((project / "assets" / "rqa").glob("*.json"))


# --- the other exit codes ---------------------------------------------------

def test_a_step_that_raises_is_a_failure(tmp_path, only_fake, capsys):
    only_fake("raise")
    project = _project(tmp_path, with_data=True)
    assert cli.main(["run", "--config", str(project / "config.json")]) == 1
    assert "deliberate" in capsys.readouterr().err


def test_a_step_that_writes_is_a_success(tmp_path, only_fake):
    only_fake("write")
    project = _project(tmp_path, with_data=True)
    assert cli.main(["run", "--config", str(project / "config.json")]) == 0
    assert (project / "assets" / "fake" / "v1_fake.json").exists()


def test_a_step_the_config_does_not_enable_is_skipped_not_failed(tmp_path, only_fake):
    only_fake("silent")
    project = _project(tmp_path, with_data=True)
    cfg = json.loads((project / "config.json").read_text())
    del cfg["include_RQA"]
    (project / "config.json").write_text(json.dumps(cfg))
    assert cli.main(["run", "--config", str(project / "config.json")]) == 0


def test_an_unknown_step_id_is_a_usage_error(tmp_path):
    project = _project(tmp_path, with_data=True)
    proc = _run_cli(project, "--steps", "nosuchstep")
    assert proc.returncode == 2
    assert "unknown step" in proc.stderr


def test_a_missing_config_is_a_usage_error(tmp_path):
    assert cli.main(["run", "--config", str(tmp_path / "nope.json")]) == 2


def test_a_step_that_cannot_be_imported_fails_if_it_was_wanted(tmp_path, only_fake, capsys):
    """A missing pycwt meant the only requested analysis never ran, exit 0."""
    only_fake("write", problems=[("crosswavelet", ImportError("No module named 'pycwt'"))])
    project = _project(tmp_path, with_data=True)
    code = cli.main(["run", "--config", str(project / "config.json"),
                     "--steps", "crosswavelet"])
    assert code == 1
    assert "could not be loaded" in capsys.readouterr().err


def test_an_unimportable_step_nobody_asked_for_does_not_fail_the_run(tmp_path, only_fake):
    only_fake("write", problems=[("thirdparty", ImportError("boom"))])
    project = _project(tmp_path, with_data=True)
    assert cli.main(["run", "--config", str(project / "config.json"),
                     "--steps", "fake"]) == 0
