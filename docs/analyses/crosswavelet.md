# Cross-wavelet analysis

Two people move. Do they move *together*? The question hides a second one —
together at what timescale? A pair can share a slow sway and share nothing at
all in their fast adjustments, and a single correlation coefficient will average
those into one number that describes neither.

The wavelet transform answers timescale by timescale, moment by moment. The
cross-wavelet transform asks where two signals have **energy at the same
timescale at the same time**, and coherence asks whether, where they do, they
keep a **consistent timing relationship**.

Those are different questions, they have different answers, and confusing them
is the most common way to over-read this analysis. The rest of this page is
mostly about telling them apart.

- Step id `crosswavelet`, gated by `include_crosswavelet`, a list of pairs.
- Writes `assets/crosswavelet/{video}_crosswavelet_data.json`, and — unless you
  turn it off — `{video}_crosswavelet_full.json` beside it.
- Built on [pycwt](https://github.com/regeirk/pycwt), pinned at `0.5.0b0`, with
  the significance levels re-derived in-house from Torrence & Compo (1998).

## What it looks like

Both figures below are the payload from
[`demo_crosswavelet.json`](demo/demo_crosswavelet.json), which
[`make_demo_data.py`](demo/make_demo_data.py) produced by running the step over
the two synthetic signals from the [overview](index.md).

<div class="figure" id="fig-xwt-power"></div>

<div class="figure" id="fig-xwt-coherence"></div>

Read those two together. The burst between 20 s and 35 s is the brightest thing
in the power plot and is unremarkable in the coherence plot, because the two
signals oscillate there at 1.20 s and 1.45 s — nearly the same energy at nearly
the same time, with a relationship that drifts. The 4-second band is the reverse:
modest power, coherence close to 1 for the whole record, and phase arrows that
all point the same way.

That is the entire argument for computing both.

## Preparing the signals

Before anything is transformed, each series is cleaned and each pair is put on
one clock.

1. **Read and clean.** The `Time` column is matched under any casing, rows with
   missing values are dropped. Fewer than **50 samples** and the pair is skipped.
2. **Detrend.** A first-order polynomial is fitted against time and subtracted.
   Not just the mean: a linear drift puts power at the longest periods, which is
   exactly where the cone of influence already makes the answer weakest.
3. **Normalise.** Divide by the standard deviation, so the series is unit
   variance. Power is therefore in units of *normalised signal squared*, and is
   not comparable to a physical quantity.
4. **Align.** The pair is cut to the overlap of the two time ranges, and both
   are linearly interpolated onto a uniform grid at `min(Δt₁, Δt₂)`, the finer
   of the two. The overlap must be at least **50 % of the longer of the two
   recordings** — `(t_end − t_start) / max(span₁, span₂)` — or the pair is
   skipped. Note which way round that is: a 10 s series overlapping a 60 s one
   completely is still refused.
5. **Taper.** A Tukey window with α = 0.05 is applied to both. This softens the
   first and last 2.5 % of the record so the ends do not ring; it does not
   replace the cone of influence, which is about the same problem from the other
   side.

## The transform

The mother wavelet is **Morlet with ω₀ = 6**:

```
ψ₀(η) = π^(−1/4) · e^(iω₀η) · e^(−η²/2)
```

ω₀ = 6 is the usual choice because it is the smallest value for which the
wavelet is (near enough) admissible without a correction term, and it puts the
wavelet scale and the Fourier period within a few percent of each other:

```
period = 1.03 · s          (Morlet, ω₀ = 6)
```

so a "scale" and a "period in seconds" can be read as almost the same number.
Almost — the payload stores both `scales` and `period`, and the difference
matters in exactly one place, noted under the cone of influence below.

Scales are laid out as powers of two, `sⱼ = s₀ · 2^(jδj)`:

| quantity | value | meaning |
|---|---|---|
| `s0` | `2Δt` | the smallest resolvable scale — two samples |
| `dj` | `1/12` | twelve sub-octaves per octave, fine enough that the scale axis looks continuous |
| `J` | `log₂(NΔt / s₀) / δj` | enough octaves to reach the length of the record, unless `maxPeriod` caps it |

The transform itself is `pycwt.cwt`, which pads the series to the next power of
two internally and removes the padding afterwards.

### Cross-wavelet power and phase

With `W^X` and `W^Y` the transforms of the two prepared signals, the
cross-wavelet transform is

```
W^XY(s, t) = W^X(s, t) · conj(W^Y(s, t))
```

and the payload stores its modulus and its argument:

```
power = |W^XY|          phase = arg(W^XY)  ∈ (−π, π]
```

Note that `power` is the **modulus, not the modulus squared**. That is not a
stylistic choice: Torrence & Compo's eq. 31 states its significance level for
`|W^X W^Y*|`, and storing the square beside a level derived for the modulus is
how a plot ends up with an unfalsifiable amount of significance in it.

`phase` is the lead–lag, read as an angle: 0 means in phase, and a phase of φ at
period *T* corresponds to a delay of `φT / 2π` seconds. In the figure above, the
4 s band sits at roughly 1.1 rad, which is the 0.7 s delay the signals were
built with.

### Coherence

Coherence is the cross-spectrum normalised by the two auto-spectra, each
smoothed first in time and in scale (Torrence & Webster 1999):

```
              | S( s⁻¹ · W^XY ) |²
    R²(s,t) = ─────────────────────────────────────
              S( s⁻¹|W^X|² ) · S( s⁻¹|W^Y|² )
```

The smoothing operator `S` is pycwt's `mother.smooth()` — the wavelet's own time
and scale kernels — and **it is applied to the complex cross-spectrum**. That
detail is the whole mechanism: coherence works by letting mismatched timing
cancel during smoothing. Smooth the magnitude instead and nothing can ever
cancel, and the answer is near 1 everywhere. See the defects section below;
this project shipped that bug.

Two guards sit on the result:

- Where the denominator is at or below a floor of 1e-10 × its own median — that
  is, where neither signal has meaningful energy — the cell is **NaN**, not 1.0.
  Stillness is not perfect synchrony, and capping it at the maximum is how a
  recording of two people sitting still comes out looking perfectly coupled.
- Values above 1 by more than 1e-6 are treated as undefined rather than clipped,
  because a coherence above 1 means the arithmetic went wrong, not that the
  coupling was unusually good.

## Parameters

### Set in the study's `config.json`, under `analysis.crosswavelet`

| key | type | default | what it does |
|---|---|---|---|
| `mcCount` | integer ≥ 0 | **100** if `include_network` is set, otherwise **0** | surrogate pairs behind the coherence chance level. `0` skips it, and `sig95_wtc` is then `null` in the payload |
| `maxPeriod` | seconds or `null` | `null` | longest period computed. Caps `J`; the usual reason to set it is compute time |
| `scaleAvgBand` | `[min, max]` seconds | `[2Δt, min(8Δt, longest period / 2)]` | the band `scale_avg_power` averages over |
| `maxTimePoints` | integer ≥ 1 | 500 | width of the **stored picture**, in samples. The analysis always runs at full resolution |
| `maxFreqPoints` | integer ≥ 1 | 100 | height of the stored picture, in scales |
| `saveFullResolution` | boolean | `true` | also write `{video}_crosswavelet_full.json`, the grids at the resolution they were computed at |

Two notes on `mcCount`. **300 is the number to publish with**, and it is what
the schema recommends, but it is not what you get by default — the default is
100 when the network tab is enabled and 0 otherwise, because the network's
coherence mode is the only thing that reads the grid — the cross-wavelet title
reads two numbers derived from it in every study, which is why that line reports
the level as not computed rather than going quiet. And it is the expensive part of a rebuild: cost
follows pairs × recordings × scale count, not minutes of video, and 300
surrogates over a twelve-recording study is measured in hours.

### Fixed in the step

Changing any of these means editing `steps/crosswavelet.py`. They are listed
because a method section has to state them, not because they are options.

| constant | value |
|---|---|
| mother wavelet, ω₀ | Morlet, 6 |
| `dj`, `s0` | 1/12, 2Δt |
| detrending | first-order polynomial |
| taper | Tukey, α = 0.05 |
| significance level | 0.95 |
| "high coherence" for the summary statistics | 0.8 |
| AR(1) coefficient clamp | 0.01 … 0.95 |
| minimum samples | 50 |
| minimum overlap | 50 % of the longer recording |
| Monte Carlo seed | 20250906 |

The AR(1) clamp is worth knowing about when you read `alpha1` and `alpha2` in
the payload: human movement is very red, values of 0.96–0.98 are normal, and
anything above 0.95 is recorded as 0.95. The clamp exists because pycwt's red
noise generator calls a NumPy function removed in NumPy 2 when the coefficient
reaches 0, and because the estimate stops being meaningful as it approaches a
random walk.

## Four significance levels, and which one answers your question

This is the part to get right. The payload carries four different levels, all
of them arrays of plausible shape, and using the wrong one produces a picture
rather than an error.

| field | shape | tests | answers |
|---|---|---|---|
| `signif_xwt` | per scale | cross-wavelet **power** against red noise | "is there unusually much joint energy here?" |
| `global_signif` | per scale | the **time-averaged** power | "over the whole record, is this timescale unusual?" |
| `scale_avg_signif` | one scalar | the **band-averaged** power | "is the average over this band unusual?" |
| `sig95_wtc` | per scale | **coherence** against unrelated red noise | "is the timing relationship stronger than chance?" |

Where each one lives, and what it draws:

| field | in the payload | drawn as |
|---|---|---|
| `signif_xwt` | `visualization` | the heatmap's contour, the gate on the phase arrows, and the network tab's **shared power** mode |
| `global_signif` | `statistics` (and, at the stored resolution, `visualization`) | the dashed level beside the global spectrum, panel C |
| `scale_avg_signif` | `statistics` only | the flat dashed level on the band-averaged series, panel D |
| `sig95_wtc` | `visualization` | the network tab's **coherence** mode, and the cross-wavelet title's chance-level line |

**Three are computed and one is sampled.** `signif_xwt`, `global_signif` and
`scale_avg_signif` come out of Torrence & Compo's formulae for a red-noise
background: they cost nothing and are in every payload. `sig95_wtc` is a Monte
Carlo null — `mcCount` pairs of surrogate series — so it costs the time it costs
and is `null` in a study that did not ask for one. That difference is why the
network tab's shared power mode works in a study built with `mcCount: 0` while
its coherence mode cannot, and why the two report different fixes when an edge
cannot be tested.

**`signif_xwt` is not a test of coupling.** Two people moving vigorously at the
same time have joint energy whether or not their movements are related. If the
question is whether they are coordinated, the field is `sig95_wtc`.

**A level can be absent, and absent is not zero.** `sig95_wtc` is `null` when no
null was computed, and individual scales are `null` where the scale lies entirely
inside the cone of influence. `signif_xwt` can reduce to a null or non-positive
value on a scale, and `scale_avg_signif` is `0` when the band selected no scale
at all. Every reader in the dashboard drops those cells rather than treating the
level as passed or failed — a scale with no level contributes no contour, no
arrow, and no cell to a network edge's average.

Because the levels are per scale and the grids are period × time, the
comparison is one index deep:

```js
const above = coherence[j][t] > sig95_wtc[j];       // j indexes period
const strong = power[j][t] / signif_xwt[j] > 1;     // the ratio the plot contours
```

`sig95_xwt` is deliberately **not** stored. It would be `power / signif_xwt`,
and a payload that carries a quotient of two fields it already carries is a
payload with two ways to be inconsistent.

### Where the power levels come from

All three power levels are computed in `common/tc98.py` from Torrence & Compo
(1998) rather than taken from a chi-square. The cross-wavelet spectrum is the
**square root of a product of two chi-squares** (eq. 30), not a chi-square
(eq. 18), and the difference is not small: measured on this project's own
earlier code, the level came out **1.50× too high** with matched AR(1)
coefficients and **2.39× too high** at α = (0.95, 0.20). Too high, so the error
hid real structure rather than inventing it — which is why it survived so
long.

The distribution of `|W^X W^Y*|` under two independent red-noise processes is
eq. 30, and inverting it numerically gives the constants the paper publishes:

```
Z₁(95%) = 2.18195     (published 2.182)
Z₂(95%) = 3.99852     (published 3.999)
```

- **Local** (`signif_xwt`), eq. 31 with ν = 2: `Z₂/2 · √(P^X_k · P^Y_k)`, where
  `P_k` is the AR(1) background spectrum of eq. 16.
- **Time-averaged** (`global_signif`), eq. 23: the degrees of freedom grow with
  the number of independent points averaged, `N − s`, which is why the level
  falls as you average more.
- **Scale-averaged** (`scale_avg_signif`), eqs. 25–28, with eq. 30's `Z_ν` in
  place of chi-square.

### Where the coherence level comes from

For coherence no closed form is available, so the level is estimated by
simulation, following Grinsted, Moore & Jevrejeva (2004):

1. Estimate the lag-1 autocorrelation of each prepared signal.
2. Generate `mcCount` pairs of **independent** red-noise series with those
   autocorrelations.
3. Compute the coherence of each pair, and take the 95th percentile at each
   timescale.

That percentile is `sig95_wtc`. It answers one question: *how coherent would two
unrelated signals with this much redness look, here?* The generator is seeded
and the result is cached, so a rerun reproduces the same level. Scales that lie
entirely inside the cone of influence come back as `null`.

The level is not flat. It sits around 0.58–0.60 through the middle of a band and
rises at both ends — above 0.7 at the extremes — where fewer independent cycles
fit inside the record.

## The one thing to know before reading a coherence value

**Coherence does not sit at zero when there is no relationship.** It is a ratio
taken over a smoothing neighbourhood, so a handful of random phases still average
to something well above zero.

How far above is a property of your data, not a constant. Measured on the
Karnatak study, two independent signals averaged about **0.25**, and the 95 %
level came out near **0.59** — so on that data an edge of 0.27 is
indistinguishable from no coupling at all. Treat those two numbers as an
illustration of the size of the effect, not as thresholds to reuse: one is a mean
and the other a 95th percentile, and both were measured on one dataset.

The consequence is general even though the numbers are not. A value of 0.5 means
nothing on its own, and a picture of raw coherence with no baseline drawn on it is
unreadable — it will look like coupling everywhere, because it is coherent
everywhere.

Every value has to be read against `sig95_wtc`. Every one.

### What the method assumes

Five assumptions, each of which is a judgement rather than a measurement:

1. **The surrogate count.** 300 pairs is the number to publish with. Estimating
   a 95th percentile from 100 samples is noisy: with an unseeded generator,
   repeated runs on identical data disagreed by up to 0.04 on the level. Seeding
   makes it reproducible, which is not the same as accurate.
2. **AR(1) is a model.** Whether a first-order autoregressive process describes
   the signal at hand is a choice, not a fact about the data.
3. **The null is stationary; a recording is not.** One level per timescale is
   applied across a record that may contain both rest and vigorous movement.
4. **Every cell is tested at 95 %, so 5 % exceed by construction.** Treat a
   single bright cell as noise. What means something is the *fraction* of usable
   cells above the level, read against a 0.05 baseline — which is what
   `statistics.wtc_signif_fraction` is.
5. **The surrogates are independent; two measurements of the same scene may not
   be.** When both signals come from one video, their jitter has shared
   sources — camera motion, lighting, the tracker's own instability. Shared
   measurement noise produces genuine coherence, and AR(1) surrogates cannot
   tell that the correlation came from the camera rather than from the people.
   If that is a live concern, the answer is a stronger null: surrogates that
   preserve each signal's amplitude envelope and randomise only the timing.
   That has not been built.

## The cone of influence is a different thing

The cone of influence marks where a wavelet coefficient is contaminated by the
edges of the record — the transform has run off the end of the data. It is about
**which cells exist**, and applies to power and coherence alike.

Significance is about **which existing cells mean something**. Cells inside the
cone are excluded from the statistics entirely; they are not "insignificant",
they are unavailable. Conflating the two is easy because both end up drawn as
hatching or transparency.

Two practical points about the stored `coi` array:

- **The grids are not masked.** `coi` is an axis, like `time` and `period`, and
  applying it is the reader's job. The summary statistics do apply it.
- **The comparison is against `scales`, not `period`.** A cell is unusable when
  `scales[j] > coi[t]`. Since `period = 1.03 · s`, drawing `coi` straight onto a
  period axis puts the boundary 3 % out — small, and in the direction that
  flatters the result.

## Three defects worth checking older output for

All three were found in this project's own analyses, all are fixed, and any of
them can be present in output produced elsewhere by similar code.

**Discarding phase before it can cancel.** Smoothing the *magnitude* of the
cross-spectrum instead of the complex value removes the timing before it can
cancel, so nothing ever cancels. The symptom is unmistakable once looked for: a
large share of cells sitting at exactly 1.0 — in the case that prompted this,
56.7 % of them — and coherence correlating with signal power at +0.87.
Corrected, the same recording had no cells at 1.0 and a power correlation of
−0.02.

**Reporting silence as perfect coupling.** Where neither signal moves, the
calculation divides almost-nothing by almost-nothing and the result is
numerically capped at the maximum. Cells with no meaningful energy in either
signal must be left blank, not capped.

**No baseline at all.** Without `sig95_wtc` there is nothing to read a value
against, and every edge looks strong.

A quick check on any existing output: the share of cells at exactly 1.0, and the
correlation between coherence and log power. Both should be near zero.
`dims_checks.coherence` in the notebooks package runs exactly these.

## Reading a result

- Compare `statistics.wtc_signif_fraction` with **0.05**, not with zero.
- **"Not detectable" is not "absent".** A null result is a statement about one
  recording, over one band of timescales, against one kind of null.
- Analyse `_full.json`, not the reduced payload. That one is reduced in time and
  rounded to six significant figures; it is a picture, not the analysis.
- A within-person pair scoring far above chance while between-person pairs sit
  at chance is the expected shape of a healthy analysis, not a disappointment.
  One body is one motor system, and it is the strongest coupling most recordings
  contain.

### Two more views the payload gives you for free

<div class="figure" id="fig-xwt-global"></div>

<div class="figure" id="fig-xwt-scaleavg"></div>

## What it writes

One entry per pair under `crosswavelet_pairs`, keyed `"{type1}_vs_{type2}"`:

```jsonc
{
  "video_id": "demo",
  "payload_version": 2,
  "crosswavelet_pairs": {
    "sig_a_vs_sig_b": {
      "data_type1": "sig_a", "data_type2": "sig_b",
      "dt": 0.1, "n_samples": 599, "time_range": [0.0, 59.9],
      "mother_wavelet": "morlet", "omega0": 6,
      "dj": 0.0833333, "s0": 0.2, "J": 79.0,
      "alpha1": 0.944406, "alpha2": 0.95,
      "scale_avg_band": [0.2, 0.8],
      "statistics": { "…": "summary numbers, below" },
      "metadata":   { "…": "the preparation settings used" },
      "visualization": { "…": "the grids, below" }
    }
  },
  "data_types": ["sig_a", "sig_b"],
  "config": { "…": "the step's fixed constants" },
  "provenance": { "core_version": "1.4.3", "mc_count": 200,
                  "significance_level": 0.95, "wct_signif_seed": 20250906,
                  "max_time_points": 150, "max_freq_points": 48 },
  "processing_info": { "…": "" },
  "precision": { "significant_figures": 6 }
}
```

### `visualization` — the grids

`P` is the number of periods and `T` the number of time points after reduction.
Every 2-D field is **period × time**, in that order.

| field | encoding | shape | units |
|---|---|---|---|
| `time` | JSON list | `T` | seconds |
| `period` | JSON list | `P` | seconds |
| `scales` | JSON list | `P` | wavelet scale, seconds |
| `freqs` | JSON list | `P` | Hz |
| `power` | `f32-b64` | `P × T` | \|W^XY\|, normalised-signal² |
| `phase` | `f32-b64` | `P × T` | radians, (−π, π] |
| `coherence` | `f32-b64` | `P × T` | 0…1, `null` where undefined |
| `coi` | JSON list | `T` | period, seconds — compare against `scales` |
| `signif_xwt` | JSON list | `P` | same units as `power` |
| `sig95_wtc` | JSON list or `null` | `P` | coherence units; `null` when `mcCount` is 0 |
| `global_power`, `global_signif` | JSON list | `P` | time-averaged power and its level |
| `scale_avg_power` | JSON list | `T` | band-averaged power per time point |
| `downsampling_factors` | object | — | `{time_factor, freq_factor}` |

### `statistics` — the summary numbers

`wtc_signif_fraction` is the one to read: the share of finite, outside-the-cone
cells whose coherence exceeds `sig95_wtc`, against a 0.05 baseline. Also here:
`max_coherence`, `mean_coherence`, `high_coherence_fraction` (share above 0.8),
`mean_phase_by_freq` (a **circular** mean, `arg(mean(e^{iφ}))`, because the
arithmetic mean of two angles either side of ±π is meaningless),
`scale_avg_power_mean` and `scale_avg_signif`.

### Two things in the payload that are less informative than they look

`processing_info.visualization_resolution` and the top-level `config` block
report the step's **module constants**, not what this study asked for. The
settings actually used are in `provenance`. If you want to know the grid this
payload was reduced to, read `provenance.max_time_points` — or the shape of
`visualization.power`, which cannot be wrong.

## References

- Torrence, C., & Compo, G. P. (1998). A practical guide to wavelet analysis.
  *Bulletin of the American Meteorological Society*, **79**(1), 61–78.
  [doi:10.1175/1520-0477(1998)079<0061:APGTWA>2.0.CO;2](<https://doi.org/10.1175/1520-0477(1998)079%3C0061:APGTWA%3E2.0.CO;2>)
  — the source of the scale layout, the AR(1) background spectrum, and all three
  power significance levels used here. The authors' companion page, with the
  original code and the worked NIÑO3 example, is at
  <https://atoc.colorado.edu/research/wavelets/>. The constants transcribed from
  it are in [`examples/reference/TORRENCE_COMPO.md`](../../examples/reference/TORRENCE_COMPO.md).
- Torrence, C., & Webster, P. J. (1999). Interdecadal changes in the ENSO monsoon
  system. *Journal of Climate*, **12**(8), 2679–2690. — the smoothed coherence
  formula.
- Grinsted, A., Moore, J. C., & Jevrejeva, S. (2004). Application of the cross
  wavelet transform and wavelet coherence to geophysical time series.
  *Nonlinear Processes in Geophysics*, **11**, 561–566.
  [doi:10.5194/npg-11-561-2004](https://doi.org/10.5194/npg-11-561-2004)
  — the Monte Carlo coherence null.
