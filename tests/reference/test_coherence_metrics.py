"""Cross-wavelet and coherence, comprehensively, on signals with known answers.

The historic defect in this project was a coherence that measured signal power
rather than coupling. Its signature was measurable and is recorded here: 57 % of
cells pinned at exactly 1.0, a correlation of +0.87 against log power, and a
mean of 0.645 where unrelated signals should sit near 0.3. Every one of those
is now an assertion, so the same defect cannot return quietly.

The other half is the positive control: a signal against *itself* must be
perfectly coherent. Without it, "no cells at 1.0" could be satisfied by a
measure that never reaches 1 at all.
"""
from __future__ import annotations

import numpy as np
import pytest

from conftest import as_array, pair

#: Pairs that are genuinely different signals. Perfect coherence here would be
#: the defect; the historic one produced 57 % of cells at exactly 1.0.
DISTINCT = ["noise_a_vs_noise_b", "eff_hand_l_vs_eff_other",
            "eff_hand_r_vs_eff_other"]

#: A signal against itself, and against a scaled copy of itself. Coherence is
#: amplitude-normalised, so these two must be indistinguishable.
IDENTICAL = ["sine_vs_sine", "sine_vs_sine_x10"]

PERIOD_S = 2.0


def finite(values):
    return values[np.isfinite(values)]


# --- the positive control ----------------------------------------------------

@pytest.mark.parametrize("key", IDENTICAL)
def test_a_signal_is_perfectly_coherent_with_itself(coherence_study, key):
    """The strongest invariant the measure has, and the control that stops the
    tests below being satisfiable by a coherence that never reaches 1."""
    study, _ = coherence_study
    coherence = as_array(pair(study, key)["coherence"])
    assert abs(np.nanmean(coherence) - 1.0) < 1e-3, (
        f"{key} gave mean coherence {np.nanmean(coherence):.6f}")


def test_scaling_a_signal_changes_nothing(coherence_study):
    """Coherence is amplitude-normalised by construction. `sine_x10` is the
    same signal ten times larger, so every cell must be identical -- a
    normalisation that went missing shows up here and nowhere else."""
    study, _ = coherence_study
    plain = as_array(pair(study, "sine_vs_sine")["coherence"])
    scaled = as_array(pair(study, "sine_vs_sine_x10")["coherence"])
    assert plain.shape == scaled.shape
    assert np.allclose(plain, scaled, atol=1e-9, equal_nan=True), (
        f"largest difference {np.nanmax(np.abs(plain - scaled)):.3g}")


# --- the signature of the defect this project was rebuilt around ------------

@pytest.mark.parametrize("key", DISTINCT)
def test_distinct_signals_never_pin_at_one(coherence_study, key):
    """The old smoothing destroyed phase before it could cancel and left the
    ratio unnormalised behind a clamp, so 57 % of cells sat at exactly 1.0.
    Measured now: 0 %."""
    study, _ = coherence_study
    coherence = finite(as_array(pair(study, key)["coherence"]))
    pinned = float(np.mean(coherence >= 1.0))
    assert pinned < 0.01, f"{key}: {pinned:.1%} of cells sit at exactly 1.0"


@pytest.mark.parametrize("key", DISTINCT)
def test_coherence_does_not_track_signal_power(coherence_study, key):
    """The defect's other symptom, and the one that named it: coherence
    correlated +0.87 with log power, because it was measuring how much the
    signals moved rather than whether they moved together. Measured now:
    0.03 to 0.17."""
    study, _ = coherence_study
    vis = pair(study, key)
    coherence = as_array(vis["coherence"])
    power = as_array(vis["power"])
    usable = np.isfinite(coherence) & np.isfinite(power) & (power > 0)
    assert usable.sum() > 100
    r = float(np.corrcoef(coherence[usable], np.log(power[usable]))[0, 1])
    assert abs(r) < 0.5, (
        f"{key}: coherence correlates {r:+.3f} with log power; the defect this "
        f"replaced measured +0.87")


def test_unrelated_signals_sit_near_the_chance_level_not_near_one(coherence_study):
    """Independent red noise averages around 0.3, not 0.645 -- which is what
    the defect produced, and why every edge in a network came out thick."""
    study, _ = coherence_study
    coherence = finite(as_array(pair(study, "noise_a_vs_noise_b")["coherence"]))
    mean = float(np.mean(coherence))
    assert 0.15 < mean < 0.5, f"independent signals averaged {mean:.4f}"


# --- the scale axis, which is where a unit error would hide -----------------

@pytest.mark.parametrize("key", ["sine_vs_sine", "sine_vs_sine_lagged"])
def test_power_peaks_at_the_period_the_signal_actually_has(coherence_study, key):
    """A units test for the wavelet scales.

    The signal is a 2 s sine, so the time-averaged cross-wavelet power must
    peak at 2 s. It peaks at 1.926 s -- the nearest scale on a dj = 1/12 grid,
    3.7 % away. Any larger discrepancy is a scale-to-period conversion that has
    drifted, and nothing else in the output would look wrong.
    """
    study, _ = coherence_study
    vis = pair(study, key)
    power = as_array(vis["power"])
    period = np.asarray(vis["period"], dtype=float)
    peak = float(period[int(np.nanargmax(np.nanmean(power, axis=1)))])
    assert abs(peak - PERIOD_S) / PERIOD_S < 0.10, (
        f"{key}: power peaks at {peak:.3f} s for a {PERIOD_S} s signal")


def test_the_period_axis_spans_what_the_wavelet_parameters_imply(coherence_study):
    """s0 = 2*dt = 0.04 s sets the shortest scale; the record length sets the
    longest. A period axis that started somewhere else would silently relabel
    every row of every heatmap."""
    study, _ = coherence_study
    period = np.asarray(pair(study, "sine_vs_sine")["period"], dtype=float)
    assert 0.02 < period[0] < 0.2, f"shortest period {period[0]:.4f} s"
    assert period[-1] < 20.48, f"longest period {period[-1]:.3f} s exceeds the record"
    assert np.all(np.diff(period) > 0)


# --- the cone, and the fields that describe it ------------------------------

def test_the_cone_of_influence_is_widest_at_the_edges(coherence_study):
    """The wavelet window runs past the data at the start and end, so the cone
    admits only short periods there and opens out in the middle. A flat cone
    would mean the edge correction is not being applied at all."""
    study, _ = coherence_study
    coi = np.asarray(pair(study, "sine_vs_sine")["coi"], dtype=float)
    edge = min(coi[0], coi[-1])
    middle = float(np.max(coi))
    assert middle > 5 * edge, (
        f"the cone is {edge:.3f} s at the edges and {middle:.3f} s in the "
        f"middle; it should open out far more than that")


def test_the_power_significance_is_a_separate_field_from_the_coherence_null(
        coherence_study):
    """`signif_xwt` tests joint *power* against red noise; `sig95_wtc` tests
    coherence against unrelated signals. They answer different questions, and
    the built-in tab has used the first where it needed the second.

    Both are one level per period now, so the shapes no longer separate them --
    the power level used to be stored a second time as a full grid, `power`
    divided by it and broadcast across time, which held nothing the two fields
    beside it did not. What keeps them apart is what they are measured against,
    so that is what this checks: the power level is a level on the same scale
    as `power`, and the coherence null is a number between 0 and 1.
    """
    study, _ = coherence_study
    vis = pair(study, "sine_vs_sine_lagged")

    level = np.asarray(vis["signif_xwt"], dtype=float)
    null = np.asarray([np.nan if x is None else x for x in vis["sig95_wtc"]],
                      dtype=float)
    period = np.asarray(vis["period"], dtype=float)
    assert level.shape == period.shape and null.shape == period.shape

    power = as_array(vis["power"])
    assert power.shape == (len(period), len(vis["time"]))
    assert np.nanmax(level) > 1.5, (
        "a power level lives on the scale of power, not of coherence; "
        f"this one tops out at {np.nanmax(level):.3f}")
    finite = null[np.isfinite(null)]
    assert finite.size and np.all((finite > 0) & (finite <= 1)), (
        "a coherence level is a coherence, so it is between 0 and 1")

    # And the ratio a tab thresholds at 1 is still recoverable, which is the
    # whole reason storing it separately was redundant.
    ratio = power / level[:, None]
    assert np.isfinite(ratio).any() and np.nanmax(ratio) > 1.0
