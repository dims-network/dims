#!/usr/bin/env python3
"""Produce the analysis payloads the JavaScript tests read.

    python fixtures/generate.py

Written by running the **real** steps over short synthetic series, not by hand.
A hand-written fixture is a guess about the format, and a guess is exactly what
the seam between the Python analyses and the tabs did not need: the container
key for cross-wavelet output is `crosswavelet_pairs`, not `crosswavelet_data`,
and reading the wrong one returns nothing and raises nothing. A tab built
against a hand-written fixture would agree with the fixture and disagree with
the product.

Kept short deliberately -- 240 samples, one pair -- so the committed files stay
small. What matters is that every key a tab reads is present and has the shape
the analyses actually write.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
N, DT = 160, 0.05


def series(path, seed, lag=0):
    rng = np.random.default_rng(seed)
    t = np.arange(N) * DT
    base = np.sin(2 * np.pi * 0.6 * (t - lag * DT)) + 0.5 * np.sin(2 * np.pi * 1.7 * t)
    v = base + 0.25 * rng.standard_normal(N)
    with open(path, "w") as fh:
        fh.write("Time,value\n")
        for ti, vi in zip(t, v):
            fh.write(f"{ti:.4f},{vi:.6f}\n")


def main():
    work = tempfile.mkdtemp(prefix="dims_fixtures_")
    try:
        ts = os.path.join(work, "assets", "timeseries")
        os.makedirs(ts)
        series(os.path.join(ts, "s1_alpha.csv"), seed=11)
        series(os.path.join(ts, "s1_beta.csv"), seed=12, lag=6)

        config = {
            "title": "Fixture", "videoIDs": ["s1"],
            "dataTypes": {"s1": ["alpha", "beta"]},
            "include_RQA": ["alpha", "beta"],
            "include_cRQA": [["alpha", "beta"]],
            "include_crosswavelet": [["alpha", "beta"]],
            # A small picture on purpose: the fixture is committed, and what
            # these tests need is every key the tabs read in the shape the
            # analyses write, not a megabyte of it. These are the same knobs a
            # study uses to size its own payloads.
            # A small picture, and an explicit coherence null. Explicit
            # because this config enables nothing that reads `sig95_wtc`, so
            # the default is to skip the Monte Carlo -- which is the *other*
            # fixture below.
            "analysis": {"crosswavelet": {"maxTimePoints": 60,
                                          "maxFreqPoints": 24,
                                          "mcCount": 20}},
        }
        with open(os.path.join(work, "config.json"), "w") as fh:
            json.dump(config, fh, indent=2)

        run = subprocess.run(
            [sys.executable, "-m", "dims_analysis.cli", "run",
             "--config", "config.json"],
            cwd=work, capture_output=True, text=True)
        if run.returncode != 0:
            sys.exit("the analyses failed:\n" + run.stdout[-3000:] + run.stderr[-3000:])

        written = []
        for kind, name in (("rqa", "s1_rqa_data.json"),
                           ("crqa", "s1_crqa_data.json"),
                           ("crosswavelet", "s1_crosswavelet_data.json")):
            src = os.path.join(work, "assets", kind, name)
            if not os.path.exists(src):
                sys.exit(f"the {kind} step wrote nothing")
            dst = os.path.join(HERE, name)
            shutil.copyfile(src, dst)
            written.append((name, os.path.getsize(dst)))

        # And the same study with the coherence null skipped, which is what a
        # config with no consumer gets by default. Both states of that rule are
        # real payloads here, so the tab is tested against what it will meet
        # rather than against a fixture edited to look like it.
        without = json.loads(json.dumps(config))
        without["analysis"]["crosswavelet"]["mcCount"] = 0
        with open(os.path.join(work, "config.json"), "w") as fh:
            json.dump(without, fh, indent=2)
        shutil.rmtree(os.path.join(work, "assets", "crosswavelet"))
        run = subprocess.run(
            [sys.executable, "-m", "dims_analysis.cli", "run",
             "--config", "config.json", "--steps", "crosswavelet"],
            cwd=work, capture_output=True, text=True)
        if run.returncode != 0:
            sys.exit("the no-null run failed:\n" + run.stdout[-3000:] + run.stderr[-3000:])
        src = os.path.join(work, "assets", "crosswavelet", "s1_crosswavelet_data.json")
        dst = os.path.join(HERE, "s1_crosswavelet_no_null.json")
        shutil.copyfile(src, dst)
        written.append(("s1_crosswavelet_no_null.json", os.path.getsize(dst)))

        with open(os.path.join(HERE, "config.json"), "w") as fh:
            json.dump(config, fh, indent=2)
            fh.write("\n")
        for name, size in written:
            print(f"  {name}  {size / 1024:.0f} kB")
        print(f"written from dims_analysis into {HERE}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
