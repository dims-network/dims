# Contract: what an analysis output is

[Asset layout](assets.md) says where a result goes and what it is called. This
says what has to be **in** it, and why each requirement exists.

It exists because nine defects were found in these outputs one at a time, each
by accident, and they were not nine unrelated bugs: nothing stated what an
output was supposed to be, so every check could only ask "did it crash?". Every
requirement below is stated once and tested against
[`examples/reference/`](../../examples/reference/README.md), a synthetic study
whose answers are known before anything runs.

---

## A1 — Stated input bounds, refused before allocating

An analysis states the shortest and longest input it accepts, in samples, with
the reason.

RQA and cross-RQA build a dense N×N matrix, so the maximum follows from memory:
a 58,000-point recording is 3.4 billion cells and **27 GB**, and there was no
guard at all. `common/limits.py` holds one implementation of the arithmetic;
`check_length` refuses **before** allocating and names the limit, the actual
length, and what to do about it.

The lower bound is a minimum of `MIN_POINTS` samples and a **non-zero
variance**. Both recurrence analyses normalise by the standard deviation, and a
constant series divides by zero: measured before the check existed, a flat
signal reported `recurrence_rate = -0.000977517` — a negative share of cells,
which reached a dashboard caption. It is refused with a sentence, not analysed
into a NaN.

Both steps normalise through one `series.normalise`. They used to do it two
ways — one divided by `np.std(x)`, the other by `np.std(x) + 1e-6` — which does
not move DET or RR, because the threshold is a percentile and the analysis is
scale-free, but does move the stored `threshold`, so the two steps' thresholds
were not comparable.

A pairwise analysis interpolates both series onto one grid at the **finer** of
the two sampling intervals, so a 10 Hz series paired with a 100 Hz one produces
a 100 Hz grid — ten times the points, a hundred times the matrix, and no added
information. The length guard therefore applies to the **common grid**, not to
either input.

## A2 — One file format

**JSON, with base64 little-endian typed arrays for anything large.** No `.npz`
anywhere. Every array field is either a plain JSON list — small, and something
a person opens the file to read — or an object naming its encoding:

```jsonc
{"encoding": "bitmap-b64", "rows": 500, "cols": 500, "data": "…"}
{"encoding": "f32-b64",    "shape": [128, 3026],      "data": "…"}
```

The `encoding` field is the design. A reader that meets one it does not know
**says so by name**; a format that changed silently is how a tab ends up
drawing an empty panel with nothing in the log. One decoder in Python
(`common/arrays.py`), one in JavaScript (`DIMS.decodeArray`), tested against
each other with vectors the Python side produced.

There used to be two artifacts per analysis, and measured file by file the
second one mostly held nothing the first did not:

| | what the `.npz` uniquely held | verdict |
|---|---|---|
| RQA | `time` + `signal`, byte-identical to the source CSV after the documented cleaning; windowed metrics that duplicate the JSON's exactly | redundant |
| cRQA | the prepared signals on the common grid; metrics duplicated | nearly redundant |
| cross-wavelet | coherence, power and phase at 6× the time resolution | the real thing |

Meanwhile the assets contract told readers "**Analyse from the `.npz`**" —
pointing them, for RQA, at the file holding *less*.

A recurrence matrix is a **bitmap**, one bit per cell, not a list of
`[row, col]` pairs. Pairs cost about ten bytes per recurrent cell; a bitmap
costs one bit per cell whatever the density. Measured on one ORTHO gaze matrix:
**7,300,452 bytes as pairs against 133,803 as a bitmap, 54.6×**. Sparse only
wins below about 1.2 % density, and RQA targets 7 % while ORTHO's gaze channels
run 63–89 %.

**Nothing derived is stored.** `sig95_xwt` — joint power divided by its own
per-scale level, broadcast across time — was a third full grid holding the
quotient of two fields already in the file, and a quarter of the full-resolution
output. A reader divides.

The measured cost, stated rather than glossed. On the reference study:

| | before | after | |
|---|---|---|---|
| RQA (JSON + `.npz`) | 781,681 | 207,459 | **3.8× smaller** |
| cRQA | 309,186 | 137,937 | **2.2× smaller** |
| cross-wavelet, what a page fetches | 4,881,299 | 2,238,164 | **2.2× smaller** |
| cross-wavelet, full resolution | 6,979,924 | 12,721,453 | **1.8× larger** |

The last row is the price: base64 float32 against a deflate-compressed `.npz`.
It is paid by the file a browser never fetches, and it buys one format with one
decoder and one schema. A study that does not want it sets
`analysis.crosswavelet.saveFullResolution: false`.

## A3 — Two resolutions, and only where the second has content

Same schema, two files:

- `{video}_{analysis}_data.json` — reduced, what the browser fetches
- `{video}_crosswavelet_full.json` — full resolution

They differ **only** in the time axis; field names and schema are identical, so
one reader serves both, and a notebook written against the payload does not
break on the file it is supposed to prefer.

**Only cross-wavelet gets the second file**, and that is measured rather than
assumed: only there are the large fields two-dimensional (128 × 3026 against
128 × 504 drawn). Everything in a recurrence result except the matrix is
one-dimensional and small — a 6,000-point signal is 24 kB as float32 — so the
full-resolution signal travels in the single file, and there is nothing a second
one could hold.

**The recurrence matrix is not stored at any resolution.** It is quadratic:
3,000 points bit-packed is 1.1 MB, but 58,000 is 420 MB. The signal and the
threshold are stored, and the matrix is one `cdist` away.

Every payload carries `payload_version`, and it is not decoration.

A tab checks it before drawing and, when it cannot read the file, says which
core wrote it and what to run — an older asset says "rebuild", a newer one says
"update the vendored core", because those are opposite fixes. A blank panel is
indistinguishable from a study with no data, and that is the failure this
release most wants nobody to find by looking at a dashboard.

The merge honours it too. `write_payload` preserves entries an incoming run did
not rewrite — that is what keeps a study-owned analysis alive across a run of a
shared step — but **nothing is merged across a version change**, because an
entry nothing rewrote is one the new reader cannot read. Found by rebuilding
ORTHO: four of twelve recordings came out stamped v2 while holding v1 entries.
What is dropped is named.

A payload with **no** version written into a file that has one is **refused**,
not merged. Otherwise a study-owned step that forgot the field would drop every
entry already in the file, including analyses it did not produce — turning one
missing line into the silent loss that merging exists to prevent.

## A4 — Reduction is recorded, and a cap is a cap

Everything a browser draws is reduced, and the reduction is part of the result:
factor, method, the full length it came from, and the recurrence rate both
before and after.

`n // factor <= max_points`, and the two words matter. `factor_for`
floor-divided, so 999 points against a cap of 500 gave a factor of 1 and drew
all 999 — anything between the cap and twice the cap was not reduced at all,
which is quadratic in a recurrence plot. The same defect existed a second time,
inside the cross-wavelet step, which computed its own factors.

Budgets, in drawn elements: a recurrence plot at most **500 × 500**, a
cross-wavelet picture at most **500 × 100**.

`rate_full` and `rate_drawn` are both recorded because they can differ: on a
very sparse matrix, reproducing the rate exactly would reduce a recurrent line
to a couple of dots. The picture must never silently contradict the number
printed beside it.

## A5 — The window is a parameter of the result

DET, LAM, RR and L_MAX are shares of the structure inside one window, and every
one of them moves with how long that window is. So a windowed analysis records
`window`: the length and step **asked for**, the length and step **used**, the
number of windows, and a sentence when they differ.

They differ often. A 20 s window does not fit twice in a 20.48 s recording, and
one trivial window renders a blank chart, so it is shortened — correctly, and
until this contract existed, silently: 20 s and 1 s requested, 10.24 s and 0.5 s
used, nothing said. Two recordings of different lengths were then analysed at
different window lengths and their metric series compared as if they were not.

The placement is decided **in seconds**, and sample indices derived from times.
Doing it in samples made the reported time axis move with the sampling rate: the
same 2 s sine at 50 Hz and 100 Hz produced steps of 0.5 s and 0.51 s and last
window centres of 15.12 s and 15.32 s. A unit error like that is invisible on
real data, because every number stays plausible.

One implementation: `common/window.py`, used by both recurrence steps.

## A6 — Asked-for and achieved are both recorded

Wherever an analysis aims at something it may not hit, the payload carries both
numbers and a warning when they are far apart.

- **Recurrence rate.** The threshold is a percentile of the distance matrix, so
  a signal with many exactly-equal distances lands on a plateau and the target
  cannot be reached. That is common in real data — a game piece at rest, a
  quantised sensor — and it went unrecorded: an ORTHO series reached 12.7 %
  against a 7 % target in silence, and a four-level quantised signal reaches
  33.7 %. DET and LAM depend strongly on the rate, so two recordings analysed at
  materially different rates are not comparable, and that is a fact about the
  data rather than an error: it is reported, not raised.
- **The window**, as A5 describes.
- **`mcCount`**, so a study computed partly at 100 surrogates and partly at 300
  cannot be silently inconsistent.
- **The core version that produced the file**, in `provenance`.

Rounding is uniform. Every payload passes through `round_payload` and carries a
`precision` block; a study-owned step that skips it produces a file whose stated
precision is not its actual precision.

## A7 — A stated compute budget

`analysis.crosswavelet.mcCount` is the number of Monte Carlo surrogates behind
the coherence null. 300 is the publication setting; the whole ORTHO study at
that setting is **~2.8 hours**, and the bottleneck is a Python double loop
inside `pycwt.wct_significance` — 6.9M `numpy.ma.__getitem__` calls per six
surrogates — not the wavelet mathematics. Rewriting a published numerical
routine is out of scope; running independent pairs concurrently is not.

`--jobs` does that, defaulting to one process per core. **Serial and parallel
output must be byte-identical**, and that is the acceptance check rather than a
hope: the null is seeded on its own parameters rather than drawn from a shared
stream, and results are collected in the order the pairs were listed rather than
as they finish, because a payload is a dict written in insertion order. Measured
on the reference study with a cold null cache, ten cores, seven pairs: **95.3 s
serially against 37.1 s in parallel**, byte for byte the same file.

## A8 — What is computed is shown, or it is not computed

A system can sit in a third state — paying for something nobody reads — and
nothing says so. The coherence null was exactly that: every study computed it,
and one tab in one study read it.

The rule: **the Monte Carlo is available to every study, and its default
follows from what the study contains.**

- `analysis.crosswavelet.mcCount` works in any case repository. Anyone who
  wants to display or work with coherence elsewhere turns it on; nothing about
  the pipeline has to change for them.
- **Default 100** when the config enables something that reads `sig95_wtc` —
  today that is `include_network`. **Default 0 otherwise**, skipping the
  simulation entirely.
- An explicit `mcCount` always wins, in both directions.
- The step **says which it chose and why**, and records the choice in the
  payload per A6, so it is visible after the fact and not only in a log nobody
  kept.
- A tab that wants `sig95_wtc` and does not find it **says so** — "this output
  was built without a coherence null; set `analysis.crosswavelet.mcCount` and
  rebuild" — rather than drawing nothing. That is what keeps the default safe
  when someone adds such a tab later.

## A9 — Significance levels are the published ones

The cross-wavelet spectrum is the square root of a product of two chi-squares
(Torrence & Compo 1998, eq. 30), **not** a chi-square. All three significance
levels used the chi-square anyway, and evaluated the background at the mean of
the two AR(1) coefficients rather than combining the two series' own spectra.
Measured: the local level was 1.50× too high with matched coefficients and 2.39×
at α = (0.95, 0.2); the time-averaged 1.32–1.37×; the scale-averaged 1.267×.

One implementation, `common/tc98.py`, with the equation number beside each
formula and the paper itself in `examples/reference/`. Its transcription is
tested against the two values the paper prints (Z₁ = 2.182, Z₂ = 3.999) and
against `pycwt` under substitution — put the chi-square back and hand it one
spectrum twice, and it must reproduce `pycwt.significance` exactly.

`examples/reference/TORRENCE_COMPO.md` transcribes every constant used, with
its table and equation number, so a reader can check the transcription rather
than trust it.

---

## Acceptance

- `python -m pytest examples/reference/tests -q -rs` is green, and every skip is
  one you meant. It is a **gate**: CI runs it, and the generated
  `core-update.yml` in every study runs it against a candidate release before
  offering the bump, because the analyses are not vendored — a study installs
  them from the core it pins.
- A 60,000-point series is refused with a message naming the limit, before
  anything is allocated.
- `tests/baseline.json` pins every number these analyses produce. When it moves,
  the commit says which numbers moved and why.
