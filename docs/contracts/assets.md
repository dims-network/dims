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
  "matrix": {                        // one bit per cell of a 500x500 grid
    "encoding": "bitmap-b64", "rows": 500, "cols": 500, "data": "…"
  },
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

Large arrays name their encoding; short axes stay plain JSON lists. Decode with
`DIMS.decodeArray(field)` in a tab, or `common.arrays.unpack(field)` in Python.
The full rules — and why a bitmap rather than the `[row, col]` index pairs this
used to carry — are in [analysis output](analysis-output.md), A2.

`rate_full` and `rate_drawn` normally agree. They can differ on a very sparse
matrix, where reproducing the rate exactly would reduce a recurrent line to a
couple of dots; the reduction keeps the structure there and records what it
drew, so the picture never silently contradicts the number printed beside it.

## Two resolutions, one format

```
{output_dir}/{videoID}_{slug}_data.json          the browser payload — reduced
{output_dir}/{videoID}_crosswavelet_full.json    the analysis — full resolution
```

Same schema, same field names; only the time axis differs, so one reader serves
both. **Only cross-wavelet has a second file**, because only its large fields
are two-dimensional: 128 scales × 3026 times against 128 × 504 drawn. A
recurrence payload carries its own full-resolution signal (`full_data` for RQA,
`full_stats` for cRQA) in the single file, because everything in it except the
matrix is one-dimensional and small.

**The recurrence matrix itself is not stored**, at any resolution, and that is
deliberate rather than an omission: it is quadratic in the length of the
recording, and one Karnatak lesson would be 3.4 billion cells. What is stored is
what a reader continues from — the prepared signals, the threshold, and the
windowed metrics at full resolution — from which the matrix is one `cdist` away.

Read it with:

```python
import json
from dims_analysis.common import arrays

with open("assets/crosswavelet/3120_crosswavelet_full.json") as fh:
    payload = json.load(fh)
v = payload["crosswavelet_pairs"]["bodysync_vs_neuralsync"]["visualization"]
coherence = arrays.unpack(v["coherence"])   # (periods, time)
period    = v["period"]
null      = v["sig95_wtc"]                  # the 95% AR(1) level, or null
```

### Precision

The JSON is **rounded to 6 significant figures**, and says so: every output
carries a `precision` block naming the figure count and what it applies to.

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

Nothing is lost to analysis: **the large arrays are not rounded at all.** They
travel as float32, about seven significant figures — more than this rounding
ever claimed. Only the short readable fields pass through it.

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

## Acceptance

- A file placed by these rules is picked up with no config change beyond listing
  its `videoID`/`dataType`.
- A file that breaks them produces a validation error naming the expected path,
  rather than an empty tab.
