# <study name>

A DIMS dashboard: video beside its time series, with recurrence and
cross-wavelet analyses of how the signals relate over time.

Replace this file with a description of your study. What follows is the part
worth keeping — how to run it, and how to rebuild what it draws.

## Run it

```sh
python serve.py            # then open http://localhost:8000
python serve.py 8080       # if that port is taken
```

Nothing to install and no build step: the dashboard is plain files, and
`serve.py` uses only the Python standard library.

## What you get

The tabs that appear are decided by `config.json` — a tab whose key is absent
or empty does not show up at all.

| tab | shown when | what it draws |
|---|---|---|
| Time series | always | every signal for the selected video, stacked on a shared time axis |
| RQA | `include_RQA` lists data types | a recurrence plot per signal, with recurrence rate, determinism and laminarity tracked over time |
| Cross-RQA | `include_cRQA` lists pairs | the same, between two different signals — structure off the main diagonal is a lagged coupling |
| Cross-Wavelet | `include_crosswavelet` lists pairs | coherence by time and timescale, with a chance level from a Monte Carlo null |
| ELAN | `include_elan` is true | annotation tiers from an `.eaf` file, aligned to the video |

Across all of them: pick a point on the timeline and every tab narrows to a
window around it; the window size is `defaultWindowSize` seconds.

## Where the data lives

By default, in `assets/` here:

```
assets/videos/{videoID}.mp4              the recording
assets/timeseries/{videoID}_{type}.csv   one signal, columns Time and a value
assets/transcripts/{videoID}_transcript.json
assets/elan/{videoID}.eaf
assets/rqa/ assets/crqa/ assets/crosswavelet/    written by the analyses
```

If the recordings are identifiable and must stay out of the repository, copy
`data.local.json.example` to `data.local.json`, point `assetsRoot` at them, and
leave `assets/` here empty. `serve.py` and every analysis step resolve through
it, so nothing has to be copied in. `data.local.json` is untracked.

## Rebuild the analyses

```sh
pip install -e /path/to/dims     # the analyses; not on PyPI yet
python build_assets.py --check   # what would run
python build_assets.py           # run it
```

`build_assets.py` runs the shared analyses for whatever `config.json` enables,
then any analysis this study ships itself in `opt/step_<id>.py`, gated by
`include_<id>`.

It does **not** produce the time series. Where those come from is specific to
the study — motion capture from video, an eye-tracker export, a game log — and
if this study has such a step it belongs in `opt/` and `build_assets.py` will
run it. Until then, put the CSVs in `assets/timeseries/` yourself.

## Configuration

`config.json` is validated against
[`docs/contracts/config.schema.json`](https://github.com/dims-network/dims/blob/main/docs/contracts/config.schema.json)
in CI. The keys you will set first:

```jsonc
{
  "videoIDs": ["session1"],                    // one per recording
  "dataTypes": { "session1": ["bodysync"] },   // which signals it has
  "include_RQA": ["bodysync"],                 // analyses to enable
  "include_crosswavelet": [["bodysync", "neuralsync"]],
  "defaultWindowSize": 5,
  "title": "", "subtitle": "", "authors": "", "contacts": ""
}
```

## The rest of the system

- The dashboard code in `vendor/` is a pinned copy of the shared core. It is
  verified against its release in CI, so do not edit it — a fix belongs
  upstream in [dims](https://github.com/dims-network/dims) and arrives here as
  a version bump.
- A tab that only makes sense for this study goes in `tabs/`, loaded from
  `index.html` between the study-tabs markers. Contract:
  [`docs/contracts/tab.md`](https://github.com/dims-network/dims/blob/main/docs/contracts/tab.md).
- An analysis that only makes sense for this study goes in `opt/`. Contract:
  [`docs/contracts/step.md`](https://github.com/dims-network/dims/blob/main/docs/contracts/step.md).
