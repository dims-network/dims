# The analyses DIMS ships

Three analyses come with the core. Each one reads prepared time series from
`assets/timeseries/`, and each one writes a single JSON payload that a dashboard
tab draws and a notebook can read back.

| analysis | takes | asks | writes |
|---|---|---|---|
| [Cross-wavelet & coherence](crosswavelet.md) | a **pair** | at which timescales, and when, do two signals share energy — and do they keep a consistent timing relationship? | `assets/crosswavelet/{video}_crosswavelet_data.json` |
| [Recurrence, RQA](rqa.md) | **one** signal | when does a signal return to a value it held before, and how structured are those returns? | `assets/rqa/{video}_rqa_data.json` |
| [Cross-recurrence, cRQA](crqa.md) | a **pair** | when is one signal where the other has been, and how long do the two stay together? | `assets/crqa/{video}_crqa_data.json` |

Which to reach for is mostly a question of what you think the structure is. The
wavelet analysis works in the frequency domain and answers questions about
*rhythm*: it is at its best when there is something oscillating, even briefly,
and it will tell you at which period and with what lead or lag. The recurrence
analyses make no assumption that anything repeats at a fixed rate — they ask
whether the signal keeps coming back to where it has been, which is a question
you can ask of a signal with no rhythm at all.

Read them beside the two contracts that govern their output:
[asset layout](../contracts/assets.md) says where every file goes and what a
`visualization` block holds; [analysis output](../contracts/analysis-output.md)
says what any analysis must record and why.

## The running example

Every figure in this section is real output. A generator builds six synthetic
signals whose answers are known before anything runs, feeds them to
`dims-analysis run`, and the pages plot the payloads that come out —
[`docs/analyses/demo/make_demo_data.py`](demo/make_demo_data.py), and the
committed results beside it. Nothing here is an illustration of what the code
is supposed to do.

Two of those six are the running example, carried through all three pages:

<div class="figure" id="fig-signals"></div>

`sig_a` and `sig_b` are built to make one distinction visible. Both contain a
4-second oscillation, with `sig_b` delayed by 0.7 s — a constant phase lag, so
their *timing relationship at that period is perfectly consistent*. Both also
contain a burst between 20 s and 35 s, at a period of 1.2 s in `sig_a` and
1.45 s in `sig_b` — plenty of energy in both at almost the same time, but with a
relationship that drifts. On top of each sits independent AR(1) noise, which is
the kind of thing the chance level is estimated against.

That pair is the reason both cross-wavelet *power* and *coherence* exist: power
finds the burst, coherence does not.

## What goes in

One CSV per recording per signal, at `assets/timeseries/{video}_{type}.csv`,
with a `Time` column in seconds and one value column:

```csv
Time,sig_a
0.000000,0.101474
0.100000,0.264876
0.200000,0.451709
```

The rules are in [asset layout](../contracts/assets.md), and all three analyses
read through one loader, so they agree about what the file says: the time column
is matched under any casing, rows with missing values are dropped, and the
series is sorted by time. What differs between them is the guard afterwards —
cross-wavelet refuses fewer than 50 samples, the recurrence analyses refuse
fewer than 10 and refuse a signal that does not vary at all.

## Turning them on

Each analysis is gated by one key in the study's `config.json`, and the shape of
that key is not the same for all three:

```jsonc
{
  "videoIDs": ["demo"],

  "include_RQA": ["sig_a", "periodic", "noisy"],          // data types
  "include_cRQA": [["sig_a", "sig_b"], ["lead", "lag"]],  // pairs
  "include_crosswavelet": [["sig_a", "sig_b"]],           // pairs

  "analysis": {
    "rqa":  { "window": 12.0, "step": 0.5, "targetRecurrence": 0.07 },
    "crqa": { "window": 12.0, "step": 0.5, "targetRecurrence": 0.07 },
    "crosswavelet": { "mcCount": 200, "maxPeriod": 20.0 }
  }
}
```

Three things about those keys are worth knowing before they cost you a rebuild.

**A list, not `true`.** `"include_RQA": true` is refused with a message naming
the fix, because the key has to say *which* signals. The same goes for a bare
string: write `["sig_a"]`, not `"sig_a"`.

**Case does not matter, but a duplicate does.** `include_crqa` and
`include_cRQA` are the same key. Writing both in one file is an error rather
than a preference — which of them applied would otherwise be arbitrary.

**A flat list of types expands to pairs for cross-wavelet, and only for
cross-wavelet.** `"include_crosswavelet": ["a", "b", "c"]` is a legacy form
meaning all three unique pairs. `"include_cRQA": ["a", "b", "c"]` is *not*: the
step wants `[type1, type2]` entries, skips anything else with a warning, and
then writes nothing. The config schema shares one definition between the two
keys, so it will not catch this for you.

Tuning goes under `analysis.<step id>`, where the step id is `rqa`, `crqa` or
`crosswavelet` — the names `dims-analysis list` prints, not the gate keys. Each
page below documents its own parameters; the schema that validates them is
[`contracts/config.schema.json`](../contracts/config.schema.json).

## What comes out

One file per recording per analysis, always this shape:

```jsonc
{
  "video_id": "demo",
  "payload_version": 2,
  "<container key>": { /* keyed by data type, or by "{a}_vs_{b}" */ },
  "provenance": { "core_version": "1.0.2", "...": "the settings actually used" },
  "precision": { "significant_figures": 6, "note": "..." }
}
```

| analysis | container key | entries keyed by |
|---|---|---|
| `rqa` | `rqa_data` | data type — `"sig_a"` |
| `crqa` | `crqa_data` | pair — `"sig_a_vs_sig_b"` |
| `crosswavelet` | `crosswavelet_pairs` | pair — `"sig_a_vs_sig_b"` |

Writing merges one level deep rather than replacing the file, so a study-owned
analysis can add its own entries to `rqa_data` without erasing the core's.

### Numbers are rounded, arrays are packed

Every small field is rounded to **six significant figures** — significant
figures, not decimal places — and non-finite values become `null`, because
`json.dump` writes a bare `NaN` token that `JSON.parse` rejects outright.

The large arrays skip the rounding and travel packed, in one of two
self-naming encodings:

```jsonc
{"encoding": "bitmap-b64", "rows": 300, "cols": 300, "data": "…"}
{"encoding": "f32-b64",    "shape": [40, 150],       "data": "…"}
```

`bitmap-b64` is one bit per cell, most-significant-first, with each **row**
starting on a byte boundary — so a cell is `byte[row * stride + (col >> 3)]`
where `stride = (cols + 7) >> 3`. It is what carries a recurrence matrix, which
is binary and dense: measured on one study's gaze matrix, index pairs cost
7,300,452 bytes against 133,803 as a bitmap.

`f32-b64` is little-endian float32 — stated rather than inherited, because numpy
follows the platform and the browser's `DataView` defaults to big-endian. NaN
survives it, and means what it means in the analysis: *this cell has no value*.

Reading either one is a few lines. This is the decoder the figures on these
pages actually use:

```js
function decodeF32(o) {
  const raw = Uint8Array.from(atob(o.data), c => c.charCodeAt(0));
  const flat = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);
  const [rows, cols] = o.shape.length === 2 ? o.shape : [1, o.shape[0]];
  const out = [];
  for (let r = 0; r < rows; r++) {
    const row = new Array(cols);
    for (let c = 0; c < cols; c++) {
      const v = flat[r * cols + c];
      row[c] = Number.isNaN(v) ? null : v;   // Plotly reads null as a gap
    }
    out.push(row);
  }
  return o.shape.length === 2 ? out : out[0];
}

function decodeBitmap(o) {
  const raw = Uint8Array.from(atob(o.data), c => c.charCodeAt(0));
  const stride = (o.cols + 7) >> 3, out = [];
  for (let r = 0; r < o.rows; r++) {
    const row = new Array(o.cols);
    for (let c = 0; c < o.cols; c++) {
      row[c] = (raw[r * stride + (c >> 3)] >> (7 - (c & 7))) & 1;
    }
    out.push(row);
  }
  return out;
}
```

In Python, `dims_analysis.common.arrays.unpack()` walks a payload and returns
whichever it finds, so you do not have to know in advance which fields grew
large enough to be packed.

### A picture and the analysis are not the same file

Every payload holds a `visualization` block that has been **reduced** to
something a browser can draw, and records how:

```jsonc
"reduction": {
  "factor": 2,
  "series": "block-mean",
  "matrix": "density-preserving",
  "n_points_full": 600,
  "rate_full": 0.0700,
  "rate_drawn": 0.0699
}
```

A recurrence matrix is reduced density-preserving rather than by block-mean and
a threshold, so the drawn plot has the same recurrence rate as the real one —
`rate_full` beside `rate_drawn` is there to be checked. A cross-wavelet grid is
block-averaged, except phase, which is averaged through the unit circle because
the mean of 179° and −179° is not 0°.

For cross-wavelet there is a second file, `{video}_crosswavelet_full.json`, at
the resolution the analysis actually ran at. **Analyse that one.** The reduced
payload is a picture. For the recurrence analyses there is no second file,
because there is nothing in it that the payload does not already carry: the
matrix is quadratic and is rebuilt in two lines from the stored signal and
threshold, which each page shows.

The rule and its rationale are contract A3 in
[analysis output](../contracts/analysis-output.md).

## Where these figures came from

The demo payloads were produced by running the real steps over the synthetic
signals, against the pinned dependencies. Re-generate them with:

```sh
python docs/analyses/demo/make_demo_data.py
```

Everything is seeded — the signals, and the Monte Carlo null behind the
coherence chance level — so two runs produce identical files, and a change in a
figure means a change in the analysis.
