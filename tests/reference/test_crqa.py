"""Cross-recurrence against a lag we chose ourselves.

`sine_lagged` is `sine` delayed by exactly 0.4 s, so the cross-recurrence line
sits 20 samples off the diagonal. That is the one structure a striding
reduction destroys, and no real study can test it because nobody knows its
true lag.

Shared fixtures and helpers: conftest.py.
"""
import numpy as np

from conftest import (LAG_S, LAG_SAMPLES, TARGET_RATE, dense,
                      diagonal_offsets, entry)


# --- K3: a known lag lands where it should -----------------------------------

def test_K3_cross_recurrence_finds_the_lag_it_was_given(recurrence):
    """The line sits LAG off the diagonal, and that is the whole point.

    Catches: **striding**. Sampling every nth row and column keeps a line on
    the main diagonal and deletes one beside it -- and a lagged coupling is
    precisely a line beside it. This is the test the real studies could never
    have provided, because nobody knows their true lag.
    """
    study, _ = recurrence
    vis = entry(study, "crqa", "crqa_data", "sine_vs_sine_lagged")["visualization"]
    factor = vis["reduction"]["factor"]
    expected = LAG_SAMPLES / factor

    offsets = diagonal_offsets(dense(vis))
    assert offsets, "two identical signals, one delayed, produced no line at all"
    nearest = min(offsets, key=lambda k: abs(abs(k) - expected))
    assert abs(abs(nearest) - expected) <= max(2, 0.2 * expected), (
        f"the dominant line is at offset {nearest} (factor {factor}); a {LAG_S} s "
        f"lag should put it near {expected:.0f}. Offsets found: {offsets[:12]}")


# --- A6: asked-for beside achieved, which this step used not to record --------

def test_each_pair_records_the_rate_asked_for_and_the_rate_reached(recurrence):
    """The mirror of the RQA test, and for a long time it could not be written.

    cRQA never called `rate_report`, so its payload carried
    `global_recurrence_rate` and nothing to read it against: the target survived
    only in `provenance`, and the reference baseline pinned `recurrence_rate`
    and `target_recurrence` as null -- fields the gate was watching that had
    never held a value. Contract A6 says both numbers are recorded wherever an
    analysis aims at something it may not hit, and a percentile threshold on a
    quantised or partly-still signal is exactly that.
    """
    study, _ = recurrence
    for name in ("sine_vs_sine", "sine_vs_sine_lagged", "noise_a_vs_noise_b"):
        e = entry(study, "crqa", "crqa_data", name)
        assert e["target_recurrence"] == TARGET_RATE
        # One number under two names: the tab reads the long one, RQA uses the
        # short one, and they must not be allowed to disagree.
        assert e["recurrence_rate"] == e["global_recurrence_rate"]
        assert abs(e["achieved_recurrence"] - e["recurrence_rate"]) < 1e-9
        missed = abs(e["achieved_recurrence"] - TARGET_RATE) > 0.01
        assert bool(e["recurrence_rate_warning"]) == missed, (
            f"{name}: achieved {e['achieved_recurrence']:.4f} against "
            f"{TARGET_RATE}, warning={e['recurrence_rate_warning']!r}")


# --- the sign of the lag, which nothing checked ------------------------------

def test_the_lag_falls_on_the_side_the_orientation_implies(recurrence):
    """K3 matches the lag by |offset|, so it cannot see the direction.

    Which is the half that says *which measure led*. The matrix is
    `cdist(series 1, series 2)`, so cell (i, j) is recurrent where
    `series1[i] ~ series2[j]`. Here `sine_lagged[j] = sine[j - LAG]`, so
    `i ~ j - LAG`, so the line sits at `k = j - i = +LAG`. Positive, and
    positive is a fact about the orientation the analysis writes.

    The tab reads that orientation and transposes it to match its own axis
    labels (packages/dims-tabs/crqa.js). If the analysis is ever flipped, the
    tab's transpose becomes wrong in the same silent way it was before: the
    picture stays a valid cross-recurrence plot and starts naming the other
    measure as leading. This is what would fail first.
    """
    study, _ = recurrence
    vis = entry(study, "crqa", "crqa_data", "sine_vs_sine_lagged")["visualization"]
    factor = vis["reduction"]["factor"]
    expected = LAG_SAMPLES / factor

    offsets = diagonal_offsets(dense(vis))
    nearest = min(offsets, key=lambda k: abs(abs(k) - expected))
    assert nearest > 0, (
        f"the lag line is at offset {nearest}; cdist(series 1, series 2) with "
        f"series 2 delayed puts it at +{expected:.0f}. A negative offset means "
        f"the matrix is transposed relative to what it was, and every reader of "
        f"a lead/lag from the cross-RQA tab now has it backwards. "
        f"Offsets found: {offsets[:12]}")
