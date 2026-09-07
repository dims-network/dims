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


def test_no_power_means_undefined_coherence_not_perfect_coherence():
    """A real failure, from a real study.

    In a tabletop-game study the velocity signals are exactly zero about half
    the time, because the pieces are not moving. The smoothed denominator then
    collapses toward zero, the ratio explodes — 176 was observed — and clipping
    it to 1.0 painted "perfect coupling" across every stretch where nothing
    happened.

    Those cells have no coherence to report. They must be undefined, and travel
    to the browser as null so it draws a gap.
    """
    src = open(os.path.join(HERE, "dims_analysis", "steps", "crosswavelet.py")).read()

    assert "np.clip(WCO, 0.0, 1.0)" in src
    assert "undefined" in src, "degenerate cells must be marked, not clipped"
    # the give-away of the old behaviour: a bare clip with only an epsilon guard
    assert "np.abs(S12) ** 2 / (S1 * S2 + 1e-30)" not in src, \
        "an epsilon is not enough when both signals are genuinely silent"


def test_json_carries_no_bare_nan():
    """json.dump writes a bare NaN token, which JSON.parse rejects outright, so
    one undefined cell would make a study's output unreadable in a browser."""
    src = open(os.path.join(HERE, "dims_analysis", "steps", "crosswavelet.py")).read()
    assert "_json_safe" in src
    for field in ("'coherence': _json_safe", "'power': _json_safe", "'phase': _json_safe"):
        assert field in src, f"{field} must go through the NaN-to-null conversion"


def test_statistics_survive_undefined_cells():
    """One undefined cell must not turn every summary into NaN."""
    src = open(os.path.join(HERE, "dims_analysis", "steps", "crosswavelet.py")).read()
    assert "coi_mask | ~np.isfinite" in src, \
        "undefined cells must be masked out of the statistics too"


# --- payload precision ------------------------------------------------------
# These guard a decision that is easy to undo by accident: someone "fixes" the
# rounding to decimal places, or drops it while touching serialisation, and the
# files quadruple or the quiet cells silently become zero.

def test_significant_figures_not_decimal_places():
    from dims_analysis.common.payload import round_significant

    # The whole reason this is not one call to round(): cross-wavelet power
    # spans eight orders of magnitude.
    assert round_significant(3.21e-08) == 3.21e-08, \
        "a small value must survive; decimal-place rounding would zero it"
    assert round(3.21e-08, 6) == 0.0, "which is what we are avoiding"

    assert round_significant(0.5940133868313864) == 0.594013
    assert round_significant(1234.5678901) == 1234.57


def test_integers_are_left_alone():
    """A sparse recurrence matrix is tens of thousands of [row, col] index
    pairs. Turning those into floats is wrong and larger on disk."""
    from dims_analysis.common.payload import round_significant, round_payload
    assert round_significant(7) == 7 and isinstance(round_significant(7), int)
    assert round_significant(505) == 505
    matrix = [[0, 7], [3, 17]]
    assert round_payload(matrix) == matrix
    assert all(isinstance(v, int) for row in round_payload(matrix) for v in row)


def test_nan_becomes_null_not_a_bare_token():
    from dims_analysis.common.payload import round_payload
    assert round_payload(float("nan")) is None
    assert round_payload(float("inf")) is None


def test_every_step_rounds_its_payload_and_says_so():
    """The guard against this quietly disappearing: each step must round on the
    way out and record the precision in the file."""
    import os
    steps = os.path.join(HERE, "dims_analysis", "steps")
    for name in ("crosswavelet.py", "rqa.py", "crqa.py"):
        src = open(os.path.join(steps, name)).read()
        assert "round_payload(" in src, f"{name} writes an unrounded payload"
        assert "precision_note()" in src, f"{name} does not record its precision"
        # code lines only: a comment explaining why indent=2 was removed is not
        # a violation, and matching it would be the same false positive twice.
        code = [l for l in src.splitlines() if not l.lstrip().startswith("#")]
        assert not any("indent=2" in l for l in code), \
            f"{name} still writes indentation nobody reads"
