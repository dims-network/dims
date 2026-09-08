# Torrence & Compo (1998), as this project uses it

Everything here is transcribed from the paper in this directory —
`Torrence_compo1998.pdf`, *Bull. Amer. Meteor. Soc.* **79**(1), 61–78 — with the
equation and table numbers so a reader can check the transcription rather than
trust it. Values are exact as printed.

The tests in `tests/test_wavelet_reference.py` assert against these, so a
number here that is wrong is a test that is wrong.

## Table 1 — Morlet, ω₀ = 6

| | |
|---|---|
| ψ₀(η) | π^(−1/4) e^(iω₀η) e^(−η²/2) |
| e-folding time τ_s | **√2 · s** |
| Fourier wavelength λ | **4πs / (ω₀ + √(2 + ω₀²))** |

For ω₀ = 6 that wavelength ratio is λ/s = **1.0330**, quoted in section 3h as
"λ = 1.03s", i.e. for Morlet the scale is almost equal to the Fourier period.

## Table 2 — empirically derived factors, Morlet ω₀ = 6

| | value | what it is for |
|---|---|---|
| C_δ | **0.776** | reconstruction factor, eq. 11 and 14 |
| γ | **2.32** | decorrelation factor for time averaging |
| δj₀ | **0.60** | factor for scale averaging |
| ψ₀(0) | **π^(−1/4)** | removes the energy scaling in eq. 11 |

## Equations this project depends on

**Eq. 9–10 — the scales.** s_j = s₀ 2^(jδj), j = 0…J, with
J = δj⁻¹ log₂(Nδt/s₀).

**Eq. 14 — energy conservation.** The check that a transform is normalised:

    σ² = (δj·δt) / (C_δ · N) · Σ_n Σ_j |W_n(s_j)|² / s_j

Section 3i says plainly that "both (11) and (14) should be used to check
wavelet routines for accuracy and to ensure that sufficiently small values of
s₀ and δj have been chosen."

**Eq. 16 — the red-noise (AR(1)) Fourier spectrum**, the background the
significance test is against:

    P_k = (1 − α²) / (1 + α² − 2α cos(2πk/N))

with α the lag-1 autocorrelation, and α = 0 giving white noise.

**Eq. 18 — the distribution of wavelet power.** At each time and scale,

    |W_n(s)|² / σ²  ⇒  ½ P_k χ²₂

so the 95 % level is ½ χ²₂(0.95) P_k σ². Since χ²₂(0.95) = 5.991, that half is
**2.996**, and Fig. 5a shows the white-noise 95 % level sitting at exactly
**3σ²** with a mean of **1σ²**. Those two numbers are the cleanest check on a
significance implementation that exists in the paper.

Note the χ²₂: for a **complex** wavelet like the Morlet there are two degrees of
freedom. A real-valued wavelet has one, and the paper says so explicitly.

## Choices the paper prescribes, and what this project does

| paper | says | `crosswavelet.py` |
|---|---|---|
| s₀ (§3f) | choose so the equivalent Fourier period is ≈ 2δt | `S0_FACTOR = 2` → period 2.07δt ✔ |
| δj (§3f) | ≤ 0.5 for Morlet; larger gives inadequate scale sampling | `DJ = 1/12` ≈ 0.083 ✔ |
| J (eq. 10) | δj⁻¹ log₂(Nδt/s₀) | same ✔ |
| padding (§3g) | pad with zeroes to the next power of two | left to `pycwt` |
| ω₀ (§3b) | 6, "to satisfy the admissibility condition" | `OMEGA0 = 6` ✔ |

## Eq. 31 — the cross-wavelet spectrum has its own distribution

Section 6c, and the one this project had wrong.

    |W_n^X(s) W_n^Y*(s)| / (σ_X σ_Y)  ⇒  (Z_ν(p) / ν) √(P_k^X P_k^Y)

with **Z₁(95%) = 2.182** for real wavelets and **Z₂(95%) = 3.999** for complex
ones. Morlet is complex, so the level is (3.999/2)·√(P^X P^Y) = **1.9995**·√(…).

`crosswavelet.py` asked pycwt for the *single-spectrum* level of eq. 18 instead
— χ²₂(95%)/2 = **2.9957** — and evaluated the background at the mean of the two
α rather than taking the geometric mean of the two spectra. Measured against the
paper: the level was 1.50× too high when the two coefficients matched, 1.71× at
α = (0.9, 0.5), and 2.39× at (0.95, 0.2).

The payload stores `power / level`, so the stored field was that much too small.
On the reference study the share of cells the built-in tab would call
significant went from 3.13 % to 9.10 % once corrected — it was drawing about a
third of the phase arrows it should.

### Two siblings, still wrong

The same mistake is in `global_signif` (crosswavelet.py:690) and
`scale_avg_signif` (:1028), which apply single-spectrum significance to
cross-wavelet quantities and use the mean of the two α. They are **not** fixed:
the paper gives eq. 31 only for the *local* spectrum, and the time- and
scale-averaged cross-wavelet distributions are in Torrence & Webster (1999),
which is not in this directory. Guessing at them would be worse than a recorded
wrong.

Nothing reads either field — checked across `dims-tabs/` and both studies' own
tabs — so they are computed, stored, and unused. Either correct them against
that paper or delete them. `test_wavelet_reference.py` carries an
`xfail(strict=True)` so the decision cannot quietly lapse.

## What this paper does **not** cover

Wavelet **coherence** is not in it. The smoothing operator and the coherence
formula come from Torrence & Webster (1999), and the Monte Carlo null for
coherence from Grinsted, Moore & Jevrejeva (2004). So the checks in this
directory that concern coherence are against those methods and against an
independently computed null, not against this paper.
