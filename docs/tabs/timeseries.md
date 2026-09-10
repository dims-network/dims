# The time series tab

Every measure plotted against time, one strip each, with the playhead on all of
them. This is the base view: it is the only tab whose gate is unconditional, so
a dashboard always has at least this one.

- Tab id `timeseries`, label **Time series**, order 10.
- Gate: `() => true`. It cannot be switched off.
- Draws into `plotContainer`. It is one of two tabs that name their pane
  explicitly instead of taking the derived `{id}Container` — the cross-wavelet tab
  is the other — because the id predates the tab registry and other code and tests
  still use it.
- Reads no analysis output. It plots `app.currentData`, the CSVs the host has
  already loaded from `assets/timeseries/{videoID}_{dataType}.csv`.

## What it draws

One subplot per loaded data type, stacked, sharing a single **Time (s)** axis at
the bottom. Each strip carries the measure's name as a label in its top-left
corner rather than a legend — the legend is off, because with one trace per strip
it would repeat what the label already says.

Trace colour is `hsl(i × 360 / n, 70%, 50%)`, where `i` is the measure's position
in the loaded set and `n` is how many there are. **The RQA and cross-RQA tabs
reuse this formula** so that a measure keeps its colour across tabs; they look the
index up by name and fall back to a fixed colour when they cannot find it.

The figure is a fixed 800 px tall regardless of how many measures there are, so
with many measures each strip gets thin.

The figure's title defaults to your study's `title` followed by the recording id.
Set **`timeseriesTitle`** in `config.json` to override it; `{videoID}` is
substituted:

```json
{ "timeseriesTitle": "Ground reaction force — {videoID}" }
```

It used to read "ROI Synchrony Over Time for Video `{videoID}`" for every study,
a leftover from the fNIRS work the tab was first written for.

### A multi-column CSV becomes one averaged trace

Every column except `Time` is a value column. If a CSV has more than one, the tab
does not draw them separately — it averages them per row and draws a single trace
named `{dataType} (averaged)`.

Two things follow from how that average is taken:

- **Missing values are dropped from the average, not carried.** A row with three
  columns of which one is null averages the other two.
- **A row where every value is missing becomes `0`, not a gap.** That is a real
  zero on the plot, indistinguishable from a measured zero. If your CSV has
  all-empty rows, split the columns into separate files rather than relying on
  this.

A CSV with only a `Time` column produces no trace at all, silently. It still
takes a strip and still gets a label.

## The playhead

Clicking **a point on a trace** calls the host's `handleTimeClick` with that
point's time, which moves the video, the transcript and every other tab. It is a
Plotly point-click, so clicking empty space inside a strip does nothing — aim at
the line.

When a time is selected, each strip gets a highlight rectangle spanning
`selectedTime ± windowSize / 2`, clamped at 0 on the left. The width comes from
the **Window Size** control, read live from the page and defaulting to 5 seconds
when it cannot be parsed.

This tab has **no `onTimeUpdate` hook**, unlike every other tab. It does not need
one: `handleTimeClick` calls `plotTimeseries` directly — it is the first thing
that redraws, and it happens before the time bus runs at all. The tab is redrawn by the host rather than by a
subscription.

Its `onActivate` re-fires `handleTimeClick(app.lastClickedPoint)` when a playhead
is already set, so switching back to the tab restores the highlight instead of
showing an unmarked plot.

## What it does not do

- **No y-axis titles.** Each strip's y-axis is unlabelled; the measure name is
  the corner annotation. Units are whatever your CSV was in, and nothing states
  them.
- **No resampling, smoothing or normalisation.** What is in the CSV is what is
  drawn — except for the multi-column averaging above. Points are sorted by
  `Time` before plotting, so an out-of-order CSV draws correctly rather than
  wrapping back on itself.
- **No per-measure scaling.** Each strip autoscales independently, so two strips
  side by side are not comparable by eye without reading the axes.

## Where it lives

[`packages/dims-tabs/timeseries.js`](../../packages/dims-tabs/timeseries.js).
It adds one method to the host, `plotTimeseries(datasets, selectedTime)`, via
`DIMS.extendHost` — which is what lets `handleTimeClick` call it by name.
