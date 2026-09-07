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

DJ, S0_FACTOR, OMEGA0 = 1 / 12, 2.0, 6.0
N, DT = 1024, 0.02


def _coherence(d1, d2, dt=DT, dj=DJ):
    """The shipped implementation, isolated from the step's file I/O."""
    mw = wavelet.Morlet(OMEGA0)
    s0 = S0_FACTOR * dt
    J = np.log2(len(d1) * dt / s0) / dj
    W1, scales, _, _, _, _ = wavelet.cwt(d1, dt, dj, s0, J, mw)
    W2, _, _, _, _, _ = wavelet.cwt(d2, dt, dj, s0, J, mw)
    XWT = W1 * np.conj(W2)
    n = W1.shape[1]
    scales_2d = np.ones([1, n]) * scales[:, None]
    S1 = mw.smooth(np.abs(W1) ** 2 / scales_2d, dt, dj, scales)
    S2 = mw.smooth(np.abs(W2) ** 2 / scales_2d, dt, dj, scales)
    S12 = mw.smooth(XWT / scales_2d, dt, dj, scales)
    return np.clip(np.real(np.abs(S12) ** 2 / (S1 * S2 + 1e-30)), 0.0, 1.0)


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
