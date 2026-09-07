"""The browser payload and the analysis are two different artifacts.

For a long time they were one file: the JSON the dashboard draws was also the
only surviving analysis. Anyone continuing from a study's output was silently
working at a sixth of the resolution, from a copy reduced by striding — which
does not remove detail, it folds it back onto the frequencies that remain.
"""
import importlib.util
import os

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = importlib.util.spec_from_file_location(
    "cw_res", os.path.join(HERE, "dims_analysis", "steps", "crosswavelet.py"))
cw = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cw)


def test_reduction_averages_rather_than_strides():
    # A ramp: striding keeps every nth sample, averaging keeps the block mean.
    a = np.arange(12, dtype=float)
    out = cw._reduce_time(a, 4)
    assert list(out) == [1.5, 5.5, 9.5], "expected block means, got something else"
    assert list(out) != list(a[::4]), "this is striding, which is the bug"


def test_reduction_does_not_alias_a_fast_oscillation():
    """The concrete harm. A signal alternating +1/-1 averages to ~0, which is
    honest. Striding picks one phase and reports a constant +1, inventing a
    trend that is not in the data."""
    a = np.tile([1.0, -1.0], 64)
    averaged = cw._reduce_time(a, 2)
    strided = a[::2]
    assert np.allclose(averaged, 0.0), "averaging should cancel the oscillation"
    assert np.allclose(strided, 1.0), "striding reports a constant — this is the aliasing"


def test_frequency_reduction_works_on_the_first_axis():
    a = np.arange(24, dtype=float).reshape(6, 4)
    out = cw._reduce_freq(a, 2)
    assert out.shape == (3, 4)
    assert np.allclose(out[0], (a[0] + a[1]) / 2)


def test_reduction_is_a_no_op_when_nothing_to_reduce():
    a = np.arange(5, dtype=float)
    assert np.array_equal(cw._reduce_time(a, 1), a)
    assert np.array_equal(cw._reduce_freq(a, 1), a)


def test_full_resolution_artifact_is_written(tmp_path):
    n_t, n_f = 100, 8
    cwt = {
        "period": np.linspace(0.5, 8, n_f),
        "freqs": np.linspace(2, 0.125, n_f),
        "coherence": np.random.rand(n_f, n_t),
        "power": np.random.rand(n_f, n_t),
        "phase": np.random.rand(n_f, n_t),
        "coi": np.ones(n_t),
        "sig95_wtc": np.full(n_f, 0.59),
    }
    time = np.arange(n_t) * 0.02
    path = cw.save_full_resolution(str(tmp_path), "vid1", "a_vs_b", cwt, time, np.ones(n_t))
    assert os.path.exists(path)

    with np.load(path) as z:
        assert z["a_vs_b/coherence"].shape == (n_f, n_t), "must keep the computed resolution"
        assert np.allclose(z["a_vs_b/sig95_wtc"], 0.59)

    # a second pair joins the same file rather than replacing it
    cw.save_full_resolution(str(tmp_path), "vid1", "c_vs_d", cwt, time, np.ones(n_t))
    with np.load(path) as z:
        assert "a_vs_b/coherence" in z.files and "c_vs_d/coherence" in z.files


def test_phase_is_averaged_as_an_angle():
    """Averaging +179 and -179 degrees numerically gives 0, which is the
    opposite of the truth. The reduction must go through the unit circle."""
    src = open(os.path.join(HERE, "dims_analysis", "steps", "crosswavelet.py")).read()
    assert "np.angle(_reduce_time(_reduce_freq(np.exp(1j" in src, \
        "phase must be reduced via complex exponentials, not averaged directly"
