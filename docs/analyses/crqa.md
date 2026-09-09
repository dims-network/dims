# Cross-recurrence quantification (cRQA)

Cross-recurrence asks the same question as [RQA](rqa.md), but across two
signals: *was signal X, at moment i, in a state that signal Y was in at moment
j?* The plot is no longer symmetric and no longer has a line of identity, and
the diagonal stops being trivial — a line **on** the diagonal means the two
signals are doing the same thing at the same time, and a line **parallel to** it
means one is doing what the other did, at a fixed delay.

- Step id `crqa`, gated by `include_cRQA`, a list of `[type1, type2]` pairs.
- Writes `assets/crqa/{video}_crqa_data.json`.
- Same machinery as RQA: `cdist`, one percentile threshold, the same four
  measures.

<div class="figure" id="fig-crqa-lag"></div>

## The method

```
CR(i, j) = Θ( ε − |xᵢ − yⱼ| )
```

on two z-scored signals sampled on one common grid. Rows index the **first**
series, columns the **second**, from `cdist(series1, series2)` — so the payload's
`data_x` runs down the rows and `data_y` across the columns.

As in RQA, **no time-delay embedding is applied**: both series are reshaped to
`(N, 1)`, so the embedding dimension is 1 and the delay is 0. The function that
builds the matrix would accept `(N, d)` arrays and its docstring still says
"embedded", but its only caller passes `d = 1`. Everything the
[RQA page says about that](rqa.md) applies here unchanged.

### Alignment is the real preprocessing

Cross-recurrence needs both signals on one clock, and that, rather than
detrending or tapering, is where the preparation happens:

1. Read both CSVs through the shared loader — NaNs dropped, sorted by time.
2. Refuse either series with fewer than 10 usable points or zero variance.
3. Require the two time ranges to overlap at all.
4. Build a uniform grid over the overlap at `min(Δt₁, Δt₂)`, the **finer** of
   the two median sampling intervals, and check the length of *that* grid
   against the 2 GiB matrix budget.
5. Linearly interpolate both series onto it.
6. z-score each.

There is **no detrending and no taper** here. The cross-wavelet step does both;
this one does not, because a recurrence threshold is a percentile of the
distances and a shared linear trend moves that percentile without changing the
structure much. If your signals have strong drift, know that it will show up as
large low-recurrence blocks off the diagonal.

### The threshold

The same fixed-recurrence-rate rule as RQA, with one difference: there is no
line of identity to exclude, so the percentile is taken over the **whole**
matrix rather than the upper triangle, and

```
RR = ΣR / (n · m)
```

with no subtraction. For the same reason DET's denominator here is the full
recurrent count — the diagonal scan skips nothing, so nothing is excluded from
what it is a share of. LAM is unchanged.

## What it measures, and what it does not

<div class="figure" id="fig-crqa-pair"></div>

The four measures are the same — RR, DET, LAM and L_MAX in seconds — and they
are computed over **square blocks on the main diagonal** of the cross-recurrence
matrix, sliding in seconds exactly as in RQA.

That placement is the important limitation, and it is easy to miss because the
plot shows more than the numbers do:

- **The windowed metrics describe simultaneity.** A block on the main diagonal
  covers moments where *i* and *j* are close, so DET and LAM here answer "how
  structured is what these two do at the same time?"
- **A lag is visible and unquantified.** In the figure above, `lead` and `lag`
  are the same signal 2 s apart and the recurrent band sits neatly off the
  diagonal — and nothing in the payload reports "2 s". There is no diagonal-wise
  cross-recurrence profile, no maximum-of-lag search, no line-of-synchronisation
  estimate.

If you need the lag, the matrix is one `cdist` away (the recipe on the
[RQA page](rqa.md) works here with `cdist(x, y)` and `self_paired=False`), and
the diagonal-wise profile is `[R.diagonal(k).mean() for k in range(-n+1, n)]`.

## Parameters

Under `analysis.crqa`, identical to RQA:

| key | type | default | what it does |
|---|---|---|---|
| `window` | seconds | 20.0 | length of the sliding window |
| `step` | seconds | 1.0 | how far it moves between windows |
| `targetRecurrence` | fraction, 0 < x < 1 | 0.07 | recurrence rate the threshold search aims for |

**A flat list of data types does not work here.** `include_cRQA` wants
`[[type1, type2], …]`; an entry that is not a two-element list is skipped with a
warning, and if none survive the step writes nothing at all. The config schema
shares one definition with `include_crosswavelet`, which *does* accept the flat
form, so validation will not catch this.

## What it writes

One entry per pair under `crqa_data`, keyed `"{type1}_vs_{type2}"`:

```jsonc
{
  "video_id": "demo",
  "payload_version": 2,
  "crqa_data": {
    "sig_a_vs_sig_b": {
      "pair_name": "sig_a_vs_sig_b",
      "series_names": ["sig_a", "sig_b"],
      "threshold": 0.127593,
      "global_recurrence_rate": 0.0700026,
      "recurrence_rate": 0.0700026,
      "target_recurrence": 0.07,
      "achieved_recurrence": 0.0700026,
      "recurrence_rate_warning": null,
      "time_range": [0.0, 59.8],
      "windowed_metrics": { "time": [], "RR": [], "DET": [], "LAM": [], "L_MAX": [] },
      "window": { "length_requested_sec": 12.0, "length_used_sec": 12.0,
                  "step_requested_sec": 0.5, "step_used_sec": 0.5,
                  "n_windows": 96 },
      "visualization": {
        "time": [], "data_x": [], "data_y": [], "matrix_size": 299,
        "matrix": { "encoding": "bitmap-b64", "rows": 299, "cols": 299, "data": "…" },
        "reduction": { "factor": 2, "series": "block-mean",
                       "matrix": "density-preserving", "n_points_full": 599,
                       "rate_full": 0.0700026, "rate_drawn": 0.0699768 }
      },
      "full_stats": {
        "n_points": 599, "window_size_sec": 12.0, "step_size_sec": 0.5,
        "time":     { "encoding": "f32-b64", "shape": [599], "data": "…" },
        "signal_x": { "encoding": "f32-b64", "shape": [599], "data": "…" },
        "signal_y": { "encoding": "f32-b64", "shape": [599], "data": "…" }
      }
    }
  },
  "provenance": { "core_version": "1.1.0", "target_recurrence": 0.07,
                  "max_points_drawn": 500 },
  "precision": { "significant_figures": 6 }
}
```

| field | type | units / notes |
|---|---|---|
| `series_names` | list of 2 | `[rows, columns]`, in that order |
| `threshold` | float | Euclidean distance in z-score units |
| `global_recurrence_rate` | float | share of all `n · m` cells |
| `recurrence_rate` | float | the same number under the name RQA uses |
| `target_recurrence`, `achieved_recurrence` | float | asked for, and got |
| `recurrence_rate_warning` | string or `null` | present when those two differ by more than 0.01 |
| `windowed_metrics` | object | as in RQA; `L_MAX` in seconds |
| `window` | object | requested beside used |
| `visualization.data_x`, `.data_y` | list | the reduced signals, z-scored; `data_x` runs down the rows |
| `visualization.matrix` | `bitmap-b64` | rows = first series, columns = second |
| `full_stats.signal_x`, `.signal_y` | `f32-b64` | both series on the common grid, z-scored |

### Two differences from the RQA payload

Worth knowing before you write code that reads both:

1. **The rate is written under two names.** `global_recurrence_rate` is what
   the dashboard tab reads; `recurrence_rate` is the same number under the name
   RQA uses. They are written from one value and cannot disagree.
2. **`full_stats` carries the window settings and `full_data` does not** — and
   the ones it carries are the values **requested**, not the ones used. When
   they differ, `window.length_used_sec` is the truth.

Until recently there was a third: this step recorded no
`target_recurrence`, `achieved_recurrence` or `recurrence_rate_warning`, so a
threshold search that landed on a plateau went unreported and the target
survived only in `provenance`. That was a gap against contract A6 in
[analysis output](../contracts/analysis-output.md) rather than a deliberate
difference, and it is closed — a payload written by an older core will still be
missing those three fields.

## Further reading

- [**recurrence-plot.tk**](https://www.recurrence-plot.tk/) — cross-recurrence
  plots, joint recurrence plots, and the diagonal-wise profile this
  implementation does not compute.
- Marwan, N., & Kurths, J. (2002). Nonlinear analysis of bivariate data with
  cross recurrence plots. *Physics Letters A*, **302**(5–6), 299–307.
  [doi:10.1016/S0375-9601(02)01170-2](<https://doi.org/10.1016/S0375-9601(02)01170-2>)
  — the line of synchronisation, and reading a lag off a cross-recurrence plot.
- [RQA](rqa.md) for the measures, the threshold rule and the embedding question,
  all of which are shared.
