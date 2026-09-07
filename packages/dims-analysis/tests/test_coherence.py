"""Regression tests for the wavelet coherence defect.

These exist because the bug they catch shipped to five repositories and stood
for months. It was not a crash: the field looked plausible and was wrong, so
only a numerical check finds it. If someone reintroduces the old smoothing,
these fail immediately.

The defect: smoothing ``np.abs(XWT)**2`` instead of the complex cross-spectrum
destroys the phase cancellation that coherence measures, and leaves the ratio
unnormalised behind a clamp at 1.0. Measured effect on independent AR(1)
surrogates: 68% of cells at exactly 1.0, mean 0.76, r=0.88 against log power —
and independent noise scoring *higher* than genuinely coupled signals.
"""
import numpy as np
import pycwt as wavelet
import pytest

from dims_analysis.common import coherence as coh

DJ, S0_FACTOR, OMEGA0 = 1 / 12, 2.0, 6.0
N, DT = 1024, 0.02


def _coherence(d1, d2, dt=DT, dj=DJ):
    """The shipped implementation. Imported, not re-implemented.

    This function used to be a copy of the formula, "isolated from the step's
    file I/O" -- and the copy had already fallen behind the product: it omitted
    the masking of cells with too little power to define coherence, which is
    itself a fix for a variant of the very bug these tests exist to catch. A
    regression suite that is a second copy of the thing it guards eventually
    guards the copy.

    NaNs (undefined cells) are left in: a test that wants them gone says so.
    """
    mw = wavelet.Morlet(OMEGA0)
    s0 = S0_FACTOR * dt
    J = np.log2(len(d1) * dt / s0) / dj
    W1, scales, _, _, _, _ = wavelet.cwt(d1, dt, dj, s0, J, mw)
    W2, _, _, _, _, _ = wavelet.cwt(d2, dt, dj, s0, J, mw)
    wco, _undefined = coh.coherence(W1, W2, scales, dt, dj, mw)
    return wco


def _ar1(n, alpha=0.9, seed=0):
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = alpha * x[i - 1] + rng.standard_normal()
    return (x - x.mean()) / x.std()


@pytest.fixture(scope="module")
def t():
    return np.arange(N) * DT


def test_coherence_does_not_saturate(t):
    """The old code pinned 68% of cells at exactly 1.0. Nothing should saturate."""
    c = _coherence(_ar1(N, seed=1), _ar1(N, seed=2))
    saturated = float(np.mean(np.isclose(c, 1.0, atol=1e-9)))
    assert saturated < 0.01, f"{saturated:.1%} of cells sit at 1.0 — the clamp is doing real work"


def test_coherence_is_bounded(t):
    """A sanity check, NOT a regression guard.

    Verified: this one passes on the old implementation too, because it clamped
    with np.minimum(WCO, 1.0). The other three tests in this file were each
    checked against the old code and fail there — which is what makes them
    worth having.
    """
    c = _coherence(_ar1(N, seed=3), _ar1(N, seed=4))
    assert c.min() >= 0.0 and c.max() <= 1.0


def test_coupled_scores_higher_than_independent(t):
    """The property the old implementation actually inverted."""
    rng = np.random.default_rng(5)
    a = np.sin(2 * np.pi * 2 * t) + 0.3 * rng.standard_normal(N)
    b = np.sin(2 * np.pi * 2 * t + 0.7) + 0.3 * rng.standard_normal(N)
    coupled = float(_coherence(a, b).mean())
    independent = float(_coherence(_ar1(N, seed=6), _ar1(N, seed=7)).mean())
    assert coupled > independent, (
        f"coupled {coupled:.3f} did not exceed independent {independent:.3f} — "
        "this is exactly the inversion the old smoothing produced"
    )


def test_coherence_does_not_track_power(t):
    """Two independent series of very unequal power must not look coherent.

    The old code gave 0.95 here, because the expression reduced to a power
    product rather than a normalised phase measure.
    """
    loud = _ar1(N, seed=8) * 10.0
    quiet = _ar1(N, seed=9)
    c = _coherence(loud, quiet)
    assert c.mean() < 0.45, f"mean coherence {c.mean():.3f} between independent series"


# --- the second defect: stillness drawn as perfect coupling ------------------
#
# Reported from a study as "the network shows thick connections even when an
# effector is not moving", and it is a different bug from the one above. Where
# neither signal has power, the denominator collapses, the ratio explodes, and
# clipping it to 1.0 paints perfect coupling over every stretch where nothing
# happened. Nothing tested it until this suite stopped carrying its own copy of
# the formula and could see the masking at all.

def _mostly_still(n, active_from, seed):
    """Flat for the first half, then real movement."""
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    x[active_from:] = np.cumsum(rng.standard_normal(n - active_from))
    return x


def _transforms(d1, d2, dt=DT, dj=DJ):
    mw = wavelet.Morlet(OMEGA0)
    s0 = S0_FACTOR * dt
    J = np.log2(len(d1) * dt / s0) / dj
    W1, scales, _, _, _, _ = wavelet.cwt(d1, dt, dj, s0, J, mw)
    W2, _, _, _, _, _ = wavelet.cwt(d2, dt, dj, s0, J, mw)
    return W1, W2, scales, mw


def test_stillness_is_undefined_not_perfect_coupling():
    half = N // 2
    W1, W2, scales, mw = _transforms(_mostly_still(N, half, 1),
                                     _mostly_still(N, half, 2))
    wco, undefined = coh.coherence(W1, W2, scales, DT, DJ, mw)

    still = np.s_[:, : half // 2]     # well inside the flat stretch
    assert undefined[still].any(), (
        "no cell in a stretch where neither signal moves was marked undefined; "
        "those cells are being given a coherence value they cannot have")
    assert np.isnan(wco[still]).any()
    # And whatever survives there must not be the maximum.
    surviving = wco[still][~np.isnan(wco[still])]
    if surviving.size:
        assert surviving.max() < 1.0 - 1e-9, (
            "stillness scored perfect coherence, which is the reported defect")


def test_an_undefined_cell_is_nan_rather_than_clipped():
    """The clip must absorb float overshoot only, never a degenerate ratio."""
    S1 = np.array([[1.0, 1e-30]])
    S2 = np.array([[1.0, 1e-30]])
    S12 = np.array([[0.5 + 0j, 1e-12 + 0j]])   # second cell: huge ratio
    wco, undefined = coh.coherence_from_spectra(S1, S2, S12)

    assert not undefined[0, 0] and 0.0 <= wco[0, 0] <= 1.0
    assert undefined[0, 1] and np.isnan(wco[0, 1])


def test_a_real_coherence_is_not_marked_undefined():
    """The guard must not eat ordinary cells: it would hide real coupling."""
    t = np.arange(N) * DT
    base = np.sin(2 * np.pi * 0.7 * t)
    W1, W2, scales, mw = _transforms(base + 0.05 * _ar1(N, seed=3),
                                     base + 0.05 * _ar1(N, seed=4))
    wco, undefined = coh.coherence(W1, W2, scales, DT, DJ, mw)
    assert undefined.mean() < 0.05, (
        f"{undefined.mean():.1%} of cells called undefined for two clearly "
        "moving signals")
    assert np.nanmax(wco) > 0.8
