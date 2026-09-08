# Contract: asset layout and naming

The dashboard finds files by convention. There is no index; the name *is* the
interface, so a misnamed file is an invisible file.

```
assets/
  videos/{videoID}.mp4                        one per session
  timeseries/{videoID}_{dataType}.csv         one measure per file
  transcripts/{videoID}_transcript.json
  elan/{videoID}.eaf
  rqa/{videoID}_rqa_data.json                 written by analyses
  crqa/{videoID}_crqa_data.json
  crosswavelet/{videoID}_crosswavelet_data.json
```

`videoID` and `dataType` come from `config.json`. Neither may contain `_`
beyond the separator shown, because the name is split on it.

## Time series CSV

Two columns: a time column and one measurement.

```csv
Time,bodysync
0.000,0.1959
0.020,0.2213
```

- The time column is matched **case-insensitively** and normalised to `Time`.
- Time is in **seconds**, ascending. Not milliseconds, not frames.
- Only the first non-time column is read. Multi-column files are split on
  upload by the builder, one file per measure.
- `NaN` rows are dropped, not interpolated.

Converting from a tool that emits milliseconds — which is common, EnvisionBox
modules among them — is a unit change and a rename, nothing more.

## Analysis output

Where a result goes and what it is called is here. **What has to be in it** —
the bounds, the recorded reduction, the window, asked-for beside achieved, and
which significance level is the right one — is
[analysis output](analysis-output.md).

```
{output_dir}/{videoID}_{slug}_data.json
{
  "video_id": "3120",
  "<container>": { "<entity>": { … } },
  "precision":   { "significant_figures": 6, "note": … }
}
```

`entity` is a data type for single-series analyses (`"bodysync"`), and
`"{a}_vs_{b}"` for pairwise ones (`"bodysync_vs_neuralsync"`).

The container key is **not** uniform, and reading the wrong one gets you an
empty tab rather than an error:

| file | container |
|---|---|
| `rqa/{videoID}_rqa_data.json` | `rqa_data` |
| `crqa/{videoID}_crqa_data.json` | `crqa_data` |
| `crosswavelet/{videoID}_crosswavelet_data.json` | **`crosswavelet_pairs`** |

A file is **merged, not replaced**, when an analysis writes into it: ORTHO's
categorical gaze RQA writes into the same `rqa_data` the shared step writes,
and before merging existed whichever ran second erased the other. Write through
`dims_analysis.common.results.write_payload`, never `json.dump`.

### The picture inside a payload

Every per-entity entry carries a `visualization` block, and it is a
**reduction** — a few hundred points regardless of how long the recording was.

```jsonc
"visualization": {
  "time": [...], "data": [...],      // "data_x"/"data_y" for a pairwise analysis
  "matrix_size": 500,
  "sparse_matrix": [[12, 40], ...],  // recurrent cells only, as [row, col]
  "reduction": {
    "factor": 12,
    "series": "block-mean",          // "block mode (categorical)" for coded series
    "matrix": "density-preserving",
    "n_points_full": 6013,
    "rate_full": 0.0700,             // the analysis
    "rate_drawn": 0.0699             // what the picture actually shows
  }
}
```

`sparse_matrix` lists only the recurrent cells of a `matrix_size` ×
`matrix_size` grid, because a recurrence plot is a few percent ones and the
dense form would be a hundred times larger. Indices are into the **reduced**
grid, so they align with `time` and `data` in the same block and with nothing
else.

`rate_full` and `rate_drawn` normally agree. They can differ on a very sparse
matrix, where reproducing the rate exactly would reduce a recurrent line to a
couple of dots; the reduction keeps the structure there and records what it
drew, so the picture never silently contradicts the number printed beside it.

## Two artifacts, not one

```
{output_dir}/{videoID}_{slug}_data.json   the browser payload — reduced
{output_dir}/{videoID}_{slug}.npz         the analysis — full resolution
```

Members are `"{entity}/{array}"`, so one file holds every entity for that video
and a new one is appended without rewriting the rest.

| file | members, per entity |
|---|---|
| `{videoID}_crosswavelet.npz` | `time`, `period`, `freqs`, `coherence`, `power`, `phase`, `coi`, `scale_avg_power`, `sig95_wtc` |
| `{videoID}_rqa.npz` | `time`, `signal`, `threshold`, `recurrence_rate`, `windowed_time`, `windowed_RR`, `windowed_DET`, `windowed_LAM`, `windowed_L_MAX` |
| `{videoID}_crqa.npz` | `time`, `signal_x`, `signal_y`, `threshold`, `global_recurrence_rate`, and the same `windowed_*` |

**The recurrence matrix itself is not stored**, in either file, and that is
deliberate rather than an omission: it is quadratic in the length of the
recording, and one Karnatak lesson would be 3.4 billion cells. What is stored
is what a reader continues from — both prepared signals, the threshold, and the
windowed metrics at full resolution — from which the matrix is one `cdist`
away, at whatever resolution they can afford.

The JSON is reduced to a few hundred points so a page can draw it, and the
reduction is recorded in it. **Analyse from the `.npz`.** On real data the JSON
holds a sixth of the time points, and for a long time it was the only thing
kept, so anyone continuing from a study's output was working at a fraction of
the resolution without being told.

### Precision

The JSON is **rounded to 6 significant figures**, and says so: every output
carries a `precision` block naming the figure count and pointing at the `.npz`.

That is not a compression trick, it is honesty about what the file is. A value
in the payload becomes a pixel's colour on a heatmap — a few hundred
distinguishable levels — so writing `0.5940133868313864` claims a precision the
measurement never had and costs four times the bytes. Measured on the reference
study: 8.2 MB → 2.3 MB for cross-wavelet, 5.1 MB → 1.0 MB for RQA.

**Significant figures, not decimal places**, and the difference is not cosmetic:

| value | 6 significant figures | 6 decimal places |
|---|---|---|
| `3.21e-08` | `3.21e-08` | `0.0` — destroyed |
| `0.5940133868313864` | `0.594013` | `0.594013` |

Cross-wavelet power spans eight orders of magnitude, so a fixed number of
decimal places silently zeroes the quiet cells. Integers — counts, and the
`[row, col]` index pairs of a sparse recurrence matrix — are left untouched.

Nothing is lost to analysis: the `.npz` holds float32, which is about seven
significant figures.

### Reduction

A **continuous series** is block-averaged, not sampled every nth point.
Striding is decimation with no low-pass filter: it does not remove detail, it
folds it back onto the frequencies that remain. Phase is averaged through the
unit circle, since the numerical mean of +179° and −179° is 0°. A **categorical
series** (gaze codes) takes each block's commonest value, because the mean of
two area-of-interest codes is a third area nobody looked at.

A **recurrence matrix is binary**, and it has two properties a reader takes from
the picture: where the structure is, and how much of the plot is recurrent.
Neither obvious method keeps both. Striding keeps the rate and destroys the
structure — a line one cell off the main diagonal vanishes entirely, because
the sampled rows and columns never intersect it, and an off-diagonal line is
exactly what a lagged coupling looks like. Block-OR keeps the structure and
inflates the rate: measured on an ORTHO recording at factor 9, a 10.9% matrix
became 54.4% beside a caption still saying 10.9%.

What is used instead: block-average the binary matrix into a per-block
recurrence *fraction*, then keep the densest blocks — as many as reproduce the
original rate. Structure survives because a block on a line is denser than the
background; the rate survives because it is what the selection is calibrated
to.

Read it with:

```python
import numpy as np
with np.load("assets/crosswavelet/3120_crosswavelet.npz") as z:
    coherence = z["bodysync_vs_neuralsync/coherence"]   # (periods, time)
    period    = z["bodysync_vs_neuralsync/period"]
    null      = z["bodysync_vs_neuralsync/sig95_wtc"]   # the 95% AR(1) level
```

## Acceptance

- A file placed by these rules is picked up with no config change beyond listing
  its `videoID`/`dataType`.
- A file that breaks them produces a validation error naming the expected path,
  rather than an empty tab.
