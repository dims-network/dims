#!/usr/bin/env python3
"""Write a copy of the builder's example study to a folder.

The wizard generates ConvoConnect-Mini on demand and caches it, so nothing is
committed and this script is not needed to use the builder. It is here for the
two jobs that want the files on disk: looking at them, and proving that the
generator is deterministic.

    python tools/make_builder_samples.py --out ./example-study
    python tools/make_builder_samples.py --check     # generate twice, diff
"""
from __future__ import annotations

import argparse
import filecmp
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "apps", "builder"))

from dims_builder import example_study  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", help="folder to write into")
    ap.add_argument("--check", action="store_true",
                    help="generate twice into temp folders and diff them")
    args = ap.parse_args(argv)

    if args.check:
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            example_study.generate(a)
            example_study.generate(b)
            here, there = example_study.data_files(a), example_study.data_files(b)
            if here != there:
                print("file list differs")
                print("  first :", here)
                print("  second:", there)
                return 1
            match, mismatch, errors = filecmp.cmpfiles(a, b, here, shallow=False)
            if mismatch or errors:
                print("content differs:", sorted(mismatch + errors))
                return 1
            print(f"{len(match)} files, byte-identical across two runs")
            return 0

    if not args.out:
        ap.error("give --out DIR, or --check")
    example_study.generate(args.out)
    files = example_study.data_files(args.out)
    total = sum(os.path.getsize(os.path.join(args.out, n)) for n in files)
    print(f"{len(files)} files, {total / 1e6:.1f} MB in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
