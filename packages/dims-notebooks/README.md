# dims-notebooks

Sanity checks for a DIMS study, as notebooks you can run against any case.

```sh
pip install -e "../..[notebooks]"
jupyter lab            # then set STUDY at the top of a notebook
```

| Notebook | Answers |
|---|---|
| `01-signal-sanity.ipynb` | Is the sampling rate what you think? Are there gaps, drift, a flatlined channel? Does the series span its video? |
| `02-coherence-diagnostics.ipynb` | Is this coherence measuring coupling, or measuring power? Is any of it above the null? |

## Why this exists

The wavelet coherence defect that shipped to five repositories for months was
found by a notebook. It was not a crash — the field looked plausible and was
wrong, so only numbers found it. Had a check like this been part of the core and
run routinely, it would not have shipped.

So the checks live in `dims_checks/`, not inside the notebooks: they are tested,
and each test constructs the failure it is meant to catch. A diagnostic that
never fires is decoration.

```python
from dims_checks.signals import study_report
from dims_checks.coherence import study_coherence_report

for r in study_coherence_report("../case-demo"):
    for w in r.get("warnings", []):
        print(r["pair"], w)
```

## Reading a coherence value

Coherence does not sit at zero when two signals are unrelated. It is a ratio
over a smoothing neighbourhood, so random phase relationships still average to
around **0.25**. Compare against `sig95_wtc`, the 95% AR(1) null, which
typically lands near 0.59.

`significant_fraction` near **0.05** means no coupling was detected — under
independence that number is 0.05 by construction, however respectable the mean
coherence looks.
