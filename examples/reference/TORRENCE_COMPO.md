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

## Eq. 30 — where Z_ν comes from, at any ν

Eq. 31 prints Z only at ν = 1 and 2, and for one commit that was taken to mean
the two *averaged* significance levels could not be corrected without Torrence
& Webster (1999). **That was wrong**, and the correction is worth stating
plainly because it turned two recorded defects into two fixes.

Immediately above eq. 31, the paper gives the distribution itself, for general
ν:

    f_ν(z) = 2^(2−ν) / Γ²(ν/2) · z^(ν−1) · K₀(z)                        (30)

"where z is the random variable, Γ is the Gamma function, and K₀ is the
modified Bessel function of order zero. The cumulative distribution function is
given by the integral p = ∫₀^{Z_ν(p)} f_ν(z) dz […] Given a probability p, this
integral can be inverted to find the confidence level Z_ν(p)."

So Z_ν is *defined* by an integral the paper tells you to invert, at whatever ν
you have. Doing exactly that reproduces both printed values:

| | derived | paper |
|---|---|---|
| Z₁(95 %) | 2.18195 | **2.182** |
| Z₂(95 %) | 3.99852 | **3.999** |

and continues past them, with Z_ν/ν falling as averaging buys degrees of
freedom:

| ν | 2 | 4 | 8 | 16 | 32 | 128 | 431 |
|---|---|---|---|---|---|---|---|
| Z_ν/ν | 1.999 | 1.768 | 1.564 | 1.406 | 1.290 | 1.146 | 1.079 |
| χ²_ν/ν | 2.996 | 2.372 | 1.938 | 1.644 | 1.444 | 1.214 | 1.115 |

The second row is what the code used to use, at every one of those ν.

`common/tc98.py` holds this. It integrates the equivalent product form —
z = √(XY) for independent χ²_ν, which is what eq. 30 is derived from — because
eq. 30 written out overflows double precision above ν = 60 and the
time-averaged test reaches ν = 431. Both routes are computed and compared
wherever both can run.

### The two siblings, now fixed

**`global_signif`** — the time-averaged spectrum. Degrees of freedom from
eq. 23, ν = 2√(1 + (n_a δt / γs)²), with γ = 2.32 from Table 2 and n_a the
number of points averaged, reduced toward long scales for the cone of
influence.

**`scale_avg_signif`** — the scale-averaged power, eqs. 25–28. ν comes from
eq. 28, ν = (2 n_a S_avg / S_mid)·√(1 + (n_a δj / δj₀)²) with δj₀ = 0.60, and
the level is eq. 26 with √(P^X_j P^Y_j) substituted for P_j in eq. 27. The
S_avg of eq. 25 appears on both sides and cancels.

How it is checked: substitute χ²_ν back for Z_ν and give the function one
spectrum twice, and it must reproduce `pycwt.significance` — to 1e-12, measured.
That pins the degrees of freedom, the scale axis and the background against an
independent implementation, leaving only the distribution as this project's own
claim, and that is what the paper's two printed values pin.

Measured effect on the reference study: the time-averaged level was **1.32–1.37×
too high**, the scale-averaged **1.267×**. For the one genuinely coupled pair
the verdict moved — the share of periods whose time-averaged cross-power clears
its own level went from 4.59 % to 8.26 %.

Nothing reads either field yet — checked across `dims-tabs/` and both studies'
own tabs. They are still computed and stored, now correctly; "unread" is why a
wrong number survives, not a reason to leave one.

## What this paper does **not** cover

Wavelet **coherence** is not in it. The smoothing operator and the coherence
formula come from Torrence & Webster (1999), and the Monte Carlo null for
coherence from Grinsted, Moore & Jevrejeva (2004). So the checks in this
directory that concern coherence are against those methods and against an
independently computed null, not against this paper.
