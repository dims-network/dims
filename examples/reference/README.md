# The reference study

Synthetic signals whose answers are known before anything runs.

```sh
python make_reference_study.py     # writes config.json and assets/timeseries/
python -m dims_analysis.cli run --config config.json
```

Everywhere else in this project a check can only ask "did it crash?". On real
data that is all that is available: `DET = 0.2571` is a number nobody can
verify. Here the answer is arithmetic — a sine at a 2 s period recurs every
2 s, a copy delayed 0.4 s puts its cross-recurrence line 0.4 s off the
diagonal, and two independent red noises exceed a 95 % chance level in 5 % of
cells by construction.

| signal | what it is for |
|---|---|
| `sine` | periodic structure at a known spacing |
| `sine_lagged` | the same, delayed 0.4 s — a known lag and a known phase |
| `noise_a`, `noise_b` | independent AR(1), a known *absence* of relationship |
| `flat` | zero variance — the degenerate case |
| `quantised` | many equal distances, so a 7 % target cannot be met |
| `sine_x10` | the same sine, ten times larger — every analysis normalises, so nothing may change |
| `sine_2x` | the same 2 s sine over the same 20.48 s, sampled twice as fast |
| `eff_hand_l`, `eff_hand_r`, `eff_other` | three effectors: the first two share 70 % of their variation, the third shares none |

The three effectors carry the structure a cross-effector network exists to
find, and deliberately the shape of the real Karnatak result — within-person
coupling real, between-person at chance. Measured: 0.75 of cells above chance
for the coupled pair, 0.04 and 0.08 for the other two. One solid edge, two
dashed.

Coupling is made by **sharing a red-noise component**, not by adding a
sinusoid, and that choice is itself a finding. A first attempt shared a 3 s
sine: the coupled pair read 1.00 above chance inside that band, but so did the
*unrelated* pairs at 0.30 and 0.42. The AR(1) null assumes both signals are red
noise, and a signal carrying a deterministic rhythm is not — so the null
understates its level and independence stops looking like independence.

The data is generated rather than committed: producing it is the same
from-zero path a real study takes, and a formula describes it exactly, so
carrying a megabyte of CSV would only add something to drift.

The assertions live beside the data, one file per analysis:

| | |
|---|---|
| `tests/test_rqa.py` | recurrence, determinism, the achieved rate, a constant signal |
| `tests/test_crqa.py` | the known lag, 20 samples off the diagonal |
| `tests/test_crosswavelet.py` | the known phase, the chance level, and the Monte Carlo that produces it |
| `tests/test_network.py` | what the cross-effector network needs from a payload, and how it breaks |
| `tests/test_metrics.py` | RR, DET, LAM and L_MAX, for **both** RQA and cross-RQA, against pyrqa |
| `tests/test_coherence_metrics.py` | cross-wavelet: the scale axis, amplitude invariance, and the signature of the defect this project was rebuilt around |
| `tests/test_determinism.py` | two runs give identical output; one step does not erase another |
| `tests/test_baseline.py` | every number, pinned against `baseline.json` |

## Running them while changing things

```sh
cd dims
python -m pytest examples/reference -q          # 42 tests, about 6 s
```

Two kinds, and both are needed.

The first four files check **properties**: DET agrees with its own definition
and with pyrqa, the cross-recurrence line sits at the lag that was put in, the
phase is 2·π·f·τ, unrelated signals beat chance 5 % of the time. A property
survives a change that shifts every value slightly — which is exactly what a
refactor of how something is stored or computed can do.

`test_baseline.py` is the one that does not. It pins every number the analyses
currently produce, through `summary.py`, which reads **meaning rather than
bytes** — so replacing the payload format moves that one file and leaves the
expected values alone.

Checked by sabotage, three ways:

| what was broken | what the baseline said |
|---|---|
| reduction back to striding | `rqa/noise_a.rate_drawn: 0.0709746 → 0.0735611` |
| recurrence target 7 % → 8 % | `mean_DET: 0.300346 → 0.340744`, and the provenance directly |
| phase averaged as a scalar | `mean_phase_rad: 0.003938 → 0.002944` |

**When the baseline fails, do not regenerate it.** Look at which number moved
and by how much, decide whether the new value is better, and only then run
`python tests/make_baseline.py` — saying in the commit why each number moved.
Regenerating first is how a regression becomes the new normal.

The cross-wavelet file tests the simulation two ways, and both are needed. That
it is **calibrated** — signals drawn from the null exceed the 95 % level in 5 %
of cells — and that it is **computed**: the level rises at both ends of the
scale range, where fewer independent cycles fit, so a stub returning a
plausible constant fails. Checked: a constant passes the calibration tests and
fails the shape test.

Each names the defect it would have caught. Two are `xfail(strict=True)` today — they are the
specification for work that has not landed yet, and strictness means they fail
the moment they start passing, so a fix cannot go unnoticed.

Requirements this study exists to check: `docs/contracts/analysis-output.md`.


## What these tests have found so far

Not hypothetical: each of these was live in the shipped code when the reference
study was built, and each was found by giving the analyses data whose answer
was already known.

| found | what it was |
|---|---|
| `recurrence_rate = -0.000977517` | a constant signal normalised to NaN, so the matrix came out empty and the line of identity was subtracted from zero. A negative share of cells, on a dashboard caption. |
| `LAM = 1.0137` | a share of points above 1. The diagonal and vertical line scans ignore different things, so they cannot share a denominator — fixing DET's had inflated LAM's. pyrqa said which of the two values was right. |
| 33.7 % against a 7 % target | a quantised signal puts the threshold percentile on a plateau. Recorded now, with a warning that DET and LAM are not comparable across different achieved rates. |
| the cross-wavelet cap | 1024 samples against a 500-point cap drew 512 — the step computed its own reduction factors by floor division. |
| `numpy.randn` | pycwt's red-noise generator branches at exactly zero autocorrelation and calls a function removed in NumPy 2, so white noise silently lost its chance level. |

Three things were also measured and turned out **not** to be defects, which is
the other half of the value: DET on a pure sine is 0.899 and not ~1.0; the
coherence chance level barely responds to how red the noise is; and the fraction
of cells above that level is 0.05 only when the cone of influence is excluded —
including it gives 0.126.
