# The ELAN tab

Your own annotation tiers, drawn on the same timeline as the signals. This is the
tab that connects hand coding to everything else: click an annotation and the
video, the transcript and every analysis tab move to it.

- Tab id `elan`, label **ELAN Annotations**, order 50, drawn into `elanContainer`.
- Gate: `!!cfg.include_elan` — any truthy value switches it on.
- Reads `assets/elan/{videoID}.eaf` directly, with `fetch` and the browser's own
  XML parser. It is the only tab that reads an input file rather than an analysis
  payload, and the only one whose data no analysis step produces.

## What it reads out of the `.eaf`

Three element types, and nothing else:

| element | what is taken |
|---|---|
| `TIME_SLOT` | `TIME_SLOT_ID` and `TIME_VALUE`. **Values are milliseconds in the file and are divided by 1000**, so the tab works in seconds like every other tab |
| `TIER` | `TIER_ID`, used as the tier's name and its identity everywhere else |
| `ALIGNABLE_ANNOTATION` | `TIME_SLOT_REF1` and `TIME_SLOT_REF2` for the extent, and the text of `ANNOTATION_VALUE` |

**Only `ALIGNABLE_ANNOTATION` is read.** ELAN's other annotation type,
`REF_ANNOTATION` — the one used by every *dependent* tier, where an annotation
hangs off a parent annotation instead of naming its own time slots — is ignored
completely. If your coding scheme puts the interesting labels on dependent tiers,
those tiers will be missing from this tab and nothing will say so.

Two more silent drops, both by the same rule of "if it has no extent, it is not
drawn":

- An annotation whose `TIME_SLOT_REF1` or `TIME_SLOT_REF2` names a slot that is
  not in the file is skipped.
- A tier left with no annotations after that is dropped from the tier list
  entirely, rather than shown empty.

If *no* tier survives, the tab reports **"Failed to load ELAN data: No alignable
annotations found in EAF file."** rather than drawing an empty timeline. On a file
full of dependent tiers that is the message you will get, and the cause is the
paragraph above — not a missing or unreadable file, which is what the wording
suggests.

## What it draws

One horizontal lane per tier, labelled down the left. Each annotation is a filled
block spanning its own start and end, drawn at two-thirds opacity with a solid
border in the same colour.

Colours come from a fixed 20-entry palette, cycled if you have more than 20 tiers.
The index used is the tier's position in the **original** file order, not its
position among the tiers currently shown — so hiding a tier does not recolour the
ones left behind.

The left margin sizes itself to the longest visible tier name, at roughly 7 px per
character, clamped between 120 px and 220 px. Names longer than that are cut off
by the margin rather than shrinking the plot.

Hovering an annotation gives its tier, its text (or `(empty)` when the
`ANNOTATION_VALUE` is blank), its start and end to two decimals, and its duration.
The hover targets are invisible square markers at each annotation's midpoint, so
**hover is keyed to the middle of a block, not anywhere along it** — on a long
annotation you have to aim at the centre.

### Choosing tiers

Above the plot is one checkbox per tier, plus **all** and **none**. The selection
is held on the host as `app.elanSelectedTiers`.

- **Switching tab keeps it.**
- **Switching recording clears it**, because tier names belong to the recording and
  need not carry over.
- **Switching theme keeps it.** A theme change re-renders everything, which means
  re-entering the data load for the same recording — and that used to clear the
  selection on its way past, until v1.4.2. It now clears only when the recording
  actually changes.

Deselecting every tier collapses the plot to zero height: the y-axis range
becomes `[0, 0]` and the playhead's band and line are drawn with no height to
occupy, so they disappear too. You get an empty frame rather than an empty
timeline with a playhead on it.

## The playhead

Clicking seeks to that time — but the only clickable things are the invisible
midpoint markers, so **you must click at or near an annotation's centre**, the same
aiming constraint as hovering. Clicking empty timeline does nothing.

When a time is selected the tab draws two things across every lane: a translucent
band spanning `playhead ± windowSize / 2`, and a dotted vertical line at the
playhead itself. Window size is read live from the **Window Size** control,
defaulting to 5 seconds.

`onTimeUpdate` redraws the whole plot rather than moving the shapes. With many
annotations this is the more expensive of the two strategies the tabs use — the
cross-wavelet tab moves shapes instead — but it keeps the tier filter and the
highlight in one code path.

## The time axis

The x-axis spans **the recording**, from 0 to the last sample in any loaded
series — the same extent the time slider uses — so the lanes line up with every
other tab and an unannotated head or tail of the recording is visible as empty
space rather than cropped away.

Until v1.4.2 it did not. The tab asked the host for a field the host has never
set, so the request always failed and Plotly autoscaled to the annotated span:
annotations sat at their true times, but a file whose first annotation began at
40 s drew a timeline starting near 40 s.

## Where it lives

[`packages/dims-tabs/elan.js`](../../packages/dims-tabs/elan.js). It adds
`loadELANData`, `displayELANTab`, `_renderELANPlot` and `updateELANHighlight` to
the host via `DIMS.extendHost`.
