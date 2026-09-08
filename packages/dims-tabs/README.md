# dims-tabs

The built-in tabs. One self-registering file each, no index, no build step.

| file | shows | needs |
|---|---|---|
| `timeseries.js` | the raw signals against the video | `assets/timeseries/` |
| `rqa.js` | recurrence plot and windowed metrics | the `rqa` analysis |
| `crqa.js` | cross-recurrence between two signals | the `crqa` analysis |
| `crosswavelet.js` | coherence and power against a chance level | the `crosswavelet` analysis |
| `elan.js` | ELAN annotation tiers | `assets/elan/` |

A tab is switched on by its `include_*` key in `config.json`. A study can add
its own tabs in its `tabs/` directory; they register exactly the same way, which
is the point — the extension path is the one the built-ins use, so it cannot
quietly rot.

Write one against [`docs/contracts/tab.md`](../../docs/contracts/tab.md).

## What a tab may not do

- reach outside its own pane
- read a file directly — the host resolves assets, including for a study whose
  data lives outside the repository
- talk to another tab; the shared time bus is the only channel
- read the host's JavaScript theme object; style with CSS custom properties

## Reading an analysis payload

Payloads are **reduced** for the browser and rounded to six significant
figures — a picture, not the analysis. The container key differs per analysis
(`rqa_data`, `crqa_data`, but `crosswavelet_pairs`), and reading the wrong one
returns nothing and raises nothing. The shapes are in
[`docs/contracts/assets.md`](../../docs/contracts/assets.md).

Draw the reduction honestly: a payload carries a `reduction` block saying what
factor produced the picture, and a recurrence plot carries the rate it actually
drew alongside the rate of the full analysis.

Like `dims-core`, this directory is vendored into every study and verified
against the release. Never edit a study's copy.
