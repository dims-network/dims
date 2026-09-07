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

The data is generated rather than committed: producing it is the same
from-zero path a real study takes, and a formula describes it exactly, so
carrying a megabyte of CSV would only add something to drift.

The assertions live in
`packages/dims-analysis/tests/test_reference_study.py`, and each names the
defect it would have caught. Two are `xfail(strict=True)` today — they are the
specification for work that has not landed yet, and strictness means they fail
the moment they start passing, so a fix cannot go unnoticed.

Requirements this study exists to check: `docs/contracts/analysis-output.md`.
