#!/usr/bin/env python3
"""Record what the analyses currently answer, so a change that moves a number
is caught rather than assumed away.

    python tests/reference/make_baseline.py   # rewrite tests/reference/baseline.json

The other tests here check *properties* -- that DET matches its definition,
that the lag is where it was put, that unrelated signals beat chance 5 % of the
time. Those survive a change that shifts every value slightly, because the
properties still hold. This catches that.

Run it deliberately, never automatically: regenerating the baseline is how a
regression becomes the new normal. The workflow is

  1. make a change
  2. run the tests; if the baseline test fails, look at the diff
  3. decide whether the new numbers are better or worse
  4. only if better: regenerate, and say in the commit why each number moved

Numbers come from `summary.py`, which reads meaning rather than bytes -- so the
format change in the next step moves that file and leaves these values alone.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
#: The reference study, which lives in `examples/` because it *is* a study --
#: `serve.py` it and open it in a browser. This pointed at `tests/` instead,
#: from before the suite and the study were separated, so `build()` looked for
#: a generator that is not there and this script could not be run at all.
#: `conftest.py` computes the same path; the two must agree.
STUDY = os.path.join(ROOT, "examples", "reference")
BASELINE = os.path.join(HERE, "baseline.json")

sys.path.insert(0, HERE)
from summary import coherence_summary, recurrence_summary  # noqa: E402

ANALYSES = (("rqa", "rqa_data", recurrence_summary),
            ("crqa", "crqa_data", recurrence_summary),
            ("crosswavelet", "crosswavelet_pairs", coherence_summary))


def build(study: str) -> None:
    subprocess.run([sys.executable, os.path.join(study, "make_reference_study.py")],
                   check=True, capture_output=True)
    run = subprocess.run(
        [sys.executable, "-m", "dims_analysis.cli", "run", "--config", "config.json"],
        cwd=study, capture_output=True, text=True)
    if run.returncode != 0:
        sys.exit("the analyses failed:\n" + run.stdout[-4000:] + run.stderr[-4000:])


def collect(study: str) -> dict:
    out: dict = {}
    for analysis, container, summarise in ANALYSES:
        path = os.path.join(study, "assets", analysis,
                            f"reference_{analysis}_data.json")
        with open(path) as fh:
            payload = json.load(fh)
        out[analysis] = {
            "provenance": payload.get("provenance"),
            "entries": {name: summarise(entry)
                        for name, entry in sorted(payload[container].items())},
        }
    return out


def main() -> None:
    build(STUDY)
    baseline = collect(STUDY)
    with open(BASELINE, "w") as fh:
        json.dump(baseline, fh, indent=2, sort_keys=True)
        fh.write("\n")
    total = sum(len(a["entries"]) for a in baseline.values())
    print(f"wrote {os.path.relpath(BASELINE, ROOT)}: {total} entries across "
          f"{len(baseline)} analyses")


if __name__ == "__main__":
    main()
