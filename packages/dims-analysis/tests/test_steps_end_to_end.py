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
        # Asked for explicitly. The coherence null is no longer computed
        # unconditionally -- its default follows whether the study has a tab
        # that reads it -- and these tests are about what gets *written* when
        # it is computed, not about the default. The default has its own test
        # below. A small count keeps the fixture fast.
        "analysis": {"crosswavelet": {"mcCount": 8}},
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


@pytest.mark.parametrize("step", STEPS)
def test_no_step_writes_a_second_file_format(tmp_path, step):
    """One format. The `.npz` beside each payload is gone, and it is worth
    saying why rather than only that it is: measured file by file, the RQA
    archive held `time` and `signal` -- byte-identical to the source CSV after
    the documented cleaning -- plus windowed metrics that were exact duplicates
    of the JSON's. The contract meanwhile told readers "Analyse from the .npz",
    pointing them at the file holding *less*.
    """
    project, assets = _study(tmp_path, external=False)
    proc = _run(step, project)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    stray = sorted((assets / step).glob("*.npz"))
    assert not stray, f"{step} still writes a second format: {stray}"


@pytest.mark.parametrize("step", ["rqa", "crqa"])
def test_a_recurrence_payload_carries_its_own_full_resolution_signal(tmp_path, step):
    """One file, and complete. Everything in a recurrence result except the
    matrix is one-dimensional and small, so the full-resolution signal travels
    in the same file as the reduced picture -- and the matrix is one `cdist`
    from that signal and the threshold beside it.
    """
    import json

    from dims_analysis.common import arrays

    project, assets = _study(tmp_path, external=False)
    assert _run(step, project).returncode == 0

    payload = json.loads(next((assets / step).glob("*_data.json")).read_text())
    assert payload["payload_version"] == arrays.PAYLOAD_VERSION
    key = "rqa_data" if step == "rqa" else "crqa_data"
    entry = next(iter(payload[key].values()))
    drawn = len(entry["visualization"]["time"])

    block = entry["full_data"] if step == "rqa" else entry["full_stats"]
    names = ("signal",) if step == "rqa" else ("signal_x", "signal_y")
    full = len(arrays.unpack(block["time"]))
    assert full >= drawn, "the payload holds less at full resolution than it draws"
    assert full == block["n_points"]
    for name in names:
        assert len(arrays.unpack(block[name])) == full, f"{name} is a different length"
    assert entry["threshold"] is not None, (
        "without the threshold the signal cannot be turned back into a matrix")


def test_cross_wavelet_writes_the_one_second_file_that_has_content(tmp_path):
    """Only cross-wavelet has a second resolution worth a second file, and that
    is measured rather than assumed: its large fields are two-dimensional, so a
    full-resolution grid is 128 x 3026 against 128 x 504 drawn. Same schema,
    same field names, different time axis -- so one reader serves both.
    """
    import json

    project, assets = _study(tmp_path, external=False)
    assert _run("crosswavelet", project).returncode == 0

    drawn = json.loads((assets / "crosswavelet" / "v1_crosswavelet_data.json").read_text())
    full = json.loads((assets / "crosswavelet" / "v1_crosswavelet_full.json").read_text())
    assert full["resolution"] == "full"

    name = sorted(drawn["crosswavelet_pairs"])[0]
    a = drawn["crosswavelet_pairs"][name]["visualization"]
    b = full["crosswavelet_pairs"][name]["visualization"]
    assert set(a) == set(b), f"the two resolutions disagree about fields: {set(a) ^ set(b)}"
    assert len(b["time"]) >= len(a["time"])


def test_the_coherence_null_is_skipped_when_nothing_reads_it(tmp_path):
    """The default, and it is the difference between seconds and hours.

    The Monte Carlo coherence null costs ~2.8 h on a twelve-recording study and
    is displayed by exactly one tab in the whole system. So it runs when the
    config enables a tab that reads it, and otherwise does not -- while
    remaining available to any study that asks. See the analysis-output
    contract, A7.
    """
    project, _assets = _study(tmp_path, external=False)
    config = json.loads((project / "config.json").read_text())
    del config["analysis"]                      # no explicit request
    assert "include_network" not in config      # and no consumer
    (project / "config.json").write_text(json.dumps(config, indent=2))

    proc = _run("crosswavelet", project)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "coherence null: skipped" in proc.stdout, (
        f"the run must say it skipped the null and how to ask for it; it said:"
        f"\n{proc.stdout[-2000:]}")

    payload = json.loads(
        (project / "assets" / "crosswavelet" / "v1_crosswavelet_data.json").read_text())
    vis = next(iter(payload["crosswavelet_pairs"].values()))["visualization"]
    assert "sig95_wtc" not in vis or vis["sig95_wtc"] is None, (
        "a null that was not computed must be absent, not a wrong number")
    # Everything else is still there: skipping the null is not skipping the
    # analysis.
    assert vis["coherence"] and vis["power"] and vis["phase"]


def test_a_study_with_a_consumer_computes_the_null_by_default(tmp_path):
    """`include_network` is what reads `sig95_wtc` today."""
    project, _assets = _study(tmp_path, external=False)
    config = json.loads((project / "config.json").read_text())
    del config["analysis"]
    config["include_network"] = True
    (project / "config.json").write_text(json.dumps(config, indent=2))

    proc = _run("crosswavelet", project)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "coherence null: 100 surrogates" in proc.stdout, proc.stdout[-2000:]


def _one_series_study(root, n_points, period):
    """The smallest study that produces an RQA payload, at a chosen shape.

    Length and period, not amplitude: the series is z-scored before the
    distance matrix is built, so a study analysed against another study's data
    at twice the amplitude would report an identical threshold and the test
    would pass while the bug was present.
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / "assets" / "timeseries").mkdir(parents=True)
    t = np.arange(n_points) / 20.0
    values = np.sin(2 * np.pi * t / period)
    with open(root / "assets" / "timeseries" / "v_sig.csv", "w") as fh:
        fh.write("Time,sig\n")
        for a, b in zip(t, values):
            fh.write(f"{a:.6f},{b:.6f}\n")
    config = {"videoIDs": ["v"], "include_RQA": ["sig"],
              "analysis": {"rqa": {"window": 4.0, "step": 0.5}}}
    with open(root / "config.json", "w") as fh:
        json.dump(config, fh)
    return config


def test_two_projects_in_one_process_each_read_their_own_data(tmp_path):
    """The global input directory is gone, and this is what it used to cost.

    `main()` resolved INPUT_DIR into a module global, and `assets.resolve`
    returns an already-absolute path unchanged -- so the second study analysed
    in one process read the first study's time series and wrote them into the
    second study's output, in silence. Nothing shipped that ran two projects in
    one process, which is exactly why it survived: it becomes reachable the
    moment anything drives the runner in a loop.

    Both studies are analysed through Step.run() in this interpreter, and each
    payload has to describe its own data.
    """
    from dims_analysis.base import StepContext
    from dims_analysis.steps.rqa import Step

    seen = {}
    for name, n_points, period in (("a", 400, 2.0), ("b", 700, 3.5)):
        project = tmp_path / name
        config = _one_series_study(project, n_points, period)
        # An absolute output directory, which is what a private study produces
        # and what used to poison the module global for the next study.
        ctx = StepContext(str(project), config,
                          output_dir=str(project / "out"))
        Step().run(config, ctx)
        payload = json.loads((project / "out" / "v_rqa_data.json").read_text())
        entry = payload["rqa_data"]["sig"]
        seen[name] = (entry["full_data"]["n_points"], entry["threshold"])

    # Each study must describe its own series. Before this, the second run
    # resolved its input directory from a module global the first run had
    # already rewritten to an absolute path, and reported 400 points here.
    assert seen["a"][0] == 400
    assert seen["b"][0] == 700
    assert seen["a"][1] != seen["b"][1]


def test_neither_recurrence_step_reassigns_a_module_global():
    """`global` is what made the leak above possible; there is none left.

    Kept as a structural assertion rather than only a behavioural one, because
    the behavioural test can only catch the leak on the paths it happens to
    exercise.
    """
    import ast
    import inspect
    from dims_analysis.steps import rqa, crqa
    for module in (rqa, crqa):
        # Parsed, not grepped: a docstring that says the word "global" at the
        # start of a line is prose, and the first version of this test failed
        # on one of them.
        tree = ast.parse(inspect.getsource(module))
        offending = sorted({name for node in ast.walk(tree)
                            if isinstance(node, ast.Global) for name in node.names})
        assert not offending, f"{module.__name__} reassigns {offending}"
