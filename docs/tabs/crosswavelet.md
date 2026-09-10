# The cross-wavelet tab

For each pair you asked for, a four-panel figure in the style of the pycwt
reference plots: the two signals, the cross-wavelet power spectrum with phase
arrows and the cone of influence, the global spectrum beside it, and the
scale-averaged power beneath.

This page is about what the tab draws. What the transform computes, what the four
different significance levels mean, and how to avoid over-reading any of it is on
[the analysis page](../analyses/crosswavelet.md) — read that one before trusting
a figure here.

- Tab id `crosswavelet`, label **Cross-Wavelet**, order 30.
- Draws into `crossWaveletContainer`, named explicitly rather than derived, because
  other code and tests already used the id.
- Reads `assets/crosswavelet/{videoID}_crosswavelet_data.json`, container key
  `crosswavelet_pairs`.

## The gate reads both config dialects

```js
Array.isArray(v) && v.length > 0 && (Array.isArray(v[0]) || v.length >= 2)
```

`include_crosswavelet` can be written two ways, and they need different tests:

- **Explicit pairs** — `[["a","b"]]` — is valid with a single entry.
- **A legacy flat list** — `["a","b","c"]` — needs at least two names before a
  pair exists at all, and the analysis expands it into every combination.

So `["a"]` switches the tab off, and `[["a","b"]]` switches it on. This is the one
place where the flat form is genuinely supported; `include_cRQA` looks similar and
is **not** expanded the same way — see [the cross-RQA tab](crqa.md).

## The four panels

Pairs are laid out in a grid of at least 600 px columns, one figure per pair,
each 800 px tall.

| panel | axes | what it shows |
|---|---|---|
| **A** top | `x4`/`y4` | the two raw signals, normalised, in their colours from the time series tab |
| **B** middle-left | `x`/`y` | cross-wavelet power as a Viridis heatmap, with the significance contour, phase arrows and the cone of influence over it |
| **C** middle-right | `x2`/`y2` | the global (time-averaged) cross-wavelet spectrum, with its 95 % level dashed beside it |
| **D** bottom | `x3`/`y3` | scale-averaged power over time, with its 95 % level as a flat dashed line |

**The period axis is log₂.** Ticks are placed at whole powers of two and labelled
with the period in seconds, so the spacing between 1 s and 2 s is the same as
between 8 s and 16 s. Hovering reports the real period, not its logarithm.

Panels A, B and D share the time axis. **Panel C does not have one** — it is a
spectrum, with period on y and power on x — which is why the playhead window is
not drawn on it.

### The significance contour

The payload stores the 95 % level once per scale, and the power once per cell. The
tab divides one by the other and contours that ratio.

**Read the contour as approximate, not as a threshold.** The contour levels are
0.95 and 1.45, not 1 — so the outer line sits slightly *inside* the 95 % level, and
a cell just within it has not quite reached significance. The exact `> 1` test does
exist, but it is what gates the phase arrows, not what draws this line.

A scale whose level is missing or non-positive contributes no contour rather than a
spurious one.

### Phase arrows — read the caveat

Roughly 20 arrows across time by 12 down the period axis, drawn only where the
ratio above exceeds 1. Each is one of eight Unicode arrows binned from the phase
angle in 45° steps, and the figure's own subtitle carries the full legend:

- **→** in phase · **←** anti-phase
- **↑** the first measure leads by 90° · **↓** the second leads by 90°
- the diagonals are the 45° and 135° cases in between.

Hovering an arrow gives the exact time, period, phase in degrees, and power.

**The arrows sit where *power* is significant, not where coherence is.** They are
gated on `power / signif_xwt > 1` — the cross-wavelet significance level, which
asks whether there was more joint energy here than red noise would give. That is a
statement about power. It is **not** a test of whether the timing relationship was
consistent, and nothing in the arrow test looks at the coherence value at all. A
cell can carry a confident-looking arrow and have poor coherence. This is the
single easiest way to over-read the figure; the analysis page spells out the
difference at length.

Cells where either the phase or the coherence is null are skipped, so an arrow is
never drawn from a missing value.

### The cone of influence

Shaded at 8 % black, with a dashed boundary line. Inside it the transform is
contaminated by the edges of the record and the values should not be read. The
boundary is clamped to the shortest period in the payload, so it never dips below
the plotted range.

## The title tells you whether coherence can be tested at all

Above every figure: mean and maximum coherence, the two AR(1) coefficients α₁ and
α₂, and then one line that is worth reading every time.

- When a Monte Carlo null was run — **"Coherence above chance (outside the cone):
  X% of cells (N surrogates, median level M)"**. Under independence that percentage
  sits near 5 %; well above it is the finding. The surrogate count degrades to the
  words "a Monte Carlo null" when the payload does not record one, and the
  "median level" clause is dropped when that statistic is absent.
- When it was not — **"Coherence chance level: not computed for this output. Set
  `analysis.crosswavelet.mcCount` in config.json and rebuild."**

The second is the default for a study that does not switch on the network tab,
because the null is expensive and nothing else reads it. It is not an error. But
**a coherence value without it cannot be interpreted**: coherence does not sit at
zero when there is no relationship. Measured on one of the project's own studies,
independent signals averaged about 0.25 and the 95 % level came out near 0.59 — so
a raw value of 0.5 is not evidence of anything. Those numbers are one measurement
on one dataset, not constants; the point they make is that the comparison has to be
made, which is why the tab says in the title when it could not be.

## The playhead

Clicking panel A, B or D seeks to that time. **Panel C does not seek** — its
x-axis is power, so there is no time on it to go to.

Until v1.4.2 it did: the handler took `point.x` from whichever panel was clicked,
so clicking the spectrum moved the whole dashboard to a power value read as
seconds.

The window is drawn as two vertical edge lines plus a translucent band spanning
`playhead ± windowSize / 2`, clamped to the pair's own time range. It appears on
panels A, B and D, and not on C.

**Moving the playhead does not redraw the figure.** The tab recomputes only the
shapes and hands them to Plotly's `relayout`, leaving the heatmap in place. This
is why scrubbing the slider is smooth here and not on the recurrence tabs, which
rebuild their whole figure on every move.

That split is also what the [cross-effector network](network.md) depends on: when
you select an edge, the network draws this same pair figure in its detail panel
and then moves its window as the playhead moves, without ever redrawing it.

## When it cannot draw

- **No payload** — `include_crosswavelet` is set, so the analysis was expected; the
  message names `python build_assets.py`.
- **A payload from an older format** — refused by the host's version check.
- **A pair missing `visualization.time`, `.power` or `.period`** — that pair's cell
  shows the error and the rest of the grid still draws.
- **`coherence` absent** — the figure still draws and the arrows lose their
  coherence null-check. It does **not** change the title: the chance-level line
  reads `statistics.wtc_signif_fraction`, an independent field, and a payload can
  carry either one without the other.

## Where it lives

[`packages/dims-tabs/crosswavelet.js`](../../packages/dims-tabs/crosswavelet.js).
It adds `loadCrossWaveletData`, `displayCrossWaveletPlots`, `chanceLevelNote`,
`createCrossWaveletPlot`, `crossWaveletWindowShapes`, `updateCrossWaveletWindow`
and `updateCrossWaveletHighlights` to the host.

`createCrossWaveletPlot` and `updateCrossWaveletWindow` are the public seam **the
network tab reuses** to draw and then move its detail figure; treat those two as
part of this tab's interface rather than as private.
