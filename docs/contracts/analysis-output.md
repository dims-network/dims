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

## A2 — Reduction is recorded, and a cap is a cap

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

## A3 — The window is a parameter of the result

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

## A4 — Asked-for and achieved are both recorded

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
- **The window**, as A3 describes.
- **`mcCount`**, so a study computed partly at 100 surrogates and partly at 300
  cannot be silently inconsistent.
- **The core version that produced the file**, in `provenance`.

Rounding is uniform. Every payload passes through `round_payload` and carries a
`precision` block; a study-owned step that skips it produces a file whose stated
precision is not its actual precision.

## A5 — A stated compute budget

`analysis.crosswavelet.mcCount` is the number of Monte Carlo surrogates behind
the coherence null. 300 is the publication setting; the whole ORTHO study at
that setting is **~2.8 hours**, and the bottleneck is a Python double loop
inside `pycwt.wct_significance`, not the wavelet mathematics. Rewriting a
published numerical routine is out of scope; running independent pairs
concurrently is not, and produces byte-identical output.

## A6 — What is computed is shown, or it is not computed

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
  payload per A4, so it is visible after the fact and not only in a log nobody
  kept.
- A tab that wants `sig95_wtc` and does not find it **says so** — "this output
  was built without a coherence null; set `analysis.crosswavelet.mcCount` and
  rebuild" — rather than drawing nothing. That is what keeps the default safe
  when someone adds such a tab later.

## A7 — Significance levels are the published ones

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
