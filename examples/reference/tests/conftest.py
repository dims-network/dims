"""Shared setup for the reference-study tests.

Every other test here asks "did it crash?" or checks a helper in isolation. On
real data that is all that is available -- `DET = 0.2571` is a number nobody can
verify. These signals are constructed so the right answer is arithmetic: a sine
at a 2 s period recurs every 2 s, a copy delayed 0.4 s puts its cross-recurrence
line 0.4 s off the diagonal, and two independent red noises exceed a 95 % level
in 5 % of cells by construction.

Each test names the defect it would have caught. Nine were found in one session
by accident; these are what finding them on purpose looks like.

The study is generated, not committed: `examples/reference/make_reference_study.py`.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import numpy as np
import pytest

REFERENCE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERATOR = os.path.join(REFERENCE, "make_reference_study.py")

# Straight from the generator, and deliberately restated rather than imported:
# a test that reads its expectations from the code under test proves nothing.
DT = 0.02
PERIOD_S = 2.0
LAG_S = 0.4
PERIOD_SAMPLES = 100
LAG_SAMPLES = 20
TARGET_RATE = 0.07


def build(tmp_path_factory, steps: str):
    """Generate the study into a temp dir and run `steps` over it."""
    work = tmp_path_factory.mktemp("reference")
    study = str(work / "reference")
    shutil.copytree(REFERENCE, study, ignore=shutil.ignore_patterns("assets", "__pycache__"))
    subprocess.run([sys.executable, os.path.join(study, "make_reference_study.py")],
                   check=True, capture_output=True)
    run = subprocess.run(
        [sys.executable, "-m", "dims_analysis.cli", "run",
         "--config", "config.json", "--steps", steps],
        cwd=study, capture_output=True, text=True)
    if run.returncode != 0:
        pytest.fail(f"the analyses failed:\n{run.stdout[-4000:]}\n{run.stderr[-4000:]}")
    return study, run.stdout


@pytest.fixture(scope="session")
def recurrence(tmp_path_factory):
    """RQA and cross-RQA. Seconds, so these tests stay usable."""
    study, out = build(tmp_path_factory, "rqa,crqa")
    return study, out


def entry(study, analysis, container, name):
    path = os.path.join(study, "assets", analysis, f"reference_{analysis}_data.json")
    with open(path) as fh:
        payload = json.load(fh)
    assert container in payload, f"{path} has no {container}"
    assert name in payload[container], (
        f"{path} has no entry for {name}; it has {sorted(payload[container])}")
    return payload[container][name]


def dense(vis):
    """The drawn matrix, however the payload happens to encode it."""
    n = vis["matrix_size"]
    m = np.zeros((n, n), dtype=np.uint8)
    for r, c in vis["sparse_matrix"]:
        if r < n and c < n:
            m[r, c] = 1
    return m


def diagonal_offsets(m, min_fraction=0.25):
    """Offsets k whose diagonal is recurrent for at least `min_fraction` of it.

    A recurrence line is a diagonal that is mostly filled. Reading the offsets
    back out is how the known lag and the known period become checkable.
    """
    n = min(m.shape)
    found = []
    for k in range(-(n - 1), n):
        d = np.diagonal(m, offset=k)
        if d.size >= 0.5 * n and d.mean() >= min_fraction:
            found.append(k)
    return found




# --- cross-wavelet -----------------------------------------------------------

@pytest.fixture(scope="session")
def coherence_study(tmp_path_factory):
    """Cross-wavelet. ~40 s at the reference study's mcCount of 20."""
    study, out = build(tmp_path_factory, "crosswavelet")
    return study, out


def pair(study, name):
    path = os.path.join(study, "assets", "crosswavelet",
                        "reference_crosswavelet_data.json")
    with open(path) as fh:
        payload = json.load(fh)
    assert name in payload["crosswavelet_pairs"], (
        f"no pair {name}; found {sorted(payload['crosswavelet_pairs'])}")
    return payload["crosswavelet_pairs"][name]["visualization"]


def as_array(field):
    return np.array([[np.nan if c is None else c for c in row] for row in field],
                    dtype=float)


