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
