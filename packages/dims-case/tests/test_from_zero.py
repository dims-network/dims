"""The path a person actually takes: create a study, add data, build it.

Every other test starts somewhere in the middle -- with a project that already
exists, or with time series already on disk. This one starts with nothing, and
it is the path that has broken most often: the scaffold shipped a config with a
fixture study baked into it, `build_assets.py` did not exist in two of the three
studies, and the tutorial's version of these steps produced a blank page.

It is slow by this suite's standards (it runs a real recurrence analysis on a
few hundred points) and worth it: it is the acceptance check for "a new study
can rebuild itself from zero", which no unit test can stand in for.
"""
import json
import os
import subprocess
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
DIMS_CASE = os.path.join(ROOT, "tools", "dims-case")


def have_analysis():
    import importlib.util
    try:
        return importlib.util.find_spec("dims_analysis.cli") is not None
    except ModuleNotFoundError:
        return False


def write_series(path, seed, n=400, dt=0.02):
    rng = np.random.default_rng(seed)
    t = np.arange(n) * dt
    v = np.sin(2 * np.pi * 0.7 * t) + 0.2 * rng.standard_normal(n)
    with open(path, "w") as fh:
        fh.write("Time,value\n")
        for ti, vi in zip(t, v):
            fh.write(f"{ti:.4f},{vi:.6f}\n")


@pytest.mark.skipif(not have_analysis(),
                    reason="dims-analysis is not installed in this interpreter")
def test_a_new_study_builds_its_own_assets(tmp_path):
    study = str(tmp_path / "case-probe")

    # 1. Create it. Not by copying the scaffold directory: that ships no
    #    vendor/, which is what the tutorial used to tell people to do.
    r = subprocess.run([sys.executable, DIMS_CASE, "new", "probe",
                        "--visibility", "public", "--dir", study],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    for expected in ("index.html", "serve.py", "config.json", "build_assets.py",
                     "requirements.txt", "vendor/dims-core", "vendor/dims-tabs"):
        assert os.path.exists(os.path.join(study, expected)), f"no {expected}"

    # 2. A study with no recordings in it yet must say so rather than
    #    reporting a successful build of nothing.
    r = subprocess.run([sys.executable, "build_assets.py", "--check"],
                       cwd=study, capture_output=True, text=True)
    assert r.returncode != 0
    assert "no videoIDs" in r.stdout + r.stderr

    # 3. Add data and say what it is.
    ts = os.path.join(study, "assets", "timeseries")
    os.makedirs(ts, exist_ok=True)
    write_series(os.path.join(ts, "s01_bodysync.csv"), seed=1)
    write_series(os.path.join(ts, "s01_neuralsync.csv"), seed=2)

    config_path = os.path.join(study, "config.json")
    config = json.load(open(config_path))
    config.update({
        "title": "Probe",
        "videoIDs": ["s01"],
        "dataTypes": {"s01": ["bodysync", "neuralsync"]},
        "include_RQA": ["bodysync"],
        "include_cRQA": [["bodysync", "neuralsync"]],
        "include_crosswavelet": [],
    })
    json.dump(config, open(config_path, "w"), indent=2)

    # 4. --check reports without computing or installing anything.
    r = subprocess.run([sys.executable, "build_assets.py", "--check"],
                       cwd=study, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "include_RQA" in r.stdout and "include_cRQA" in r.stdout
    assert not os.path.exists(os.path.join(study, "assets", "rqa",
                                           "s01_rqa_data.json")), \
        "--check computed something"

    # 5. Build.
    r = subprocess.run([sys.executable, "build_assets.py"],
                       cwd=study, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]

    # 6. One file per analysis, and the JSON must parse. The `.npz` that used
    # to sit beside each of these is gone: for RQA it held the source CSV
    # re-cleaned plus a copy of the JSON's own windowed metrics.
    for rel in ("assets/rqa/s01_rqa_data.json",
                "assets/crqa/s01_crqa_data.json"):
        assert os.path.exists(os.path.join(study, rel)), f"no {rel}"
    stray = [p for p in os.listdir(os.path.join(study, "assets/rqa"))
             if p.endswith(".npz")]
    assert not stray, f"a second file format came back: {stray}"
    payload = json.load(open(os.path.join(study, "assets/rqa/s01_rqa_data.json")))
    assert payload["video_id"] == "s01"
    assert "bodysync" in payload["rqa_data"]
    assert payload["rqa_data"]["bodysync"]["visualization"]["reduction"]["factor"] >= 1

    # 7. The manifest closes the loop: record, then verify.
    r = subprocess.run([sys.executable, "build_assets.py", "--write-manifest"],
                       cwd=study, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    r = subprocess.run([sys.executable, "build_assets.py", "--check"],
                       cwd=study, capture_output=True, text=True)
    assert "assets match" in r.stdout

    # 8. And a deleted asset is reported, rather than a rebuild claiming success.
    os.remove(os.path.join(study, "assets/crqa/s01_crqa_data.json"))
    r = subprocess.run([sys.executable, "build_assets.py", "--check"],
                       cwd=study, capture_output=True, text=True)
    assert "1 missing" in r.stdout, r.stdout
