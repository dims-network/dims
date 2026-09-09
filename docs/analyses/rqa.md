# Recurrence quantification (RQA)

A recurrence plot asks one question of one signal, for every pair of moments in
it: *were these two moments in nearly the same state?* Mark the cell black if
they were, white if they were not, and the resulting picture makes structure
visible that a time-series plot hides. Long diagonal lines mean the signal
repeated a whole stretch of its history. Vertical and horizontal blocks mean it
stopped moving. Isolated speckle means it never came back to anywhere twice in a
row.

RQA is the practice of turning that picture into numbers.

- Step id `rqa`, gated by `include_RQA`, a list of data types.
- Writes `assets/rqa/{video}_rqa_data.json`.
- Pure numpy and scipy — the only import that matters is
  `scipy.spatial.distance.cdist`.

<div class="figure" id="fig-rqa-plot"></div>

## This implementation uses no time-delay embedding

Textbook RQA reconstructs a phase space from a scalar signal first, using
Takens' method: each point becomes a vector of *m* samples spaced *τ* apart, and
distances are taken between those vectors. **DIMS does not do this.** The whole
of the state-space construction is one line:

```python
ts_normalized = _series.normalise(time_series)   # z-score
ts_reshaped = ts_normalized.reshape(-1, 1)       # embedding dimension m = 1
distance_matrix = cdist(ts_reshaped, ts_reshaped, metric='euclidean')
```

Embedding dimension **m = 1**, delay **τ = 0**, so the distance between moments
*i* and *j* is simply `|xᵢ − xⱼ|` on the z-scored signal. There is no
`dimension`, `delay`, `tau` or `embedding` parameter anywhere in the package,
and none is applied silently — the reshape is the whole of it.

Three consequences you should carry into any interpretation:

1. **This measures amplitude recurrence, not trajectory recurrence.** Two
   moments count as recurrent when the signal has the same *value*, regardless
   of whether it was rising at one and falling at the other. An embedded
   analysis would separate those; this one does not.
2. **The numbers are not comparable with published values** from an embedded
   analysis of the same data. DET in particular is systematically different —
   an unembedded plot has more short diagonals, because a value can recur
   without the trajectory recurring.
3. **It is still a well-defined measurement, and it is stable.** Nothing here
   depends on choosing *m* and *τ*, which in practice is where most of the
   analyst-to-analyst variance in published RQA comes from. What you lose in
   dynamical interpretation you gain in reproducibility.

If your question genuinely needs an embedded phase space, the honest route is a
study-owned step — see [writing an analysis](../contracts/step.md) — rather than
reading these numbers as though they were embedded.

## The threshold is a recurrence rate, not a radius

The other choice that defines a recurrence plot is ε, the distance below which
two moments count as "the same". Most implementations take a fixed radius. DIMS
takes a **fixed recurrence rate**: ε is the percentile of the distance matrix
that makes a stated fraction of pairs recurrent.

```python
values = distance_matrix[np.triu_indices_from(distance_matrix, k=1)]
threshold = np.percentile(values, target_recurrence * 100)
recurrence_matrix = (distance_matrix <= threshold).astype(np.uint8)
```

The strict upper triangle is used, so the line of identity — n zeros that would
drag the percentile down — is excluded. The default target is **0.07**.

This trade is deliberate and it has consequences:

- **RR is not informative globally.** It is fixed by construction at whatever
  you asked for. The windowed RR still is informative, because a window can be
  denser or sparser than the record as a whole.
- **DET and LAM depend strongly on the rate.** Two recordings analysed at
  different `targetRecurrence` values are not comparable, and neither are
  yours against a paper that used a fixed radius.
- **The target is not always reachable.** A quantised sensor or a signal that
  is partly still produces many exactly-equal distances, and the percentile
  lands on a plateau. When that happens the payload says so:
  `achieved_recurrence` sits beside `target_recurrence`, and
  `recurrence_rate_warning` is a sentence explaining what is not comparable.
  Measured cases: a real gaze series reached 12.7 % against a 7 % target, and a
  signal quantised to four levels reached 33.7 %.

**There is no Theiler window.** The only exclusion is the line of identity
itself, `k = 0`, skipped in the diagonal scan and subtracted from the recurrence
rate. Implementations that exclude a band around the diagonal report lower DET
than this one on the same data, because the short diagonals immediately beside
the identity line — which are an artefact of the signal being continuous, not a
finding — are counted here.

<div class="figure" id="fig-rqa-compare"></div>

## The measures

All four come from `common/recurrence.py`, computed over each window. The
minimum line length is **fixed at 2** — a "line" of one point is a point.

With `R` the binary matrix, `n` its side, and `ℓ` the length of a run:

| measure | formula | units |
|---|---|---|
| **RR** — recurrence rate | `(ΣR − n) / (n² − n)` | share, 0…1 |
| **DET** — determinism | `Σ{ℓ over diagonals, ℓ ≥ 2} / (ΣR − n)` | share, 0…1 |
| **LAM** — laminarity | `Σ{ℓ over verticals, ℓ ≥ 2} / ΣR` | share, 0…1 |
| **L_MAX** — longest diagonal | `max(ℓ over diagonals) × Δt` | **seconds** |

DET and LAM have **different denominators**, and that is not an oversight. Both
are shares of the recurrent points that lie on lines, and the rule is that
whatever a line extraction ignores, its denominator must ignore too. The
diagonal scan skips the line of identity, so DET's denominator excludes those
`n` points; the vertical scan skips nothing, so LAM's is every recurrent point.
Sharing one denominator got this wrong in both directions in turn — first
deflating DET by 17–25 % on real data, then, once corrected, inflating LAM
above 1.0, which a share of points cannot be. Separated, LAM matches pyrqa to
four decimal places on a pure sine.

`L_MAX` is in **seconds**, not samples. Multiplying by Δt is what makes it
comparable between a 50 Hz and a 100 Hz recording of the same movement.

### What is not computed

L (mean diagonal line length), ENTR (Shannon entropy of the line-length
histogram), TT (trapping time), V_MAX, DIV, RATIO, TREND and the recurrence-time
measures are **not** in the payload. The line-length histograms that would
produce them are built and then reduced to a sum and a maximum. If you need one
of them, the matrix is two lines away from being back in memory — see below.

## Windows

The four measures are shares of the structure inside one window, and every one
of them moves with how long that window is. So the window is a parameter of the
result in the same way the recurrence rate is, and the same rule applies: what
was asked for and what was used are both recorded.

Windows are square blocks along the main diagonal of the full-resolution matrix,
placed in **seconds** rather than samples — the same 2 s window on a 50 Hz and a
100 Hz recording gives the same answer. A window is shortened rather than
honoured when the recording cannot hold twenty of them, and the payload's
`window` block then carries a `warning` saying so in a sentence.

<div class="figure" id="fig-rqa-metrics"></div>

## Parameters

Under `analysis.rqa` in the study's `config.json`:

| key | type | default | what it does |
|---|---|---|---|
| `window` | seconds | 20.0 | length of the sliding window |
| `step` | seconds | 1.0 | how far it moves between windows |
| `targetRecurrence` | fraction, 0 < x < 1 | 0.07 | the recurrence rate the threshold search aims for |

A value that is not a number is an error naming the key, not a silent fall back
to the default: `"window": "20s"` is refused.

Fixed in the step: minimum line length 2, no Theiler window, Euclidean distance,
z-score normalisation, 20 windows minimum before a window is shortened, and 500
points as the cap on the drawn matrix.

### Bounds

- Fewer than **10 usable samples**, or a signal whose standard deviation is 0,
  and the data type is skipped with a message. The variance guard exists
  because both this and cross-recurrence normalise by the standard deviation; a
  constant signal once produced `recurrence_rate = −0.000977517`, a negative
  share of cells, and it reached a dashboard caption.
- The distance matrix is `n × n` float64, so it is refused before allocation
  above a **2 GiB** budget — about **16,384 samples**. At 50 Hz that is five and
  a half minutes of recording. Downsample, or window the input, rather than
  raising the budget.

## What it writes

One entry per data type under `rqa_data`:

```jsonc
{
  "video_id": "demo",
  "payload_version": 2,
  "rqa_data": {
    "sig_a": {
      "data_type": "sig_a",
      "threshold": 0.127161,
      "recurrence_rate": 0.07,
      "target_recurrence": 0.07,
      "achieved_recurrence": 0.07,
      "recurrence_rate_warning": null,
      "time_range": [0.0, 59.9],
      "windowed_metrics": { "time": [], "RR": [], "DET": [], "LAM": [], "L_MAX": [] },
      "window": { "length_requested_sec": 12.0, "length_used_sec": 12.0,
                  "step_requested_sec": 0.5, "step_used_sec": 0.5,
                  "n_windows": 96 },
      "visualization": {
        "time": [], "data": [], "matrix_size": 300,
        "matrix": { "encoding": "bitmap-b64", "rows": 300, "cols": 300, "data": "…" },
        "reduction": { "factor": 2, "series": "block-mean",
                       "matrix": "density-preserving", "n_points_full": 600,
                       "rate_full": 0.07155, "rate_drawn": 0.0715556 }
      },
      "full_data": {
        "n_points": 600, "time_range": [0.0, 59.9],
        "time":   { "encoding": "f32-b64", "shape": [600], "data": "…" },
        "signal": { "encoding": "f32-b64", "shape": [600], "data": "…" }
      }
    }
  },
  "provenance": { "core_version": "1.0.2", "target_recurrence": 0.07,
                  "max_points_drawn": 500 },
  "precision": { "significant_figures": 6 }
}
```

| field | type | units / notes |
|---|---|---|
| `threshold` | float | Euclidean distance **in z-score units**, not in the signal's own |
| `recurrence_rate` | float | share, off-diagonal |
| `target_recurrence`, `achieved_recurrence` | float | asked for, and got |
| `recurrence_rate_warning` | string or `null` | present when those two differ by more than 0.01 |
| `windowed_metrics.time` | list | window **centres**, seconds, taken from the real time axis |
| `windowed_metrics.RR/DET/LAM` | list | shares, 0…1 |
| `windowed_metrics.L_MAX` | list | **seconds** |
| `window` | object | requested beside used, plus `n_windows` and an optional `warning` |
| `visualization.time`, `.data` | list | the reduced signal, z-scored, at most 500 points |
| `visualization.matrix` | `bitmap-b64` | **time × time**, symmetric, square |
| `full_data.time`, `.signal` | `f32-b64` | the cleaned, z-scored signal at full rate |

One detail that catches people: `reduction.rate_full` and `rate_drawn` are plain
densities of their matrices — they **include** the line of identity, so they sit
about `1/n` above `recurrence_rate`. They are there to be compared with each
other, to show the drawn picture kept the density of the real one, not with the
recurrence rate.

### The matrix is never stored at full resolution

It is quadratic: 600 samples is a 300×300 drawn bitmap, 16,000 samples would be
a 32 MB one. What is stored instead is everything needed to rebuild it exactly:

```python
import numpy as np, json
from scipy.spatial.distance import cdist
from dims_analysis.common import arrays

entry = json.load(open("assets/rqa/demo_rqa_data.json"))["rqa_data"]["sig_a"]
signal = arrays.unpack(entry["full_data"]["signal"])          # already z-scored
R = (cdist(signal.reshape(-1, 1), signal.reshape(-1, 1)) <= entry["threshold"])
```

That is also the route to any measure this step does not compute:
`common.recurrence.line_lengths(R, "diagonal", 2, self_paired=True)` hands you
the histogram that ENTR and mean-L need.

## Further reading

- [**recurrence-plot.tk**](https://www.recurrence-plot.tk/) — the standard
  reference site for recurrence plots and RQA: the measures, what the visual
  structures mean, and an extensive bibliography. Start here.
- Marwan, N., Romano, M. C., Thiel, M., & Kurths, J. (2007). Recurrence plots
  for the analysis of complex systems. *Physics Reports*, **438**(5–6), 237–329.
  [doi:10.1016/j.physrep.2006.11.001](https://doi.org/10.1016/j.physrep.2006.11.001)
  — the review the site is built around, and the source of the standard
  definitions of DET, LAM and the rest.
- [Cross-recurrence](crqa.md) applies the same machinery to a pair of signals.
