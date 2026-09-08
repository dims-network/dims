# Wavelet coherence, and reading it honestly

Coherence asks whether two signals *keep a consistent timing relationship*,
timescale by timescale, moment by moment. It is not correlation and it is not
shared energy: two signals can both be large and score nothing, and two quiet
signals can score highly.

This page is the method and its traps. What each stored field means is in
[asset layout](contracts/assets.md); what the tab draws is in the study that
uses it.

## The one thing to know first

**Coherence does not sit at zero when there is no relationship.** Two unrelated
red-noise signals typically score around 0.25–0.6 depending on the timescale.
So a value of 0.5 means nothing on its own, and a picture of raw coherence with
no baseline drawn on it is unreadable — it will look like coupling everywhere,
because it is coherent everywhere.

Every value has to be read against a null. That is what `sig95_wtc` is for.

## The null, and how it is obtained

For wavelet **power** there is an analytic significance level (Torrence & Compo
1998, eq. 31), stored per scale as `signif_xwt`. For **coherence** no closed
form is available, so
the level is estimated by simulation, following Grinsted, Moore & Jevrejeva
(2004):

1. Estimate the lag-1 autocorrelation of each prepared signal. Human movement
   is very red — values around 0.96–0.98, close to a random walk, are normal.
2. Generate many pairs of **independent** red-noise series with those
   autocorrelations.
3. Compute the coherence of each pair, and take the 95th percentile at each
   timescale.

That percentile is `sig95_wtc`. It answers one question: *how coherent would
two unrelated signals with this much redness look, here?* The generator is
seeded and the result is cached, so a rerun reproduces the same level.

The level is not flat. It sits around 0.58–0.60 through the middle of a band
and rises at both ends — above 0.7 at the extremes — where fewer independent
cycles fit inside the record.

### `sig95_wtc` and `signif_xwt` are not interchangeable

This is the trap that has caught this project once already, and it does not
announce itself: both are arrays of the right shape, so using the wrong one
produces a plausible picture rather than an error.

| field | tests | answers |
|---|---|---|
| `signif_xwt` | cross-wavelet **power** against red noise | "is there unusually much joint energy here?" |
| `sig95_wtc` | **coherence** against unrelated red noise | "is the timing relationship stronger than chance?" |

`signif_xwt` is not a test of coupling. Two people moving vigorously at the same
time have joint energy whether or not their movements are related.

### What the method assumes

Five assumptions, each of which is a judgement rather than a measurement:

1. **The surrogate count.** 300 pairs is the default and the number to publish
   with. Estimating a 95th percentile from 100 samples is noisy: with an
   unseeded generator, repeated runs on identical data disagreed by up to 0.04
   on the level. Seeding makes it reproducible, which is not the same as
   accurate.
2. **AR(1) is a model.** Whether a first-order autoregressive process describes
   the signal at hand is a choice, not a fact about the data.
3. **The null is stationary; a recording is not.** One level per timescale is
   applied across a record that may contain both rest and vigorous movement.
4. **Every cell is tested at 95%, so 5% exceed by construction.** Treat a
   single bright cell as noise. What means something is the *fraction* of
   usable cells above the level, read against a 0.05 baseline.
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
edges of the record — the transform has run off the end of the data. It is
about **which cells exist**, and applies to power and coherence alike.

Significance is about **which existing cells mean something**. Cells inside the
cone are excluded from statistics entirely; they are not "insignificant", they
are unavailable. Conflating the two is easy because both end up drawn as
hatching or transparency.

## Three defects worth checking older output for

All three were found in this project's own analyses, all are fixed, and any of
them can be present in output produced elsewhere by similar code.

**Discarding phase before it can cancel.** Coherence works by letting
mismatched timing cancel out during smoothing. Smoothing the *magnitude* of the
cross-spectrum instead of the complex value removes the timing before it can
cancel, so nothing ever cancels. The symptom is unmistakable once looked for:
a large share of cells sitting at exactly 1.0 — in the case that prompted this,
56.7% of them — and coherence correlating with signal power at +0.87. Corrected,
the same recording had no cells at 1.0 and a power correlation of −0.02.

**Reporting silence as perfect coupling.** Where neither signal moves, the
calculation divides almost-nothing by almost-nothing, and the result is
numerically capped at the maximum. Stillness is then drawn as perfect synchrony.
Cells with no meaningful energy in either signal must be left blank, not capped.

**No baseline at all.** Without `sig95_wtc` there is nothing to read a value
against, and every edge looks strong — see the first section of this page.

A quick check on any existing output: the share of cells at exactly 1.0, and
the correlation between coherence and log power. Both should be near zero.

## Reading a result

- Compare the fraction of above-chance cells with **0.05**, not with zero.
- **"Not detectable" is not "absent".** A null result is a statement about one
  recording, over one band of timescales, against one kind of null.
- Analyse `_full.json`, not the reduced payload. That one is reduced in time and rounded to
  six significant figures; it is a picture, not the analysis.
- A within-person pair scoring far above chance while between-person pairs sit
  at chance is the expected shape of a healthy analysis, not a disappointment.
  One body is one motor system, and it is the strongest coupling most recordings
  contain.

## References

- Torrence, C., & Compo, G. P. (1998). A practical guide to wavelet analysis.
  *Bulletin of the American Meteorological Society*, 79(1), 61–78.
- Torrence, C., & Webster, P. J. (1999). Interdecadal changes in the ENSO
  monsoon system. *Journal of Climate*, 12(8), 2679–2690.
- Grinsted, A., Moore, J. C., & Jevrejeva, S. (2004). Application of the cross
  wavelet transform and wavelet coherence to geophysical time series.
  *Nonlinear Processes in Geophysics*, 11, 561–566.
