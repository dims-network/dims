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
`docs/contracts/analysis-output.md`. The assertions are in `tests/reference/`,
one file per analysis -- they moved there so that building a temporary study
from this directory no longer copied the test suite into it.
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


#: How much of a coupled effector is the shared component, by amplitude. Two
#: effectors sharing this much of their variation are genuinely coupled; one
#: that shares none is not.
EFFECTOR_SHARED = 0.7


def _effector(seed: int, shared: float, shared_seed: int = 30) -> np.ndarray:
    """A movement-like signal: red noise, some of it shared with its partners.

    Coupling is created by **sharing a noise component**, not by adding a
    sinusoid, and the difference matters. The AR(1) null assumes both signals
    are red noise; a signal carrying a deterministic rhythm is not, so the null
    understates its level and even an unrelated partner reads as coupled.
    Measured on a first attempt that used a shared 3 s sinusoid: inside that
    band the genuinely coupled pair read 1.00 above chance, but the *unrelated*
    pairs read 0.30 and 0.42 -- against the 0.05 that independence should give.

    Sharing red noise keeps every signal the shape the null assumes, so the
    only thing separating a coupled pair from an uncoupled one is the coupling.
    """
    own = ar1(0.85, seed)
    if shared <= 0:
        return own
    common = ar1(0.85, shared_seed)
    mixed = shared * common + (1.0 - shared) * own
    return (mixed - mixed.mean()) / mixed.std()


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
        # The same signal, ten times larger. Every analysis here normalises by
        # the standard deviation, so the result must not move at all -- only
        # the distance threshold, which scales with it. A normalisation that
        # went missing would show up here and nowhere else.
        "sine_x10": sine * 10.0,
        # Three "effectors", with the coupling structure a cross-effector
        # network exists to find -- and deliberately the same shape as the real
        # Karnatak result: within-person coupling real, between-person at
        # chance. `hand_l` and `hand_r` share a rhythm, `other` does not, so a
        # correct network draws one solid edge and two dashed ones.
        "eff_hand_l": _effector(seed=31, shared=EFFECTOR_SHARED),
        "eff_hand_r": _effector(seed=32, shared=EFFECTOR_SHARED),
        "eff_other": _effector(seed=33, shared=0.0),
    }


def write_series(directory: str, name: str, values: np.ndarray,
                 t: np.ndarray | None = None) -> str:
    path = os.path.join(directory, f"reference_{name}.csv")
    t = time_axis() if t is None else t
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
        "dataTypes": {"reference": sorted(signals()) + ["sine_2x"]},
        "include_RQA": ["sine", "noise_a", "quantised", "flat",
                        "sine_x10", "sine_2x"],
        "include_cRQA": [
            ["sine", "sine_lagged"],
            # The contrast: no relationship to find. cRQA's metrics must
            # separate these as sharply as RQA's separate a sine from noise.
            ["noise_a", "noise_b"],
            # A signal against itself. Cross-recurrence has no line of identity
            # to exclude -- the two series are different by construction -- so
            # this is the case where that assumption is false, and it is worth
            # knowing what the metrics do with it.
            ["sine", "sine"],
        ],
        "include_crosswavelet": [
            ["sine", "sine_lagged"],
            ["noise_a", "noise_b"],
            # Every pair of the three effectors, which is what a cross-effector
            # network draws. One of the three is genuinely coupled.
            ["eff_hand_l", "eff_hand_r"],
            ["eff_hand_l", "eff_other"],
            ["eff_hand_r", "eff_other"],
            # A signal against itself: coherence must be 1 everywhere it is
            # defined. Degenerate, and the strongest single invariant the
            # measure has.
            ["sine", "sine"],
            # The same signal ten times larger. Coherence is
            # amplitude-normalised by construction, so this must be identical
            # to sine_vs_sine -- a normalisation that went missing shows up
            # here and nowhere else.
            ["sine", "sine_x10"],
        ],
        # The cross-effector network reads every pair of these. Its presence is
        # also what would switch the coherence null on by default, if mcCount
        # below did not already ask for it explicitly.
        "include_network": True,
        "analysis": {
            "crosswavelet": {
                # Set explicitly. `include_network` above would switch the
                # null on anyway, at the default 100; 20 is enough to show the
                # fraction lands near 0.05 and keeps the study fast enough to
                # run on every change. An explicit value winning over the
                # default is itself part of the contract.
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

    # The same 2 s sine over the same 20.48 s, sampled twice as fast. What an
    # analysis reports in *seconds* must not depend on the sampling rate; a
    # unit error is otherwise invisible, because every number stays plausible.
    fast_t = np.arange(N * 2) * (DT / 2)
    fast = np.sin(2 * np.pi * (1.0 / PERIOD) * fast_t)
    written.append(os.path.basename(
        write_series(assets, "sine_2x", fast, t=fast_t)))

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
