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
ones. Alongside it, a step writes the full-resolution result as `.npz`; the JSON
is a browser payload and may be reduced, so it is not what you analyse from.

## Acceptance

- A file placed by these rules is picked up with no config change beyond listing
  its `videoID`/`dataType`.
- A file that breaks them produces a validation error naming the expected path,
  rather than an empty tab.
