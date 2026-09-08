"""The Torrence & Compo (1998) significance distributions, in one place.

`examples/reference/Torrence_compo1998.pdf` is the paper; every equation number
below refers to it, and `examples/reference/TORRENCE_COMPO.md` transcribes the
constants and tables so a reader does not have to open the PDF to check a
number.

Why this module exists at all: three significance levels were computed in
`steps/crosswavelet.py`, and **all three used the wrong distribution**. The
cross-wavelet spectrum is the square root of a product of two chi-squares
(eq. 30), not a chi-square (eq. 18), and the difference is not small -- the
level came out 1.50x too high with matched AR(1) coefficients and 2.39x too
high at alpha = (0.95, 0.2). Two of the three also evaluated the background at
the *mean* of the two series' alphas instead of combining their two spectra.

The first of the three was corrected against the paper's tabulated
Z_2(95%) = 3.999. That fixed the local spectrum and left its two siblings --
the time-averaged and scale-averaged levels -- wrong, on the stated grounds
that the paper gives Z only at nu = 1 and 2 and the averaged distributions
would need Torrence & Webster (1999). **That was wrong.** Eq. 30 is stated for
general nu, and integrating it numerically reproduces both published values:

    Z_1(95%) = 2.18195   paper: 2.182
    Z_2(95%) = 3.99852   paper: 3.999

So the whole family is available from this paper alone, and the two siblings
are fixed here rather than left recorded as defects.
"""
from __future__ import annotations

import functools

import numpy as np
from scipy import integrate, optimize, special, stats

#: The confidence level everything here is computed at. Both published Z values
#: are 95 % ones; the derivation below is not restricted to that, but no other
#: level has a paper value to check it against.
DEFAULT_LEVEL = 0.95

#: Torrence & Compo eq. 31, printed: Z_1(95%) = 2.182 for real wavelets,
#: Z_2(95%) = 3.999 for complex ones. These are the anchors the derivation is
#: tested against (`test_wavelet_reference.py`), not what the code uses -- using
#: them would leave a table with two rows where the analysis needs a function.
Z1_95_PUBLISHED = 2.182
Z2_95_PUBLISHED = 3.999

#: Where the density of eq. 30 stops being computable in double precision.
#: `z^(nu-1)` overflows and `2^(2-nu)` underflows; their product is finite but
#: evaluating it term by term is not. Measured over the whole range of z:
#: exact at nu = 60, `nan` at 70.
MAX_DIRECT_NU = 60.0


def cross_wavelet_pdf(z, nu: float):
    """Torrence & Compo eq. 30: the density of the cross-wavelet spectrum.

        f_nu(z) = 2^(2-nu) / Gamma^2(nu/2) * z^(nu-1) * K_0(z)

    where K_0 is the modified Bessel function of order zero. This is the
    distribution of the square root of the product of two chi-square variables
    with `nu` degrees of freedom each (Jenkins & Watts 1968, cited there), which
    is what |W^X W^Y*| is -- and is why the chi-square of eq. 18 does not apply
    to it.

    It integrates to 1 for every nu the double-precision range allows (1 to 60,
    to 1e-9), which is the check that the transcription is right.
    """
    z = np.asarray(z, dtype=float)
    return (2.0 ** (2 - nu) / special.gamma(nu / 2.0) ** 2
            * z ** (nu - 1) * special.kv(0, z))


def survival_by_quadrature(z: float, nu: float) -> float:
    """P(Z > z) straight from eq. 30, by integrating the density.

    Correct and slow, and it overflows above nu = 60: the density carries
    `z^(nu-1)` against `2^(2-nu)`, both beyond double precision long before the
    scales a 1024-point series produces (the smallest one reaches nu = 431).
    So this is the *definition* -- kept because it is the paper's own formula
    and because it is what `survival` is tested against -- while `survival`
    below is what the analysis calls. Above the limit it refuses rather than
    returning the `nan` that the overflow produces.
    """
    if nu > MAX_DIRECT_NU:
        raise ValueError(
            f"eq. 30 evaluated directly overflows above nu = {MAX_DIRECT_NU} "
            f"(asked for {nu}); use survival(), which is the same distribution "
            f"written so it can be computed.")
    value, _ = integrate.quad(cross_wavelet_pdf, z, np.inf, args=(nu,), limit=300)
    return float(value)


#: Nodes for the quadrature in `survival`. Gauss-Legendre mapped onto the
#: probability axis rather than onto x: 600 nodes then span whatever range the
#: distribution actually occupies, at every nu, with no window to tune. On a
#: window in log x instead, a fixed width is either too narrow for nu = 1 or far
#: too wide for nu = 431, where it lost four digits.
_GL_NODES, _GL_WEIGHTS = np.polynomial.legendre.leggauss(600)
_Q = 0.5 * (_GL_NODES + 1.0)
_QW = 0.5 * _GL_WEIGHTS


def survival(z: float, nu: float) -> float:
    """P(Z > z), where Z = sqrt(X Y) and X, Y are independent chi2_nu.

    That is the same distribution as eq. 30 -- the paper derives eq. 30 from
    exactly this product (Jenkins & Watts 1968) -- but written so it can be
    evaluated at any nu. Conditioning on X and integrating over its probability
    axis,

        P(Z > z) = int_0^1 P(chi2_nu > z^2 / F^-1(q)) dq

    which is bounded, smooth, and needs no scale window. It agrees with
    `survival_by_quadrature` to 2e-7 wherever that one can run at all (nu <= 60),
    which is the adaptive integrator's own accuracy on a density spanning tens
    of orders of magnitude -- and it keeps working to nu = 5000, where the
    time-averaged test needs it.
    """
    x = _chi2_nodes(round(float(nu), 9))
    return float(np.sum(_QW * stats.chi2.sf(z * z / x, nu)))


@functools.lru_cache(maxsize=4096)
def _chi2_nodes(nu: float) -> np.ndarray:
    nodes = stats.chi2.ppf(_Q, nu)
    nodes.flags.writeable = False
    return nodes


@functools.lru_cache(maxsize=4096)
def _z_cached(nu: float, level: float) -> float:
    target = 1.0 - level
    upper = max(8.0, 4.0 * nu)
    return float(optimize.brentq(lambda z: survival(z, nu) - target,
                                 1e-9, upper, xtol=1e-10, rtol=1e-12))


def cross_wavelet_z(nu, level: float = DEFAULT_LEVEL):
    """Z_nu(p): the confidence level of eq. 30, by inverting its CDF.

    The paper defines it exactly this way -- "the cumulative distribution
    function is given by the integral p = int_0^Z_nu(p) f_nu(z) dz [...] this
    integral can be inverted to find the confidence level Z_nu(p)" -- so this
    is the paper's own definition evaluated, not an approximation to it.

    Accepts a scalar or an array of degrees of freedom, because the
    time-averaged test has a different nu at every scale. Results are cached on
    (nu, level) rounded to 1e-9, since a scale array repeats values.
    """
    scalar = np.isscalar(nu) or np.ndim(nu) == 0
    values = np.atleast_1d(np.asarray(nu, dtype=float))
    if np.any(values <= 0):
        raise ValueError("degrees of freedom must be positive")
    out = np.array([_z_cached(round(float(v), 9), level) for v in values])
    return float(out[0]) if scalar else out


def ar1_background(alpha: float, period, dt: float):
    """The AR(1) Fourier spectrum, eq. 16.

        P_k = (1 - a^2) / (1 + a^2 - 2a cos(2 pi k / N))

    evaluated at the Fourier frequency each wavelet scale corresponds to. This
    is the background every significance test here is measured against;
    multiplying it by chi2_2(0.95)/2 reproduces `pycwt.significance` exactly,
    which is how the transcription was checked.
    """
    frequency = dt / np.asarray(period, dtype=float)
    return ((1 - alpha ** 2)
            / (1 + alpha ** 2 - 2 * alpha * np.cos(2 * np.pi * frequency)))


def _joint_background(alpha1: float, alpha2: float, period, dt: float):
    """sqrt(P^X_k P^Y_k) -- the two series' own spectra, combined as eq. 31 says.

    The defect this replaces used one spectrum evaluated at `mean(alpha1,
    alpha2)`. That is a different number whenever the two series differ in
    redness, and it is not a conservative substitution in either direction.
    """
    return np.sqrt(ar1_background(alpha1, period, dt)
                   * ar1_background(alpha2, period, dt))


def local_significance(alpha1: float, alpha2: float, period, dt: float,
                       level: float = DEFAULT_LEVEL):
    """The level for |W^X W^Y*| at each scale, eq. 31 with nu = 2.

        |W^X W^Y*| / (sigma_X sigma_Y)  =>  (Z_nu(p) / nu) sqrt(P^X_k P^Y_k)

    Complex wavelets give each point two degrees of freedom (Table 2,
    `dofmin = 2`), so nu = 2 and Z_2/2 = 1.9993 -- against the chi2_2/2 = 2.9957
    that was used before, hence the 1.50x.
    """
    nu = 2.0
    return (cross_wavelet_z(nu, level) / nu) * _joint_background(alpha1, alpha2,
                                                                 period, dt)


def time_average_dof(n_averaged, scales, dt: float, gamma: float,
                     dofmin: float = 2.0):
    """Degrees of freedom after averaging `n_averaged` points in time, eq. 23.

        nu = 2 sqrt(1 + (n_a dt / (gamma s))^2)

    `gamma` is the wavelet's decorrelation factor (Table 2: 2.32 for Morlet),
    and `dofmin` the 2 of a complex wavelet -- "for a real-valued function [...]
    each point only has one DOF, and the factor of 2 in (23) is removed".

    Averaging more points buys more degrees of freedom and so a lower level;
    the floor is `dofmin`, because averaging fewer points than one
    decorrelation length buys nothing.
    """
    n_averaged = np.clip(np.asarray(n_averaged, dtype=float), 1.0, None)
    scales = np.asarray(scales, dtype=float)
    nu = dofmin * np.sqrt(1.0 + (n_averaged * dt / (gamma * scales)) ** 2)
    return np.maximum(nu, dofmin)


def time_average_significance(alpha1: float, alpha2: float, scales, dt: float,
                              n_averaged, mother, level: float = DEFAULT_LEVEL):
    """The level for a **time-averaged** cross-wavelet spectrum.

    Same shape as `local_significance`, with nu from eq. 23 rather than fixed at
    2, exactly as the single-spectrum test of eq. 23 relates to eq. 18. Where
    this and `pycwt.significance(sigma_test=1)` differ is only the two places
    the cross-wavelet case differs at all: Z_nu in place of chi2_nu, and
    sqrt(P^X P^Y) in place of one spectrum. That correspondence is tested by
    substituting chi2 back in and comparing to pycwt.

    `n_averaged` is the number of local spectra averaged at each scale. For a
    global spectrum that is N, reduced near the cone of influence -- the paper:
    "if the points going into the average are within the cone of influence, then
    n_a is reduced by approximately one-half of the number within the COI".
    """
    period = np.asarray(scales, dtype=float) * mother.flambda()
    nu = time_average_dof(n_averaged, scales, dt, mother.gamma, mother.dofmin)
    return (cross_wavelet_z(nu, level) / nu) * _joint_background(alpha1, alpha2,
                                                                period, dt)


def scale_average_dof(scales, selected, dj: float, dofmin: float = 2.0,
                      dj0: float = 0.60):
    """Degrees of freedom after averaging over a scale band, eq. 28.

        nu = (2 n_a S_avg / S_mid) sqrt(1 + (n_a dj / dj0)^2)

    with S_avg from eq. 25 and S_mid the geometric mid-point of the band. The
    paper notes (28) "is valid only for confidences of 95% or less"; nothing
    here asks for more.
    """
    scales = np.asarray(scales, dtype=float)
    band = scales[selected]
    if band.size == 0:
        raise ValueError("no scales in the averaging band")
    n_avg = band.size
    s_avg = 1.0 / np.sum(1.0 / band)                       # eq. 25
    s_mid = np.exp((np.log(band[0]) + np.log(band[-1])) / 2.0)
    return ((dofmin * n_avg * s_avg / s_mid)
            * np.sqrt(1.0 + (n_avg * dj / dj0) ** 2))


def scale_average_significance(alpha1: float, alpha2: float, scales, dt: float,
                               dj: float, selected, mother,
                               level: float = DEFAULT_LEVEL) -> float:
    """The level for a **scale-averaged** cross-wavelet power, eqs. 25-28 + 30.

    Eq. 26 for one spectrum reads

        C_delta S_avg / (dj dt sigma^2) * Wbar^2  =>  Pbar chi2_nu / nu

    and the cross-wavelet form substitutes |W^X W^Y*| for |W|^2, sigma_X sigma_Y
    for sigma^2, sqrt(P^X_j P^Y_j) for P_j in eq. 27, and Z_nu for chi2_nu.
    Rearranged for the quantity actually stored -- the scale-averaged power
    itself -- S_avg cancels and the level is

        (dj dt / C_delta) * sum_band sqrt(P^X_j P^Y_j) / s_j * Z_nu / nu

    Returned as a single number: the band is fixed, so the level does not vary
    with time.
    """
    scales = np.asarray(scales, dtype=float)
    period = scales * mother.flambda()
    background = _joint_background(alpha1, alpha2, period, dt)
    nu = scale_average_dof(scales, selected, dj, mother.dofmin, mother.deltaj0)
    band_sum = float(np.sum(background[selected] / scales[selected]))   # eq. 27
    return float(dj * dt / mother.cdelta * band_sum
                 * cross_wavelet_z(nu, level) / nu)                     # eq. 26
