# The cross-RQA tab

The same figure as [the RQA tab](rqa.md), for a pair of measures instead of one.
Where RQA asks when a measure returned to a state it had been in before, this asks
when one measure was in a state the *other* had been in — and how long afterwards.
What the numbers mean is on [the analysis page](../analyses/crqa.md).

- Tab id `crqa`, label **Cross-RQA**, order 40, drawn into `crqaContainer`.
- Gate: `include_cRQA` must be an array with at least one entry.
- Reads `assets/crqa/{videoID}_crqa_data.json`, container key `crqa_data`, one
  entry per pair, keyed `{type1}_vs_{type2}`.

Everything about the figure — the four metric strips, the true-square geometry,
the four highlight shapes, the click-to-seek rule, the full redraw on every
playhead move — is identical to the RQA tab, because both call the same host
method. **Read that page for the figure; this one covers only the differences.**

## The three differences

**1. Two measures, two colours.** The top marginal is the first series of the
pair, the rotated left marginal is the second — so the square's x-axis is the
first measure's time and its y-axis is the second's. The axes are labelled that
way. Each series takes its colour from the time series tab where it can be matched
by name, and otherwise falls back to a fixed red for the first and blue for the
second.

**2. The diagonal means something.** In a plain recurrence plot the leading
diagonal is trivially black — every point matches itself — and the analysis
excludes it. Here the two axes are different measures, so a black diagonal is a
finding: the two were in the same state at the same time. A black band *parallel*
to the diagonal, offset by some distance, says one led the other by that many
seconds.

**3. A heading per pair.** Above each figure: the two series names joined by a
double arrow, then the pair's global recurrence rate as a percentage and its
threshold. The figure below it repeats all of that in its own title — see the
faults below.

## What it does not do

- **It does not expand a flat list.** `include_cRQA` must be a list of
  `[type1, type2]` pairs. Unlike `include_crosswavelet`, a flat list of measure
  names is *not* expanded into all their combinations: each name is skipped as an
  invalid entry, the analysis writes no payload, and the config schema shares one
  definition between the two keys so it will not catch it for you.

  **The tab still appears**, because its gate only asks that `include_cRQA` is a
  non-empty array — which a flat list is. So you get the tab, and inside it the
  message *"No cross-RQA output for this recording… run `python build_assets.py`"*,
  which names the wrong cause: rebuilding will not help until the config is
  written as pairs. The real signal is in the build output, one
  `Warning: Skipping invalid include_cRQA entry: … Expected [type1, type2].` line
  per name. See [the analysis page](../analyses/crqa.md).
- **It does not name the pair whose payload is broken on the page.** A pair
  missing `visualization.time`, `.matrix_size`, `.matrix`, `.data_x` or `.data_y`
  shows an error in its own block; the pair key goes to the browser console.

## Reading a lag off this tab

The band's **offset from the diagonal is the lag**, and its **side tells you which
measure led**. Both axes are time, x is the first-named series and y the second, so
a band above the diagonal means the second series repeated the first's states later.

That direction was wrong until v1.4.2. The analysis writes the matrix with its rows
indexing the first series, and Plotly draws rows on y — so the figure was the
transpose of what its own labels claimed, and the side a lag fell on named the
wrong measure. The tab now transposes on read, which changes nothing in any stored
payload: a study built before the fix renders correctly without being rebuilt.

If you took a lead/lag reading from this tab before v1.4.2, reverse it.

## Where it lives

[`packages/dims-tabs/crqa.js`](../../packages/dims-tabs/crqa.js), which adds
`loadCRQAData`, `displayCRQAPlots`, `createCRQAPlot` and `updateCRQAHighlights` to
the host.
