"""The reduced picture and the analysis are two resolutions of one schema.

For a long time they were one file: the JSON the dashboard draws was also the
only surviving analysis. Anyone continuing from a study's output was silently
working at a sixth of the resolution, from a copy reduced by striding — which
does not remove detail, it folds it back onto the frequencies that remain.

Then they were two *formats* — a JSON and an `.npz` — and for RQA the second
held nothing the first did not. Now there is one format: cross-wavelet writes
`{video}_crosswavelet_full.json` with the same field names and the same schema
as the payload, differing only in the time axis, and the recurrence analyses
carry their full-resolution signal in the single file.
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


def _cwt(n_f=8, n_t=100, fill=0.5):
    """Every key `downsample_for_storage` reads. Discovered from the function,
    not guessed: a partial dict raises a KeyError that looks like a test bug."""
    return {
        "period": np.linspace(0.5, 8, n_f),
        "freqs": np.linspace(2, 0.125, n_f),
        "scales": np.linspace(0.5, 8, n_f),
        "coherence": np.full((n_f, n_t), fill),
        "power": np.random.rand(n_f, n_t),
        "phase": np.random.rand(n_f, n_t),
        "coi": np.ones(n_t),
        "sig95_wtc": np.full(n_f, 0.59),
        "signif_xwt": np.ones(n_f),
        "global_power": np.ones(n_f),
        "global_signif": np.ones(n_f),
    }


def test_the_full_resolution_block_is_the_same_schema_as_the_drawn_one():
    """One reader must serve both files. If the full-resolution block gained or
    lost a field, a notebook written against the payload would break on the very
    file it is supposed to prefer -- which is what a second *format* did.
    """
    n_f, n_t = 8, 100
    results, time, avg = _cwt(n_f, n_t), np.arange(100) * 0.02, np.ones(100)

    drawn = cw.downsample_for_storage(results, time, avg,
                                      max_time_points=20, max_freq_points=4)
    full = cw.downsample_for_storage(results, time, avg,
                                     max_time_points=n_t, max_freq_points=n_f)

    assert set(drawn) == set(full), (
        f"the two resolutions disagree about their fields: "
        f"{set(drawn) ^ set(full)}")
    assert len(full["time"]) == n_t and len(full["period"]) == n_f, (
        "the full-resolution block must keep the resolution it was computed at")
    assert len(drawn["time"]) <= 20 < len(full["time"])


def test_the_large_grids_are_encoded_and_the_axes_stay_readable():
    """A period axis is a few hundred numbers somebody opens the file to read;
    a coherence grid is 128 x 3026 and is not."""
    from dims_analysis.common import arrays

    results = _cwt()
    block = cw.downsample_for_storage(results, np.arange(100) * 0.02,
                                      np.ones(100))
    for field in ("coherence", "power", "phase"):
        assert arrays.is_packed(block[field]), f"{field} is not encoded"
        assert arrays.unpack(block[field]).shape == (len(block["period"]),
                                                     len(block["time"]))
    for field in ("time", "period", "coi", "signif_xwt"):
        assert isinstance(block[field], list), f"{field} should stay readable"


def test_a_derived_grid_is_not_stored():
    """`sig95_xwt` was power divided by the per-scale level, broadcast across
    time -- a third full grid holding the quotient of two fields already in the
    file, and a quarter of the full-resolution output. A reader divides."""
    block = cw.downsample_for_storage(_cwt(), np.arange(100) * 0.02, np.ones(100))
    assert "sig95_xwt" not in block
    assert "signif_xwt" in block, "the level itself must still be there to divide by"


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

    This used to assert on the *text* of the step: that it contained
    `np.clip(WCO, 0.0, 1.0)` and the word "undefined". That passes for any file
    mentioning those strings and fails for any refactor that keeps the
    behaviour — which is what happened when the formula moved into
    `common/coherence.py`. It now runs the thing.
    """
    import numpy as np
    from dims_analysis.common import coherence as coh

    silent = np.zeros((1, 4))
    S12 = np.zeros((1, 4), dtype=complex)
    wco, undefined = coh.coherence_from_spectra(silent, silent, S12)

    assert undefined.all(), "cells with no power must be undefined"
    assert np.isnan(wco).all(), "and must not carry a value, least of all 1.0"


def test_json_carries_no_bare_nan():
    """json.dump writes a bare NaN token, which JSON.parse rejects outright, so
    one undefined cell would make a study's output unreadable in a browser.

    Asserted on the output rather than on the source, which is what it used to
    grep: the encoded grids carry NaN as float32 bits and never meet the JSON
    writer, and the readable axes go through `nan_to_none`. Only the result can
    say whether both routes are covered."""
    import json

    results = _cwt()
    results["coherence"][0, 0] = np.nan
    results["signif_xwt"][1] = np.nan
    results["coi"][2] = np.nan
    block = cw.downsample_for_storage(results, np.arange(100) * 0.02, np.ones(100))
    text = json.dumps(block)
    assert "NaN" not in text and "Infinity" not in text, (
        "a bare NaN token would make JSON.parse reject the whole payload")
    json.loads(text)


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


def test_the_payload_resolution_is_a_study_setting_not_a_constant():
    """Two module constants decided how large every study's payload was.

    The step contract's rule is that tuning which can only be changed by
    editing the source is how a fork ends up maintaining its own copy of an
    analysis — and `MAX_TIME_POINTS_VIZ` / `MAX_FREQ_POINTS_VIZ` were exactly
    that. The right size depends on the recording: a two-minute lesson and a
    thirty-second game do not want the same picture.
    """
    import numpy as np
    from dims_analysis.steps import crosswavelet as cw

    n_time, n_freq = 400, 80
    # Every key the function reads. Discovered from the function, not guessed:
    # a partial dict raises a KeyError that looks like a test bug and is one.
    results = {
        "freqs": np.linspace(0.1, 5, n_freq),
        "period": np.linspace(0.2, 10, n_freq),
        "scales": np.linspace(0.1, 5, n_freq),
        "power": np.ones((n_freq, n_time)),
        "phase": np.zeros((n_freq, n_time)),
        "coherence": np.full((n_freq, n_time), 0.5),
        "signif_xwt": np.ones(n_freq),
        "global_power": np.ones(n_freq),
        "global_signif": np.ones(n_freq),
        "coi": np.ones(n_time),
    }
    time = np.arange(n_time) * 0.05
    avg = np.ones(n_time)

    small = cw.downsample_for_storage(results, time, avg,
                                      max_time_points=40, max_freq_points=10)
    big = cw.downsample_for_storage(results, time, avg,
                                    max_time_points=400, max_freq_points=80)

    assert len(small["time"]) <= 40 < len(big["time"])
    assert len(small["period"]) <= 10 < len(big["period"])
    # And the picture stays rectangular: a coherence row per period, a column
    # per time point. A tab draws it as a grid and says nothing if it is not.
    from dims_analysis.common import arrays
    grid = arrays.unpack(small["coherence"])
    assert grid.shape == (len(small["period"]), len(small["time"]))


def test_the_study_tuning_block_is_where_those_numbers_come_from():
    """The plumbing, separately from the sizing: a study sets these in config."""
    from dims_analysis.steps import crosswavelet as cw

    tune = cw._tuning({"analysis": {"crosswavelet": {"maxTimePoints": 60,
                                                     "maxFreqPoints": 24}}})
    assert tune["maxTimePoints"] == 60 and tune["maxFreqPoints"] == 24
    assert cw._tuning({}) == {}, "no analysis block must mean the defaults"
