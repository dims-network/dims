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

```
{output_dir}/{videoID}_{slug}_data.json
{
  "video_id": "3120",
  "<analysis>_data": { "<entity>": { … } }
}
```

`entity` is a data type for single-series analyses, `"{a}_vs_{b}"` for pairwise
ones.

## Two artifacts, not one

```
{output_dir}/{videoID}_{slug}_data.json   the browser payload — reduced
{output_dir}/{videoID}_{slug}.npz         the analysis — full resolution
```

The JSON is reduced to a few hundred points so a page can draw it, and the
reduction is recorded in it. **Analyse from the `.npz`.** On real data the JSON
holds a sixth of the time points, and for a long time it was the only thing
kept, so anyone continuing from a study's output was working at a fraction of
the resolution without being told.

The reduction is a block average, not every nth sample. Striding is decimation
with no low-pass filter: it does not remove detail, it folds it back onto the
frequencies that remain. Phase is reduced through the unit circle, since
averaging +179° and −179° numerically gives 0°.

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
