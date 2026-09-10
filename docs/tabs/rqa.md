# The RQA tab

One recurrence plot per measure, with the windowed metrics beneath it and the
playhead across both. This page is about what the tab *draws*; what the numbers
mean and how they were computed is on [the analysis page](../analyses/rqa.md).

- Tab id `rqa`, label **RQA Plots**, order 20, drawn into `rqaContainer`.
- Gate: `include_RQA` must be an array with at least one entry. A bare `true`
  does **not** switch this tab on.
- Reads `assets/rqa/{videoID}_rqa_data.json`, container key `rqa_data`, one entry
  per data type.

## What you see per measure

One block per key in `rqa_data`, each a single figure with four parts sharing one
time axis:

| part | what it is |
|---|---|
| **the square** | the recurrence matrix — a black cell wherever the measure was in a state it had been in before, white elsewhere. Both axes are time |
| **top strip** | the raw measure, in its colour from the time series tab |
| **left strip** | the same measure again, rotated, so a horizontal band on the square lines up with the value that produced it |
| **four strips below** | the windowed metrics, top to bottom: **RR**, **DET**, **LAM**, **L_MAX**. L_MAX is in seconds; the other three are unitless fractions |

The heading above each square carries that measure's achieved recurrence rate as a
percentage and the threshold that produced it, both to fixed precision.

The metric strips are tied to the square's x-axis, so the four of them and the top
marginal are always aligned with the recurrence plot — you can read a spike in DET
straight down onto the structure that caused it.

**The square really is square.** The figure computes its own pixel geometry rather
than letting Plotly stretch it: the plotting width is 85 % of the space available
after margins, floored at 300 px, and the square itself is 80 % of that again. The
total height is derived from the result. A stretched recurrence plot misrepresents
diagonal structure, which is the thing the measures are counting.

The cost is that the figure is drawn at an explicit pixel size and **does not
reflow**. Because the width and height are both fixed in the layout, the host's
resize pass cannot recompute it either — the figure only takes a new size when
something redraws it outright, which means a playhead move, a theme change or a
recording change. Resizing the window alone leaves it as it was.

## The playhead

Clicking any subplot except the rotated left strip seeks to that time. The left
strip is excluded because its x-axis is value, not time — a click there has no
time to seek to.

A selected time draws four shapes, which is more than the other tabs because a
recurrence plot is symmetric in time:

- a vertical band across the square, the top strip and every metric strip,
- a line at the playhead itself,
- a horizontal band across the square, at the same times,
- a matching horizontal band on the left strip.

The band is `playhead ± windowSize / 2`, clamped at both ends to the first and
last time in the **drawn** series, so it never runs off the edge of the plot.
Window size comes from the **Window Size** control, defaulting to 5 seconds.

`onTimeUpdate` **re-renders every figure from scratch**, decoding the matrix again
each time. With several measures this is the most expensive redraw in the
dashboard. It is why the tab feels slower to scrub than the cross-wavelet tab,
which moves shapes instead.

## What it does not do

- **It does not compute anything.** Everything drawn is read from the payload. If
  a measure is listed in `include_RQA` but absent from the payload, the tab logs
  the mismatch to the browser console and draws the rest — it does not warn you on
  the page.
- **It does not draw the full-resolution matrix.** The payload ships a matrix
  reduced to at most 500 × 500 cells, by a density-preserving reduction — so the
  picture keeps both its structure and its recurrence density.
  **The percentage in the heading is the full matrix's rate, not the drawn one's.**
  The drawn matrix's own rate is computed and stored as
  `visualization.reduction.rate_drawn`, and is never displayed; it is close but not
  identical, and it is measured a slightly different way — it includes the line of
  identity, which the headline rate excludes. Do not read the heading as a
  description of the pixels. See [the analysis page](../analyses/rqa.md).
- **It has no controls of its own.** Everything it responds to — the recording,
  the playhead, the window — belongs to the page, not the tab.

## When it cannot draw

The ones you are most likely to meet, each naming its own fix:

- **No payload at all** — `include_RQA` is set, so the analysis was expected. The
  message tells you to run `python build_assets.py` in the study folder.
- **A payload from an older format** — the host's version check refuses it and
  says so, rather than drawing something subtly wrong. See
  [`contracts/analysis-output.md`](../contracts/analysis-output.md).
- **A payload missing `visualization.time`, `.data`, `.matrix_size` or
  `.matrix`** — that one measure's block shows the error and the others still
  draw.
- **A payload whose `rqa_data` is empty** — reported as empty or invalid, with the
  structure logged to the browser console.

## Where it lives

[`packages/dims-tabs/rqa.js`](../../packages/dims-tabs/rqa.js), which adds
`loadRQAData`, `displayRQAPlots`, `createRQAPlot` and `updateRQAHighlights` to the
host. The figure itself is built by `_renderRecurrenceFigure`, which lives on the
host and is shared with [the cross-RQA tab](crqa.md).
