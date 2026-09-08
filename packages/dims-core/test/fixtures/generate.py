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


def effectors(directory):
    """Three measures with a coupling structure whose answer is known.

    `eff_a` and `eff_b` share most of a red-noise component; `eff_c` shares
    none. A correct network therefore draws one solid edge and two dashed ones,
    and that is the only test of what the network tab is *for*.

    Coupling by sharing red noise rather than by adding a shared sinusoid, and
    the difference is not cosmetic: the AR(1) null assumes both signals are red
    noise, so a signal carrying a deterministic rhythm breaks the assumption and
    even unrelated partners read as coupled. Measured on a first attempt that
    used a shared 3 s sine, the *unrelated* pairs read 0.30 and 0.42 above
    chance against the 0.05 independence should give.
    """
    def ar1(alpha, seed, n):
        rng = np.random.default_rng(seed)
        x = np.zeros(n)
        for i in range(1, n):
            x[i] = alpha * x[i - 1] + rng.standard_normal()
        return (x - x.mean()) / x.std()

    n = 512
    common = ar1(0.85, 30, n)
    for name, seed, shared in (("eff_a", 31, 0.7), ("eff_b", 32, 0.7),
                               ("eff_c", 33, 0.0)):
        own = ar1(0.85, seed, n)
        v = shared * common + (1 - shared) * own if shared else own
        v = (v - v.mean()) / v.std()
        with open(os.path.join(directory, f"s2_{name}.csv"), "w") as fh:
            fh.write("Time,value\n")
            for i, vi in enumerate(v):
                fh.write(f"{i * DT:.4f},{vi:.6f}\n")


def encodings():
    """Vectors for the browser decoder, packed by the Python side.

    A JS decoder tested against JS-made fixtures agrees with itself. These are
    produced by `common/arrays.py`, so the two implementations are checked
    against each other and not against a shared guess. The awkward widths are
    deliberate: a row whose width is not a multiple of eight ends in padding
    bits, and reading those back as recurrent cells is the packing bug worth
    catching.
    """
    from dims_analysis.common import arrays

    rng = np.random.default_rng(5)
    cases = []
    for rows, cols, density in ((8, 8, 0.5), (7, 13, 0.3), (3, 1, 1.0),
                                (5, 129, 0.07)):
        m = (rng.random((rows, cols)) < density).astype(int)
        cases.append({"kind": "bitmap", "packed": arrays.pack_bitmap(m),
                      "expected": m.tolist()})

    grids = [
        np.array([[1.0, -2.5], [0.0, 1234.5]]),
        np.array([0.5, 1.5, 2.5, 3.5]),
        np.array([[1.0, np.nan], [np.nan, -2.5]]),
    ]
    for g in grids:
        cases.append({
            "kind": "f32",
            "packed": arrays.pack_f32(g),
            # NaN travels as null, which is what the decoder must produce and
            # what Plotly reads as a gap.
            "expected": arrays.nan_to_none(g),
        })
    return cases


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

        # A second recording with three effectors, for the network tab.
        effectors(ts)
        network_config = {
            "title": "Fixture", "videoIDs": ["s2"],
            "dataTypes": {"s2": ["eff_a", "eff_b", "eff_c"]},
            "include_crosswavelet": [["eff_a", "eff_b"], ["eff_a", "eff_c"],
                                     ["eff_b", "eff_c"]],
            "include_network": {"groups": [{"match": "^eff", "label": "Effectors"}]},
            "analysis": {"crosswavelet": {"maxTimePoints": 60,
                                          "maxFreqPoints": 24,
                                          "mcCount": 20}},
        }
        with open(os.path.join(work, "config.json"), "w") as fh:
            json.dump(network_config, fh, indent=2)
        run = subprocess.run(
            [sys.executable, "-m", "dims_analysis.cli", "run",
             "--config", "config.json", "--steps", "crosswavelet"],
            cwd=work, capture_output=True, text=True)
        if run.returncode != 0:
            sys.exit("the network run failed:\n" + run.stdout[-3000:] + run.stderr[-3000:])
        src = os.path.join(work, "assets", "crosswavelet", "s2_crosswavelet_data.json")
        dst = os.path.join(HERE, "s2_crosswavelet_data.json")
        shutil.copyfile(src, dst)
        written.append(("s2_crosswavelet_data.json", os.path.getsize(dst)))
        with open(os.path.join(HERE, "network_config.json"), "w") as fh:
            json.dump(network_config, fh, indent=2)
            fh.write("\n")

        enc = os.path.join(HERE, "encodings.json")
        with open(enc, "w") as fh:
            json.dump(encodings(), fh, indent=2)
            fh.write("\n")
        written.append(("encodings.json", os.path.getsize(enc)))

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
