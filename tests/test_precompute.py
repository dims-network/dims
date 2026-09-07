"""The builder had no tests at all. These cover the part that decides what runs.

The wizard is the only route in for a researcher who does not write code, so a
silent wrong answer here is the most expensive kind in this project.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.precompute import discover_steps, _enabled, run_precompute  # noqa: E402


def make_project(tmp_path, scripts=("step_RQA.py", "step_cRQA.py", "step_crosswavelet.py")):
    opt = tmp_path / "opt"
    opt.mkdir()
    for s in scripts:
        (opt / s).write_text("import sys; sys.exit(0)\n")
    return str(tmp_path)


def test_steps_come_from_the_project_not_from_this_file(tmp_path):
    """Adding an analysis to the template must not require editing the builder."""
    proj = make_project(tmp_path, ("step_RQA.py", "step_network.py"))
    ids = {s[0] for s in discover_steps(proj)}
    assert ids == {"rqa", "network"}, f"got {ids}"


def test_a_step_declares_its_own_output_and_gate(tmp_path):
    proj = make_project(tmp_path, ("step_crosswavelet.py",))
    step_id, script, out_dir, key = discover_steps(proj)[0]
    assert (step_id, script, out_dir, key) == (
        "crosswavelet", os.path.join("opt", "step_crosswavelet.py"),
        os.path.join("assets", "crosswavelet"), "include_crosswavelet")


def test_a_project_with_no_opt_directory_is_not_an_error(tmp_path):
    assert discover_steps(str(tmp_path)) == []


@pytest.mark.parametrize("cfg,key,expected", [
    ({"include_RQA": ["a"]}, "include_RQA", True),
    ({"include_rqa": ["a"]}, "include_RQA", True),       # case-insensitive, deliberately
    ({"include_cRQA": [["a", "b"]]}, "include_cRQA", True),
    ({"include_RQA": []}, "include_RQA", False),          # empty means off
    ({}, "include_RQA", False),
])
def test_config_gates_are_matched_case_insensitively(cfg, key, expected):
    # The historical keys are include_RQA and include_cRQA, which no naming
    # rule would have predicted from step_RQA.py / step_cRQA.py.
    assert _enabled(cfg, key) is expected


def test_nothing_enabled_is_reported_clearly(tmp_path, monkeypatch):
    proj = make_project(tmp_path)
    monkeypatch.setattr("app.precompute.create_venv", lambda p: iter(["venv ok\n"]))
    out = "".join(run_precompute(proj, config={}))
    assert "No analyses are enabled" in out
    assert "Precompute complete" in out


def test_a_failing_step_stops_the_run_and_says_so(tmp_path, monkeypatch):
    """Continuing past a failure produced output that was partly missing and
    looked complete."""
    proj = make_project(tmp_path)
    monkeypatch.setattr("app.precompute.create_venv", lambda p: iter(["venv ok\n"]))

    def fake_step(project, step_id, script, out_dir, extra=None):
        yield f"running {step_id}\n"
        yield "__EXIT__:1\n" if step_id == "rqa" else "__EXIT__:0\n"

    monkeypatch.setattr("app.precompute._run_step", fake_step)
    out = "".join(run_precompute(proj, config={
        "include_RQA": ["a"], "include_crosswavelet": [["a", "b"]]}))

    assert "__FAILED__:rqa" in out
    assert "Precompute FAILED" in out
    assert "running crosswavelet" not in out, "it should have stopped after the failure"


def test_a_clean_run_reports_success(tmp_path, monkeypatch):
    proj = make_project(tmp_path)
    monkeypatch.setattr("app.precompute.create_venv", lambda p: iter(["venv ok\n"]))
    monkeypatch.setattr("app.precompute._run_step",
                        lambda *a, **k: iter([f"ok\n", "__EXIT__:0\n"]))
    out = "".join(run_precompute(proj, config={"include_RQA": ["a"]}))
    assert "Precompute complete" in out and "FAILED" not in out


def test_the_old_boolean_signature_still_works(tmp_path, monkeypatch):
    """An older caller must not break just because the interface improved."""
    proj = make_project(tmp_path)
    monkeypatch.setattr("app.precompute.create_venv", lambda p: iter(["venv ok\n"]))
    monkeypatch.setattr("app.precompute._run_step",
                        lambda *a, **k: iter(["ok\n", "__EXIT__:0\n"]))
    out = "".join(run_precompute(proj, do_rqa=True, do_crosswavelet=False, do_crqa=False))
    assert "Running rqa" in out and "Running crosswavelet" not in out
