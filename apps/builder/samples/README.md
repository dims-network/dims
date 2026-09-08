# Sample datasets — two sessions (`session1`, `session2`)

Mock files for testing the builder end-to-end. All validate cleanly against the
builder's rules.

## `session1` — one signal per CSV (the classic layout)

| File | Role | Notes |
|------|------|-------|
| `session1.mp4` | video | Real 10 s H.264 clip (plays in any browser, supports seeking) |
| `session1_bodysync.csv` | timeseries | `Time` + `value`, 0–10 s @ 50 Hz, data type `bodysync` |
| `session1_neuralsync.csv` | timeseries | same span, data type `neuralsync` (phase-coupled to bodysync) |
| `session1_transcript.json` | transcript | `{ segments: [{start,end,speaker,text}] }` |
| `session1.eaf` | ELAN | tier `phases` with a few annotations |

## `session2` — one multi-column CSV (exercises auto-split)

`session2.csv` packs **three** value columns into a single file. On upload the
builder automatically splits it into one CSV per column — data types `bodysync`,
`neuralsync`, and `gaze` — all under session ID **`session2`**.

| File | Role | Notes |
|------|------|-------|
| `session2.mp4` | video | 8 s H.264 clip (different length/visual from session1) |
| `session2.csv` | timeseries | `Time` + `bodysync` + `neuralsync` + `gaze`, 0–8 s @ 50 Hz — **auto-splits into 3 data types** |
| `session2_transcript.json` | transcript | `{ segments: [{start,end,speaker,text}] }` |
| `session2.eaf` | ELAN | tier `phases` with a few annotations |

The three signals tell a coupling story: `bodysync` and `neuralsync` drift apart
early then phase-lock around 4 s, while `gaze` keeps its own slower rhythm —
ideal for trying **pairwise** cross-wavelet / cross-RQA (e.g. compute
`bodysync × neuralsync` and `neuralsync × gaze` but skip `bodysync × gaze`).

## How to use them

Press **Load the example study** in step 2 of the wizard. That stages every file
here through the same path an upload takes — including the split of
`session2.csv` into three measures — so what you get is what a real drag-and-drop
produces.

Then: step 4, switch on what you like; **Build → Compute → Open it**. Measured
end to end with recurrence, cross-recurrence, cross-wavelet (20 surrogates) and
the network switched on: the analyses take about a minute, and every tab draws.

> These signals are synthetic (phase-coupled sinusoids + noise), chosen so the
> analyses are non-trivial — not real recordings.
