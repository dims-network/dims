# `config.json` — every key

The study's own file. It says which recordings exist, which measures they have,
which analyses to run and which tabs to show. Everything else in a study is
derived from it.

The machine-readable shape, with every constraint, is
[`contracts/config.schema.json`](../contracts/config.schema.json) — the wizard
validates against it before writing. This page is the prose version, and adds the
one thing a schema cannot say: **who reads each key**.

Two keys are required: `videoIDs` and `dataTypes`. Unknown keys are allowed, so a
study-owned tab can keep its own settings here.

## Recordings and measures

| key | type | |
|---|---|---|
| `videoIDs` | `string[]` | the session identifiers. Each needs `assets/videos/{videoID}.mp4` unless a `videoSrcTemplate` says otherwise |
| `dataTypes` | `{videoID: string[]}` | the measures each session has. Each implies `assets/timeseries/{videoID}_{dataType}.csv` |

These two drive the recording picker and every file path the dashboard builds. A
measure named here with no CSV behind it is the most common cause of an empty tab.

## Switching analyses and tabs on

Each `include_*` key does double duty: the analysis reads it to decide what to
compute, and the tab reads it to decide whether to appear. **They are not always
the same test**, which is the subtlety worth knowing.

| key | type | analysis | tab appears when |
|---|---|---|---|
| `include_RQA` | `string[]` | one recurrence analysis per measure listed | the array is non-empty. **A bare `true` is rejected** — the schema refuses it, and the analysis raises a `ConfigError` naming the fix |
| `include_cRQA` | pair list | one cross-recurrence per pair | the array is non-empty |
| `include_crosswavelet` | pair list | one cross-wavelet per pair | non-empty **and** either the first entry is itself an array, or there are at least two entries |
| `include_elan` | `boolean` | none — there is no ELAN step | any truthy value |
| `include_network` | `true` or object | none — it reads the cross-wavelet payload | `true`, or any object |

`include_elan` and `include_network` have no analysis behind them: ELAN reads your
`.eaf` directly, and the network is a view of the cross-wavelet output.

### Pair lists, and the trap in them

Both `include_cRQA` and `include_crosswavelet` are declared with the same schema
definition, which accepts two forms:

```jsonc
"include_crosswavelet": [["a","b"], ["a","c"]]   // explicit pairs — prefer this
"include_crosswavelet": ["a","b","c"]            // legacy flat list
```

**Only `include_crosswavelet` expands the flat form** into all combinations.
`include_cRQA` skips every entry that is not a two-element list, so a flat list
there produces no pairs and no payload — while the schema, sharing one definition,
raises nothing, and the tab still appears because its gate only asks for a
non-empty array. The symptom is a cross-RQA tab saying its output is missing.

Write pairs. The schema's own description says "both forms are supported", which
is true of cross-wavelet and not of cross-RQA.

> The definition uses `anyOf` rather than `oneOf` on purpose: an empty list is
> valid under both branches, and `oneOf` would reject it.

## The window

| key | type | |
|---|---|---|
| `defaultWindowSize` | `number` | full width in **seconds** of the window around the playhead — the playhead ± half this value |

It seeds the **Window Size** control, which the viewer can then change; the
network tab also uses it as the starting half-width for "the moment".

## Presentation

| key | type | |
|---|---|---|
| `title` | `string` | **sets the browser tab title.** Two dashboards open at once are told apart by this |
| `subtitle`, `authors`, `contacts` | `string` | header text |

## Several camera angles

Read by the host, not by any tab.

| key | type | |
|---|---|---|
| `perspectives` | `string[]` | named angles, e.g. `wide`, `parent`, `child` |
| `videoPerspectives` | `{videoID: string[]}` | which angles actually exist per recording |
| `videoSrcTemplate` | `string` | path template with `{videoID}` and `{persp}` |
| `fallbackVideoSrcTemplate` | `string` | used when no template applies. Defaults to `assets/videos/{videoID}.mp4` |

With a template and no angle chosen, the host takes the first angle listed for
*that recording* before falling back to the first in `perspectives` — because not
every session has every angle.

## `analysis` — per-step tuning

```jsonc
"analysis": { "crosswavelet": { "mcCount": 300 }, "rqa": { "window": 30 } }
```

Keyed by step id. **This is where a study changes a parameter** — never in a
copied analysis script, which is what one fork previously had to maintain.

**Every *duration* here is in seconds**, never in multiples of the sampling
interval — that is the schema's own rule and the one that matters, since a window
expressed in samples silently changes meaning with the sampling rate. The
non-durations in the table below are what they say they are: `maxTimePoints` is
samples, `maxFreqPoints` scales, `mcCount` a count, `targetRecurrence` a fraction.

| key | steps | default | |
|---|---|---|---|
| `window` | rqa, crqa | `20` | windowed-metric window, capped at half the recording's span. The **step** is what shortens so that twenty windows fit. The payload records asked-for beside used for both — see [`analysis-common`](analysis-common.md) |
| `step` | rqa, crqa | `1` | windowed-metric step |
| `targetRecurrence` | rqa, crqa | `0.07` | the recurrence rate the threshold search aims for, as a fraction. **DET and LAM depend strongly on it**, so two recordings analysed at different rates are not comparable; the payload records asked-for beside achieved |
| `mcCount` | crosswavelet | see below | Monte Carlo surrogates behind the coherence null |
| `maxTimePoints` | crosswavelet | `500` | width of the stored picture, in samples. The analysis runs at full resolution regardless; this caps what the browser fetches |
| `maxFreqPoints` | crosswavelet | `100` | height of the stored picture, in scales |
| `maxPeriod` | crosswavelet | — | longest period to compute, in seconds |
| `scaleAvgBand` | crosswavelet | — | scale-averaging band `[min, max]`, in seconds |
| `saveFullResolution` | crosswavelet | `true` | also write `{video}_crosswavelet_full.json` at the computed resolution. Same schema, different time axis — **this is what a notebook should read**, not the reduced payload |

### `mcCount` decides hours

`300` is the publication setting and costs roughly **2.8 hours** on a
twelve-recording study. `0` skips the null entirely.

The default is neither: **`100` when `include_network` is set, and `0` otherwise**,
because the network's coherence mode is the only thing that reads the grid. The
analysis prints which way it went and why. The network's shared power mode reads
an analytic level instead, so it works either way.

Without a null, coherence cannot be interpreted — unrelated signals do not score
0 — so the cross-wavelet tab says the chance level was not computed rather than
letting the number look tested.

## `include_network`

Either `true` — meaning "on, with everything inferred" — or an object:

| key | |
|---|---|
| `groups` | `label`, an optional `color`, and a `match` regex when you are not declaring effectors |
| `effectors` | `series`, `label`, `group`, `part`, or explicit `x`/`y` as fractions of the chart |
| `band` | period band `[low, high]` in seconds to average each edge over. **This changes the answer**, not its presentation |
| `mode` | `coherence` (default) or `power` — which measure the edges start on |
| `threshold` | `{"coherence": 0.15, "power": 0.15}`, the share of tested cells that must beat the 95 % level for a solid edge |
| `layout` | `columns` (default) or `figure` |

`part` is one of `head`, `nose`, `lefthand`, `righthand`, `hand`, `torso`, `hip`,
`foot`. The full account, including what happens when a declaration and the data
disagree, is on [the network tab page](../tabs/network.md).

## Keys owned by tabs that are not built in

The schema lists these so a study using them validates; **nothing in the shipped
dashboard reads them.**

| key | owner |
|---|---|
| `include_trajectory`, `trajectory_settings`, `trajectory_tracks`, `path_images` | the ORTHO study's own `tabs/trajectory.js` |
| `include_dtw` | marked "beta" in the schema. **No implementation ships.** Setting it does nothing |

## See also

- [`contracts/assets.md`](../contracts/assets.md) — where each file must sit.
- [`contracts/case.md`](../contracts/case.md) — `dims-case.json`, which is a
  different file with a different job.
- [the analyses](../analyses/index.md) — what the tuning actually changes.
