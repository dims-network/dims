# From raw data to a dashboard

This page goes end to end once, with the commands that actually work. It
assumes nothing beyond a terminal, Python 3.10–3.12 and git.

If you would rather not use a terminal at all, the no-code builder does the
same job through a browser — see the bottom of this page.

## 0. Install the core

DIMS is not on PyPI yet (`dims` is taken by an unrelated project, and the name
`dims-network` is not published). Install it from a checkout:

```sh
git clone https://github.com/dims-network/dims
pip install -e ./dims
```

That gives you two commands: `dims-case`, which creates and maintains a study,
and `dims-analysis`, which runs the analyses.

> **Python 3.13 does not work for motion capture.** `mediapipe` ships no 3.13
> wheel. Everything else is fine on 3.13; if your study starts from video, use
> 3.12.

## 1. Create a study

A *study* — a "case" — is a small repository holding one study's configuration,
its data, and a pinned copy of the dashboard code.

```sh
dims-case new mystudy --visibility public     # creates ./case-mystudy
```

`--visibility` is the question you have to answer honestly, once. Choose
`private` if the data identifies anyone — video of faces, named transcripts —
and the study is created with commit and push guards that refuse to let data
into git, plus a CI check that catches it if the guards are bypassed. See
[data visibility](contracts/data-visibility.md).

It takes a **name**, not a path; use `--dir` to put it somewhere specific. To
turn an existing directory into a study instead, use `dims-case adopt`, which
never overwrites what is already there.

## 2. Put the data where it belongs

The dashboard finds files by name. There is no index, so a misnamed file is an
invisible file — the full rules are in [asset layout](contracts/assets.md).

```
assets/
  videos/{videoID}.mp4
  timeseries/{videoID}_{dataType}.csv      Time in SECONDS, ascending
  transcripts/{videoID}_transcript.json
  elan/{videoID}.eaf
```

A time series is two columns, a time column and one measurement:

```csv
Time,bodysync
0.000,0.1959
0.020,0.2213
```

Tools that emit milliseconds — several EnvisionBox modules do — need a unit
change and a rename, nothing more.

### If the data cannot go in the repository

For a private study, it should not. Leave `assets/` empty and say where the
data really is:

```sh
cp data.local.json.example data.local.json
```

```json
{ "assetsRoot": "/Volumes/Data/mystudy/assets" }
```

`serve.py` and every analysis resolve through that file, so everything runs
against the real data with an empty tracked `assets/`. Nothing has to be copied
into the repository — and on a private study, copying it in is exactly what the
guards exist to prevent.

## 3. Say what the study contains

`config.json` lists the recordings and switches on the analyses and tabs. The
full schema is [`config.schema.json`](contracts/config.schema.json).

```jsonc
{
  "title": "My study",
  "videoIDs": ["session01", "session02"],

  // Which measures each recording has. An object keyed by recording, not a
  // flat list: two sessions rarely carry exactly the same measures, and this
  // is what the time-series tab reads to know what to offer.
  "dataTypes": {
    "session01": ["bodysync", "neuralsync"],
    "session02": ["bodysync"]
  },

  // Which data types to analyse -- not true/false. The list is the answer to
  // "which of them", and true does not say.
  "include_RQA": ["bodysync", "neuralsync"],

  // Pairwise analyses take pairs.
  "include_cRQA":        [["bodysync", "neuralsync"]],
  "include_crosswavelet": [["bodysync", "neuralsync"]],

  // Tabs that need no analysis are plain switches.
  "include_elan": true
}
```

The distinction is the one thing here worth reading twice: an analysis key
names **what to analyse**, a tab key is a **switch**. Writing
`"include_RQA": true` is refused with a message saying what to write instead.

Key names are matched case-insensitively, so `include_crqa` and `include_cRQA`
are the same key.

## 4. Build the assets

```sh
python build_assets.py --check     # what would run, and what is missing
python build_assets.py             # actually run it
```

`--check` installs nothing and computes nothing. It tells you which recordings
it can see, which analyses are switched on, and which time series it could not
find — which is the fastest way to discover that a file is misnamed.

The cross-wavelet step estimates its coherence chance level by simulation and
is the slow one; on a long recording it is minutes per pair, not seconds. It
runs only when something in your config reads it, and the step says which it
chose — see [analysis output](contracts/analysis-output.md), A8.

Each analysis writes one JSON, reduced to a few hundred points so a page can
draw it. Cross-wavelet writes a second, `_full.json`, in the same schema at the
resolution it was computed at. **Continue your own analysis from `_full.json`**
where it exists; a recurrence payload carries its own full-resolution signal, so
there is nothing beside it to prefer.

## 5. Look at it

```sh
python serve.py        # http://localhost:8000
```

`serve.py` is a plain static server that also resolves `data.local.json`, so
video and assets outside the repository are served correctly. Opening
`index.html` directly from the filesystem will not work — the browser blocks
the fetches.

## 6. Record what a complete build looks like

Once the assets are right:

```sh
python build_assets.py --write-manifest
```

This writes `assets/MANIFEST.json` — names, sizes and checksums, never content.
It is the only thing in a private study's repository that says what a complete
set of assets is, so a later rebuild can be checked rather than hoped about.
Commit it.

## 7. Publish, if it is publishable

A public study deploys to GitHub Pages by the workflow it was created with; push
to `main` and it is live. A private study has no Pages workflow at all, by
construction, and going public is a deliberate, gated transition — not a
setting. The checklist is in [data visibility](contracts/data-visibility.md).

## Keeping up with the core

```sh
dims-case sync .        # refresh the vendored core to the newest release
dims-case check .       # verify nothing under vendor/ was edited
```

A bot opens this as a pull request every Monday. Never edit anything under
`vendor/`: CI rebuilds it from the release tag and compares, so a hand edit is a
red build rather than a silent fork. Fix it in the core and bump the pin.

## Without a terminal

```sh
pip install -e "./dims[builder]"
dims-builder
```

The builder asks for the same things this page does — recordings, time series,
annotations — and writes a study with them. It runs the same analyses through
the same package, so a project it produces and a project you make by hand are
the same project.
