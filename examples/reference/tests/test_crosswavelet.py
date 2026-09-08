"""Cross-wavelet and coherence against a known phase and a known non-relationship.

Two shifted copies of one sine are coherent at their shared period, with a
phase of 2*pi*f*tau -- confirmed independently by scipy.signal.csd. Two
independent AR(1) noises are the other half: what the chance level is for.

Shared fixtures and helpers: conftest.py.
"""
import json
import os

import numpy as np
import pytest

from conftest import LAG_S, PERIOD_S, build


# --- K5: a known lag has a known phase ---------------------------------------

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


def band_mask(period, low=1.6, high=2.5):
    """Scales around the 2 s component the signals actually contain."""
    return (np.asarray(period, dtype=float) > low) & (np.asarray(period) < high)


def test_K5_two_shifted_copies_are_coherent_at_their_shared_period(coherence_study):
    study, _ = coherence_study
    vis = pair(study, "sine_vs_sine_lagged")
    coh = as_array(vis["coherence"])
    band = band_mask(vis["period"])
    assert band.any(), "the 2 s band is not in the analysed range at all"
    assert np.nanmean(coh[band]) > 0.9, (
        f"two shifted copies of one sine gave mean coherence "
        f"{np.nanmean(coh[band]):.4f} at their own period")


def test_K5_the_phase_is_the_lag_that_was_put_in(coherence_study):
    """phase = 2*pi*f*tau = 2*pi*0.5*0.4 = 1.257 rad = 72 degrees.

    Confirmed independently by `scipy.signal.csd`, which gives 72.0 deg on the
    same two signals by a completely different route (Welch, not wavelets).

    Catches: the smoothing defect, which destroyed phase before it could
    cancel; and averaging phase as a scalar rather than through the unit
    circle, which turns +179 and -179 into 0.
    """
    study, _ = coherence_study
    vis = pair(study, "sine_vs_sine_lagged")
    phase = as_array(vis["phase"])
    band = band_mask(vis["period"])

    # Circular mean: the only correct way to average an angle.
    mean_phase = np.angle(np.nanmean(np.exp(1j * phase[band])))
    expected = 2 * np.pi * (1.0 / PERIOD_S) * LAG_S

    assert abs(abs(mean_phase) - expected) < np.radians(8), (
        f"phase is {np.degrees(mean_phase):.1f} deg; a {LAG_S} s lag at a "
        f"{PERIOD_S} s period is {np.degrees(expected):.1f} deg")


def test_K5_the_sign_of_the_phase_says_who_leads(coherence_study):
    """`sine_lagged` is `sine` delayed, so `sine` leads -- and the convention
    here is W1 * conj(W2), which makes that positive.

    This is worth its own test because a flipped sign is invisible in the
    number and inverts every phase arrow on the dashboard: a study would read
    "the student leads the teacher" from data saying the opposite.
    """
    study, _ = coherence_study
    vis = pair(study, "sine_vs_sine_lagged")
    band = band_mask(vis["period"])
    mean_phase = np.angle(np.nanmean(np.exp(1j * as_array(vis["phase"])[band])))
    assert mean_phase > 0, (
        f"phase {np.degrees(mean_phase):.1f} deg: the first signal leads the "
        f"second by {LAG_S} s, so under W1*conj(W2) this must be positive")


# --- K6: the chance level, which is what the expensive simulation buys -------

def stats(study, name):
    path = os.path.join(study, "assets", "crosswavelet",
                        "reference_crosswavelet_data.json")
    with open(path) as fh:
        payload = json.load(fh)
    return payload["crosswavelet_pairs"][name]["statistics"]


def test_K6_unrelated_signals_beat_chance_about_five_percent_of_the_time(coherence_study):
    """The test of the Monte Carlo null itself -- the thing that costs the hours.

    `noise_a` and `noise_b` are independent AR(1) draws, so they *are* the null.
    A 95 % level is calibrated exactly when 5 % of cells exceed it. Measured
    here: 0.0482.

    This also settles what 20 surrogates buys. Increasing to 100 and 300 moved
    the figure by less than 0.001, so the reference study can stay fast without
    the answer being noise.
    """
    study, _ = coherence_study
    fraction = stats(study, "noise_a_vs_noise_b")["wtc_signif_fraction"]
    assert abs(fraction - 0.05) < 0.02, (
        f"two independent AR(1) signals exceeded their own 95 % chance level in "
        f"{fraction:.4f} of cells; a calibrated level gives 0.05")


def test_K6_genuinely_coupled_signals_beat_chance_almost_everywhere(coherence_study):
    """The other half. A level that nothing exceeds is not a level either."""
    study, _ = coherence_study
    fraction = stats(study, "sine_vs_sine_lagged")["wtc_signif_fraction"]
    assert fraction > 0.9, (
        f"two shifted copies of one sine exceeded chance in only {fraction:.4f} "
        f"of cells")


def test_K6_the_fraction_excludes_the_cone_of_influence(coherence_study):
    """Cells inside the cone are contaminated by the edges of the record, and
    including them inflates the answer badly.

    Measured on the same file: 0.048 excluding the cone, **0.126** including
    it -- two and a half times over, from a third of the cells. I made exactly
    this mistake while writing these tests, which is the argument for pinning
    it: "which cells exist" and "which cells mean something" are different
    questions and both end up drawn as hatching.
    """
    study, _ = coherence_study
    vis = pair(study, "noise_a_vs_noise_b")
    coh = as_array(vis["coherence"])
    level = np.array([np.nan if x is None else x for x in vis["sig95_wtc"]], dtype=float)
    period = np.array(vis["period"], dtype=float)
    coi = np.array(vis["coi"], dtype=float)

    inside = period[:, None] > coi[None, :]
    assert inside.mean() > 0.1, "this recording has no cone worth excluding"

    usable = np.isfinite(coh) & np.isfinite(level)[:, None]
    with_cone = np.sum((coh > level[:, None]) & usable) / np.sum(usable)
    without = np.sum((coh > level[:, None]) & usable & ~inside) / np.sum(usable & ~inside)

    assert with_cone > without + 0.03, (
        "the cone makes no difference here, so this test is not checking what "
        "it claims to")
    reported = stats(study, "noise_a_vs_noise_b")["wtc_signif_fraction"]
    assert abs(reported - without) < 0.01, (
        f"the reported fraction {reported:.4f} matches the with-cone figure "
        f"{with_cone:.4f} rather than the without-cone figure {without:.4f}")
