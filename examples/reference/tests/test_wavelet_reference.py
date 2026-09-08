"""The wavelet transform itself, against published values and an independent path.

Everything else here tests coherence, which is built on the transform. This
file tests the transform, and it deliberately does not compare pycwt to pycwt:
that would be circular, and pycwt is the only wavelet implementation installed.

Two kinds of reference are used instead.

**Torrence & Compo (1998)**, "A Practical Guide to Wavelet Analysis",
*Bull. Amer. Meteor. Soc.* 79(1), 61-78 -- the paper this analysis follows.
Its Tables 1 and 2 give exact constants for the Morlet wavelet at omega0 = 6,
and its equation 14 gives an identity the transform must satisfy. Those are
independent of any code.

**An independently computed Monte Carlo null**: surrogates generated here,
coherence taken with this project's own validated function, percentile taken
directly rather than through pycwt's histogram. Different code, same quantity.
"""
from __future__ import annotations

import numpy as np
import pycwt
import pytest

# --- the parameters this project analyses with -------------------------------
OMEGA0 = 6.0
DJ = 1 / 12
DT = 0.02
S0_FACTOR = 2.0

# --- Torrence & Compo (1998), Morlet, omega0 = 6 ------------------------------
#: Table 1: the Fourier period a scale corresponds to,
#: lambda/s = 4*pi / (omega0 + sqrt(2 + omega0^2)).
TC_PERIOD_PER_SCALE = 1.0330
#: Table 2: the reconstruction factor in the energy identity, eq. 14.
TC_C_DELTA = 0.776
#: Table 1: the e-folding time of the wavelet, in units of the scale.
TC_EFOLDING = np.sqrt(2)

MOTHER = pycwt.wavelet.Morlet(OMEGA0)


def transform(x, dt=DT, dj=DJ, s0_factor=S0_FACTOR, extra_octaves=0):
    """The transform as this project configures it, or with a wider scale range.

    `s0_factor` and `extra_octaves` exist for the energy identity, which is
    only meaningful when the scale range is not what limits it.
    """
    s0 = s0_factor * dt
    J = int(np.log2(len(x) * dt / s0) / dj) + int(extra_octaves / dj)
    return pycwt.cwt(np.asarray(x, dtype=float), dt, dj, s0, J, MOTHER)


def sine(n=1024, period=2.0, dt=DT):
    return np.sin(2 * np.pi * (1.0 / period) * np.arange(n) * dt)


# --- the scale axis, against the published relation --------------------------

def test_the_period_of_a_scale_is_the_published_one():
    """Table 1 of Torrence & Compo: lambda/s = 1.0330 for Morlet at omega0 = 6.

    This is the conversion every period axis in every heatmap depends on. If it
    drifted, nothing would look wrong -- the picture would simply be labelled
    with the wrong timescales throughout.
    """
    _W, scales, freqs, _coi, _fft, _f = transform(sine())
    ratio = (1.0 / freqs) / scales
    assert np.allclose(ratio, ratio[0]), "the ratio must not vary with scale"
    assert abs(ratio[0] - TC_PERIOD_PER_SCALE) < 1e-4, (
        f"period/scale is {ratio[0]:.6f}; Torrence & Compo Table 1 gives "
        f"{TC_PERIOD_PER_SCALE} for Morlet at omega0 = {OMEGA0}")


def test_a_sine_puts_its_power_at_its_own_period():
    """The end-to-end consequence of the relation above: a 2 s sine must peak
    at 2 s, not at its scale and not at its frequency."""
    for period in (1.0, 2.0, 4.0):
        W, scales, freqs, _coi, _fft, _f = transform(sine(period=period))
        periods = 1.0 / freqs
        peak = periods[int(np.argmax(np.mean(np.abs(W) ** 2, axis=1)))]
        assert abs(peak - period) / period < 0.05, (
            f"a {period} s sine peaked at {peak:.4f} s")


# --- the energy identity, against the published constant ---------------------

@pytest.mark.parametrize("name,narrowband", [("sine", True), ("noise", False)])
def test_the_power_sums_back_to_the_variance(name, narrowband):
    """Torrence & Compo eq. 14, with C_delta = 0.776 from their Table 2:

        sigma^2 = (dj*dt) / (C_delta*N) * sum_n sum_j |W_n(s_j)|^2 / s_j

    A transform whose normalisation is wrong fails this identity and nothing
    else, so it is the check worth having on the transform itself.

    **The scale range is widened here on purpose**, and finding out why took
    measuring. At this project's own settings the identity recovers 0.9874 of
    a sine's variance but only 0.9259 of white noise's, and my first assumption
    -- that the longest scales were truncated -- was wrong: extending J upward
    by four octaves changes nothing (0.9263). The missing energy is at the
    *short* end. `s0 = 2*dt` is a period of 0.0413 s against a Nyquist period
    of 0.04 s, so white noise, which has power right up to Nyquist, keeps some
    of it above the shortest analysed scale. Lowering s0 to dt recovers it:
    0.9838.

    What remains is about 1.5 % and it does not go away. It is independent of
    the record length (0.9876 for a sine at N from 512 to 8192) and of the
    scale resolution (identical for dj from 0.25 down to 1/48; only dj = 0.5,
    which the paper warns against, overshoots at 1.045). So it is the accuracy
    of the published constant itself, which Torrence & Compo derived
    numerically -- not an error in this pipeline.
    """
    n = 2048
    x = (sine(n) if narrowband
         else np.random.default_rng(7).standard_normal(n))
    x = x - x.mean()
    # s0 = dt rather than 2*dt, and two extra octaves at the long end, so that
    # neither end of the scale range is what limits the sum.
    W, scales, _freqs, _coi, _fft, _f = transform(x, s0_factor=1.0,
                                                  extra_octaves=2)
    reconstructed = ((DJ * DT) / (TC_C_DELTA * n)
                     * float(np.sum(np.abs(W) ** 2 / scales[:, None])))
    ratio = reconstructed / float(x.var())
    assert 0.97 < ratio < 1.02, (
        f"{name}: the wavelet power reconstructs {ratio:.4f} of the variance; "
        f"Torrence & Compo eq. 14 with C_delta = {TC_C_DELTA} says 1.0")


def test_what_this_projects_own_settings_recover():
    """The test above widens the scale range, so on its own it says nothing
    about the configuration actually shipped. This pins that.

    `S0_FACTOR = 2` (crosswavelet.py:70) puts the shortest analysed period at
    2 * 1.033 * dt, just above Nyquist, and `J = log2(N*dt/s0)/dj` (:512) takes
    the longest out to the record length. Those are Torrence & Compo's own
    recommendations, and the consequence is arithmetic rather than a defect:
    a signal whose power sits inside the band is recovered almost entirely,
    and white noise, which has power right up to Nyquist, is not.

    Measured at the shipped settings: 0.9874 for a 2 s sine, 0.9259 for white
    noise. If either moves, the scale range has changed and every study's
    output has changed with it.
    """
    n = 2048
    rng = np.random.default_rng(7)
    for name, x, expected in (("sine", sine(n), 0.9874),
                              ("white noise", rng.standard_normal(n), 0.9259)):
        x = x - x.mean()
        W, scales, _f, _c, _ff, _f2 = transform(x)      # the shipped settings
        ratio = ((DJ * DT) / (TC_C_DELTA * n)
                 * float(np.sum(np.abs(W) ** 2 / scales[:, None]))) / x.var()
        assert abs(ratio - expected) < 0.01, (
            f"{name}: this project's settings recover {ratio:.4f} of the "
            f"variance, where they recovered {expected} when measured")


def test_the_short_end_of_the_scale_range_is_what_truncates_the_energy():
    """Why the settings this project actually uses recover less, and by how
    much -- so that the number in the test above is not mistaken for a defect.

    `s0 = 2*dt` puts the shortest analysed period just above Nyquist. A sine at
    2 s does not care; white noise loses 6 % of its variance there.
    """
    n = 2048
    noise = np.random.default_rng(7).standard_normal(n)
    noise = noise - noise.mean()

    def recovered(s0_factor):
        W, scales, _f, _c, _ff, _f2 = transform(noise, s0_factor=s0_factor,
                                                extra_octaves=2)
        return ((DJ * DT) / (TC_C_DELTA * n)
                * float(np.sum(np.abs(W) ** 2 / scales[:, None]))) / noise.var()

    at_project_settings = recovered(S0_FACTOR)
    with_shorter_scales = recovered(1.0)
    assert at_project_settings < with_shorter_scales - 0.03, (
        f"lowering s0 recovered {with_shorter_scales:.4f} against "
        f"{at_project_settings:.4f}; the short end is not the limiting factor "
        f"here, so the explanation in the test above is wrong")


# --- the cone of influence ---------------------------------------------------

def test_the_cone_is_zero_at_the_edges_and_linear_inside():
    """The wavelet window runs past the data at the ends, so the cone admits
    nothing at the very edge and opens out linearly with distance from it."""
    n = 512
    _W, _scales, _freqs, coi, _fft, _f = transform(sine(n))
    t = np.arange(n) * DT
    distance = np.minimum(t, t[-1] - t)

    assert coi[0] < 0.05, f"the cone is {coi[0]:.4f} s at the very edge"
    slope, intercept = np.polyfit(distance[5:n // 2], coi[5:n // 2], 1)
    assert abs(intercept) < 0.05, f"the cone does not start at zero: {intercept:.4f}"
    assert slope > 0


def test_the_cone_grows_at_the_rate_the_paper_gives():
    """Torrence & Compo's e-folding time, followed exactly.

    The paper gives the Morlet e-folding time as tau_s = sqrt(2)*s. At a
    distance d from the edge a scale is contaminated when sqrt(2)*s > d, so the
    trustworthy scales are s < d/sqrt(2), which as a Fourier period is

        lambda < flambda * d / sqrt(2) = 0.730472 * d

    Measured slope: 0.730472, agreeing to 1.7e-07.

    I first wrote this test asserting a *discrepancy*, having compared the
    measured slope against sqrt(2)*flambda = 1.4609 -- the e-folding time
    converted to a period, which is not the cone boundary. It is half that, and
    the factor of two was mine.
    """
    n = 512
    _W, _scales, _freqs, coi, _fft, _f = transform(sine(n))
    t = np.arange(n) * DT
    distance = np.minimum(t, t[-1] - t)
    slope = float(np.polyfit(distance[5:n // 2], coi[5:n // 2], 1)[0])

    expected = TC_PERIOD_PER_SCALE / TC_EFOLDING
    assert abs(slope - expected) < 1e-4, (
        f"the cone grows at {slope:.6f} per unit distance from the edge; "
        f"Torrence & Compo imply flambda/sqrt(2) = {expected:.6f}")


# --- the Monte Carlo null, computed a second way -----------------------------

def ar1_series(n, alpha, rng):
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = alpha * x[i - 1] + rng.standard_normal()
    return (x - x.mean()) / x.std()


def independent_null(n=512, alpha=0.9, pairs=200, seed=4242):
    """The 95th percentile of coherence between unrelated AR(1) signals,
    computed here rather than by pycwt.

    Surrogates generated in this file, coherence taken with this project's own
    `common.coherence` (itself checked against the phase and against scipy),
    percentile taken directly. pycwt instead bins each scale into a histogram
    and reads the percentile off that, so this is a genuinely different route
    to the same number.

    Cells inside the cone are excluded, because pycwt excludes them too --
    which is not a detail: including them makes the longest scales disagree by
    0.28, since almost the whole record is inside the cone there.
    """
    from dims_analysis.common import coherence as coh

    rng = np.random.default_rng(seed)
    stack, coi, scales = [], None, None
    for _ in range(pairs):
        W1, scales, _freqs, coi, _fft, _f = transform(ar1_series(n, alpha, rng))
        W2, _s, _fr, _c, _ff, _f2 = transform(ar1_series(n, alpha, rng))
        value, _undefined = coh.coherence(W1, W2, scales, DT, DJ, MOTHER)
        stack.append(value)

    period = scales * MOTHER.flambda()
    outside = period[:, None] < coi[None, :]
    masked = np.where(outside[None, :, :], np.stack(stack), np.nan)
    with np.errstate(invalid="ignore"):
        return np.nanpercentile(masked, 95, axis=(0, 2))


def test_the_monte_carlo_null_matches_one_computed_independently():
    """The expensive computation, checked by a second implementation.

    Everything else about the null tests its consequences -- that 5 % of cells
    from the null exceed it, that it is not flat, that it is reproducible. This
    tests the number itself.

    Measured over 200 surrogate pairs: the shortest quarter of the scales
    agrees to 0.004, the middle half to 0.003. The longest quarter does not,
    and that is a property of the data rather than of either implementation:
    almost nothing there lies outside the cone, so both estimates come from a
    handful of cells and neither is reliable. A reader should treat the level
    at the extremes of the band with the same caution.
    """
    from dims_analysis.steps import crosswavelet as cw

    mine = independent_null()
    cw._WCT_SIGNIF_CACHE.clear()
    theirs = np.asarray(
        cw._wct_significance_level(0.9, 0.9, DT, DJ, S0_FACTOR * DT,
                                   len(mine), MOTHER, mc_count=200),
        dtype=float)

    quarter = len(mine) // 4
    well_determined = slice(0, 3 * quarter)
    a, b = mine[well_determined], theirs[well_determined]
    usable = np.isfinite(a) & np.isfinite(b)
    assert usable.sum() > 20, "too few comparable scales to conclude anything"

    difference = float(np.nanmean(np.abs(a[usable] - b[usable])))
    assert difference < 0.05, (
        f"two independent computations of the same null differ by "
        f"{difference:.4f} on average over the well-determined scales")


def test_more_surrogates_does_not_move_the_answer():
    """What the surrogate count buys, and where it stops buying.

    The count is a compute budget: 300 surrogates cost 2.8 hours on a
    twelve-recording study and 20 cost minutes. If the answer still moved
    between them, the cheap setting would be wrong to offer.

    Measured on the fraction of null cells exceeding their own level: 0.1336 at
    20 surrogates, 0.1343 at 100, 0.1343 at 300 -- under 0.001 across a
    fifteenfold increase. (Those figures include the cone, which is why they
    are near 0.13 rather than 0.05; what matters here is that they do not
    move.)
    """
    from dims_analysis.steps import crosswavelet as cw

    levels = {}
    for count in (20, 100):
        cw._WCT_SIGNIF_CACHE.clear()
        levels[count] = np.asarray(
            cw._wct_significance_level(0.9, 0.9, DT, DJ, S0_FACTOR * DT, 60,
                                       MOTHER, mc_count=count), dtype=float)

    usable = np.isfinite(levels[20]) & np.isfinite(levels[100])
    moved = float(np.nanmean(np.abs(levels[20][usable] - levels[100][usable])))
    assert moved < 0.05, (
        f"the level moved {moved:.4f} between 20 and 100 surrogates; the cheap "
        f"setting is then not a reasonable default")
