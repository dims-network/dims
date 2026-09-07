#!/usr/bin/env python3
"""Write the reference study: synthetic signals whose answers are known.

    python examples/reference/make_reference_study.py

Every other test in this repository asks "did it crash?". On real data that is
all you can ask: `DET = 0.2571` is a number nobody can check. These signals are
chosen so that the answer is known before anything runs — a sine at a fixed
period recurs at that period, a lagged copy of it puts its cross-recurrence
line at exactly that lag, and two independent noises exceed a 95 % chance level
in 5 % of cells by construction.

The data is generated rather than committed, so producing it is the same
from-zero path a study takes, and so the repository does not carry a megabyte
of CSV that a formula describes exactly.

What each signal is for, and the expectation it supports, is in
`docs/contracts/analysis-output.md`. The assertions themselves are
`packages/dims-analysis/tests/test_reference_study.py`.
"""
from __future__ import annotations

import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

# 20.48 s at 50 Hz. Long enough for ten whole cycles of the 2 s component and
# for a windowed metric to have something to slide over; short enough that the
# whole study rebuilds in seconds, which is what makes it usable while
# iterating.
N = 1024
DT = 0.02
PERIOD = 2.0          # seconds; the sine's period, and what RQA must recover
LAG = 0.4             # seconds; 20 samples at DT, and what cRQA must recover
AR1_ALPHA = 0.9
SEED_A, SEED_B = 20260907, 20260908


def time_axis() -> np.ndarray:
    return np.arange(N) * DT


def ar1(alpha: float, seed: int) -> np.ndarray:
    """Red noise: what human movement looks like statistically, and what the
    coherence null is built from. Seeded, so the known answers stay known."""
    rng = np.random.default_rng(seed)
    x = np.zeros(N)
    for i in range(1, N):
        x[i] = alpha * x[i - 1] + rng.standard_normal()
    return (x - x.mean()) / x.std()


def signals() -> dict[str, np.ndarray]:
    t = time_axis()
    f = 1.0 / PERIOD
    sine = np.sin(2 * np.pi * f * t)
    return {
        # Periodic structure at a known spacing: RQA's diagonals must be
        # PERIOD apart, and DET must be near 1.
        "sine": sine,
        # The same signal delayed by exactly LAG. The cross-recurrence line
        # therefore sits LAG off the diagonal -- which is precisely the
        # structure a striding reduction deletes, and the phase difference is
        # 2*pi*f*LAG.
        "sine_lagged": np.sin(2 * np.pi * f * (t - LAG)),
        # A known *absence* of relationship. Two of them, independent, so the
        # fraction of coherence cells above a 95 % level must come out at 0.05.
        "noise_a": ar1(AR1_ALPHA, SEED_A),
        "noise_b": ar1(AR1_ALPHA, SEED_B),
        # Zero variance. Normalisation divides by the standard deviation, and
        # `rqa.py` does it with no guard, so this is the case that currently
        # produces NaN throughout and an empty matrix reported as a result.
        "flat": np.ones(N),
        # Four levels, so a great many distances are exactly equal and the
        # threshold search cannot land on a 7 % recurrence rate. ORTHO has this
        # for real -- a piece at rest gives ties -- and reaches 12.7 % against
        # a 7 % target with nothing said about it.
        "quantised": np.round(sine * 1.5) / 1.5,
    }


def write_series(directory: str, name: str, values: np.ndarray) -> str:
    path = os.path.join(directory, f"reference_{name}.csv")
    t = time_axis()
    with open(path, "w") as fh:
        fh.write("Time,value\n")
        for ti, vi in zip(t, values):
            fh.write(f"{ti:.4f},{vi:.10f}\n")
    return path


def config() -> dict:
    return {
        "title": "DIMS reference study",
        "subtitle": "Synthetic signals with known answers",
        "videoIDs": ["reference"],
        "dataTypes": {"reference": sorted(signals())},
        "include_RQA": ["sine", "noise_a", "quantised", "flat"],
        "include_cRQA": [["sine", "sine_lagged"]],
        "include_crosswavelet": [["sine", "sine_lagged"], ["noise_a", "noise_b"]],
        "analysis": {
            "crosswavelet": {
                # Set explicitly, and this study is the first user of that
                # escape hatch: there is no tab here that reads the coherence
                # null, so the default would skip it -- and the null is exactly
                # what one of the known answers tests. 20 surrogates is enough
                # to show the fraction lands near 0.05 and fast enough to run
                # on every change.
                "mcCount": 20,
            }
        },
        "defaultWindowSize": 5,
    }


def main() -> None:
    assets = os.path.join(HERE, "assets", "timeseries")
    os.makedirs(assets, exist_ok=True)

    written = []
    for name, values in sorted(signals().items()):
        written.append(os.path.basename(write_series(assets, name, values)))

    with open(os.path.join(HERE, "config.json"), "w") as fh:
        json.dump(config(), fh, indent=2)
        fh.write("\n")

    print(f"reference study in {HERE}")
    print(f"  {N} samples at {DT} s = {N * DT:.2f} s")
    print(f"  sine period {PERIOD} s = {int(round(PERIOD / DT))} samples")
    print(f"  lag {LAG} s = {int(round(LAG / DT))} samples")
    for name in written:
        print(f"  {name}")
    print("\nbuild it:  python build_assets.py")


if __name__ == "__main__":
    main()
