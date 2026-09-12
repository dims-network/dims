#!/usr/bin/env python3
"""Build the payloads the Analyses pages plot, by running the real analyses.

The figures on those pages are not drawings of what DIMS does. They are the
output of `dims-analysis run` over synthetic signals whose answers are known in
advance, copied here byte for byte, so a page cannot describe a field the code
does not write or a shape it does not produce. When the analyses change, this is
re-run and the figures change with them.

Nothing here is trimmed after the fact. The reduction in these files is the
step's own: `maxTimePoints`/`maxFreqPoints` for the cross-wavelet grids, and the
500-point cap for the recurrence matrices. That is deliberate -- a reader
inspecting `demo/crosswavelet.json` is looking at exactly the object a study
gets in `assets/crosswavelet/`.

    python docs/analyses/demo/make_demo_data.py

Run it against the pinned dependencies (`pycwt==0.5.0b0`), not whatever the
working copy happens to have installed; the significance levels move with pycwt.
Everything is seeded, so two runs produce identical files.

Writes, beside this script:

    demo_signals.json      the six synthetic inputs, for the "what went in" figures
    demo_crosswavelet.json assets/crosswavelet/demo_crosswavelet_data.json, verbatim
    demo_rqa.json          assets/rqa/demo_rqa_data.json, verbatim
    demo_crqa.json         assets/crqa/demo_crqa_data.json, verbatim

The `demo_` prefix is not decoration: the renderer copies these next to the
generated pages, where `rqa.json` would sit beside `rqa.html`.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

SEED = 20250909
FS = 10.0                    # Hz
N = 600                      # samples -- 60 s, and 600/500 rounds the drawn
                             # recurrence matrix to a tidy 300x300
VIDEO = "demo"


def red_noise(n, phi, sigma, rng):
    """AR(1) noise: x[i] = phi*x[i-1] + e[i]. Human movement is very red."""
    e = rng.normal(0.0, sigma, n)
    x = np.empty(n)
    x[0] = e[0]
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


def taper(t, lo, hi, edge=2.0):
    """A raised-cosine envelope that is 1 on [lo, hi] and 0 outside it."""
    env = np.zeros_like(t)
    env[(t >= lo) & (t <= hi)] = 1.0
    rise = (t > lo - edge) & (t < lo)
    env[rise] = 0.5 * (1 - np.cos(np.pi * (t[rise] - (lo - edge)) / edge))
    fall = (t > hi) & (t < hi + edge)
    env[fall] = 0.5 * (1 + np.cos(np.pi * (t[fall] - hi) / edge))
    return env


def build_signals():
    """Six series, each built so its answer is known before the analysis runs.

    `sig_a` and `sig_b` are the running example on every page:

      * a 4 s oscillation in both, with `sig_b` delayed by 0.7 s -- a constant
        1.10 rad phase lag, so coherence at that period should be near 1 for the
        whole record and the phase arrows should all point the same way;
      * a burst between 20 s and 35 s in both, at 1.2 s in `sig_a` and 1.45 s in
        `sig_b` -- lots of joint energy, but the timing relationship drifts, so
        cross-wavelet *power* is high there while *coherence* is not. That pair
        is the whole point of having both fields;
      * independent AR(1) noise in each, which is what the chance level is
        estimated against.

    `periodic` and `noisy` are the two ends of the recurrence spectrum, for the
    comparison panel. `lead` and `lag` are the same signal 2 s apart, so the
    cross-recurrence plot has one line offset from the diagonal by exactly 2 s.
    """
    rng = np.random.default_rng(SEED)
    t = np.arange(N) / FS

    burst = taper(t, 20.0, 35.0)
    sig_a = (1.00 * np.sin(2 * np.pi * t / 4.0)
             + 0.90 * burst * np.sin(2 * np.pi * t / 1.20)
             + 0.45 * red_noise(N, 0.80, 0.5, rng))
    sig_b = (1.00 * np.sin(2 * np.pi * (t - 0.7) / 4.0)
             + 0.90 * burst * np.sin(2 * np.pi * t / 1.45 + 1.0)
             + 0.45 * red_noise(N, 0.80, 0.5, rng))

    periodic = np.sin(2 * np.pi * t / 3.0) + 0.05 * rng.normal(0, 1, N)
    noisy = red_noise(N, 0.85, 0.5, rng)

    def carrier(x):
        return np.sin(2 * np.pi * x / 5.0) + 0.60 * np.sin(2 * np.pi * x / 1.7)

    lead = carrier(t) + 0.30 * rng.normal(0, 1, N)
    lag = carrier(t - 2.0) + 0.30 * rng.normal(0, 1, N)

    return t, {"sig_a": sig_a, "sig_b": sig_b, "periodic": periodic,
               "noisy": noisy, "lead": lead, "lag": lag}


CONFIG = {
    "videoIDs": [VIDEO],
    "include_RQA": ["sig_a", "periodic", "noisy"],
    "include_cRQA": [["sig_a", "sig_b"], ["lead", "lag"]],
    "include_crosswavelet": [["sig_a", "sig_b"]],
    "analysis": {
        "rqa": {"window": 12.0, "step": 0.5, "targetRecurrence": 0.07},
        "crqa": {"window": 12.0, "step": 0.5, "targetRecurrence": 0.07},
        "crosswavelet": {
            # Small enough for a web page, large enough to read. The step does
            # the reduction, so what is committed here is what a study gets.
            "mcCount": 200,
            "maxTimePoints": 150,
            "maxFreqPoints": 48,
            "maxPeriod": 20.0,
            "saveFullResolution": False,
        },
    },
}


def write_project(root, t, series):
    ts_dir = os.path.join(root, "assets", "timeseries")
    os.makedirs(ts_dir, exist_ok=True)
    for name, values in series.items():
        path = os.path.join(ts_dir, f"{VIDEO}_{name}.csv")
        with open(path, "w") as fh:
            fh.write(f"Time,{name}\n")
            for ti, vi in zip(t, values):
                fh.write(f"{ti:.6f},{vi:.6f}\n")
    with open(os.path.join(root, "config.json"), "w") as fh:
        json.dump(CONFIG, fh, indent=2)


def versions():
    """What produced these files.

    pycwt is read from the installed distribution, not from `pycwt.__version__`:
    the sdist bakes in a stale setuptools-scm string, so the module reports
    0.4.0b1.dev10 while the package really is 0.5.0b0. Believing the module
    would report the wrong provenance for the significance levels.
    """
    from importlib.metadata import version
    import dims_analysis
    return {
        "dims_analysis": dims_analysis.__version__,
        "pycwt": version("pycwt"),
        "numpy": version("numpy"),
        "scipy": version("scipy"),
    }


def main():
    v = versions()
    if v["pycwt"] != "0.5.0b0":
        print(f"warning: pycwt is {v['pycwt']}, not the pinned 0.5.0b0; the "
              f"coherence chance level will not match a study's", file=sys.stderr)

    t, series = build_signals()
    root = tempfile.mkdtemp(prefix="dims-demo-")
    try:
        write_project(root, t, series)
        print(f"running the analyses in {root} (the Monte Carlo null takes a "
              f"few minutes)")
        result = subprocess.run(
            [sys.executable, "-m", "dims_analysis.cli", "run",
             "--config", os.path.join(root, "config.json")],
            cwd=root)
        if result.returncode != 0:
            sys.exit(f"error: dims-analysis exited {result.returncode}")

        for step, out in (("crosswavelet", "demo_crosswavelet.json"),
                          ("rqa", "demo_rqa.json"),
                          ("crqa", "demo_crqa.json")):
            src = os.path.join(root, "assets", step, f"{VIDEO}_{step}_data.json")
            shutil.copyfile(src, os.path.join(HERE, out))
            print(f"  wrote {out}  ({os.path.getsize(src) / 1024:.0f} KB)")
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # The inputs, for the figures that show what went in. Rounded to the six
    # significant figures the payloads use, so nothing here is more precise
    # than the analysis it feeds.
    signals = {
        "generated_with": v,
        "seed": SEED,
        "fs_hz": FS,
        "time": [round(float(x), 6) for x in t],
        "series": {k: [float(f"{x:.6g}") for x in vals]
                   for k, vals in series.items()},
    }
    with open(os.path.join(HERE, "demo_signals.json"), "w") as fh:
        json.dump(signals, fh, separators=(",", ":"))
        fh.write("\n")
    print("  wrote demo_signals.json")
    print("versions: " + ", ".join(f"{k} {val}" for k, val in v.items()))


if __name__ == "__main__":
    main()
