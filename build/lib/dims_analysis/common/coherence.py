"""Wavelet coherence, as one function the tests can actually call.

This is the measure the whole migration was prompted by, and it was wrong for
months in five repositories at once. The regression test for it then became the
second copy that drifts: it re-implemented the formula "isolated from the
step's file I/O", and its copy omitted the undefined-cell masking that the real
code had gained -- so the suite guarding the most important defect in the
project was testing something the product no longer did.

The formula (Torrence & Webster 1999):

           | S( s^-1 * W1 * conj(W2) ) |^2
  R^2 = ---------------------------------------
         S( s^-1 |W1|^2 ) * S( s^-1 |W2|^2 )

Two things about it are easy to get wrong, and both were:

**The smoothing operator S must be applied to the *complex* cross spectrum.**
Where the phase relationship is unstable the complex terms cancel under
smoothing and coherence drops -- that cancellation is the entire content of the
measure. Smoothing `|XWT|^2` instead destroys phase before it can cancel and
leaves the expression unnormalised, O(|W|^4) over O(|W|^2), which a clamp at 1.0
then hides. The result tracks signal power rather than coupling: 57% of cells at
exactly 1.0, correlation +0.87 with log power.

**Where neither signal has power, coherence is undefined -- not 1.** The
denominator collapses toward zero, the ratio explodes (176 has been observed),
and clipping paints perfect coupling across every stretch where nothing
happened. Those cells travel as NaN and are drawn as gaps. A gap is honest; a
bright band is not.
"""
from __future__ import annotations

import numpy as np

#: Anything above this cannot be a coherence; the denominator was degenerate.
_OVERSHOOT = 1e-6


def smoothed_spectra(W1, W2, scales, dt, dj, mother_wavelet):
    """`(S1, S2, S12)` -- the three smoothed terms of the ratio.

    Delegates to pycwt's validated smoothing operator, which applies the scale
    normalisation and the right kernels for the chosen wavelet. A hand-rolled
    smoother is what produced the defect above.
    """
    n = W1.shape[1]
    scales_2d = np.ones([1, n]) * np.asarray(scales)[:, None]
    xwt = W1 * np.conj(W2)
    return (mother_wavelet.smooth(np.abs(W1) ** 2 / scales_2d, dt, dj, scales),
            mother_wavelet.smooth(np.abs(W2) ** 2 / scales_2d, dt, dj, scales),
            mother_wavelet.smooth(xwt / scales_2d, dt, dj, scales))


def coherence_from_spectra(S1, S2, S12):
    """`(coherence, undefined)` from the smoothed spectra.

    `coherence` is NaN wherever `undefined` is true. The clip absorbs
    floating-point overshoot only: a cell materially above 1 is marked
    undefined rather than saturated, because if the clip ever has real work to
    do then the formula is wrong again.
    """
    denom = np.real(S1 * S2)
    positive = denom[denom > 0]
    floor = 1e-10 * np.median(positive) if positive.size else 0.0

    with np.errstate(divide="ignore", invalid="ignore"):
        wco = np.real(np.abs(S12) ** 2 / denom)

    undefined = ~np.isfinite(wco) | (denom <= floor)
    undefined |= wco > 1.0 + _OVERSHOOT
    return np.where(undefined, np.nan, np.clip(wco, 0.0, 1.0)), undefined


def coherence(W1, W2, scales, dt, dj, mother_wavelet):
    """The measure, end to end from two wavelet transforms."""
    return coherence_from_spectra(
        *smoothed_spectra(W1, W2, scales, dt, dj, mother_wavelet))
