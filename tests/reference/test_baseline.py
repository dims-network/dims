"""Every number the analyses currently produce, pinned.

The other tests here check properties: DET agrees with its definition, the lag
is where it was put, unrelated signals beat chance 5 % of the time. All of them
survive a change that shifts every value a little, because the properties still
hold. **This is the one that does not.**

It exists for the work coming next -- parallelising the Monte Carlo, and
replacing the payload format -- both of which are supposed to change *how* an
answer is stored and computed while leaving the answer alone. That is exactly
the class of change where a quiet numeric drift is invisible.

Values come from `summary.py`, which reads meaning rather than bytes, so a
format change moves that file and leaves `baseline.json` untouched.

**When this fails, do not regenerate.** Look at which number moved and by how
much, decide whether the new value is better, and only then run
`python tests/reference/make_baseline.py` -- saying in the commit why each number moved.
Regenerating first is how a regression becomes the new normal.
"""
from __future__ import annotations

import json
import os

import pytest

from summary import coherence_summary, recurrence_summary

HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, "baseline.json")) as _fh:
    BASELINE = json.load(_fh)

#: Deterministic given the input: a threshold is a percentile, a rate is a
#: count. These should reproduce exactly; the tolerance is for float formatting.
EXACT = 1e-6

#: Derived from the seeded Monte Carlo. Reproducible on one machine, but pycwt
#: and numpy are free to reorder floating-point work between versions, so this
#: is loose enough to survive that and tight enough that a real change in the
#: null -- which moves the level by ~0.04 when unseeded -- still fails.
SIMULATED = 0.02
SIMULATED_FIELDS = {"wtc_signif_fraction", "mean_sig95_wtc", "n_unusable_levels"}

ANALYSES = (("rqa", "rqa_data", recurrence_summary),
            ("crqa", "crqa_data", recurrence_summary),
            ("crosswavelet", "crosswavelet_pairs", coherence_summary))


def payload(study, analysis):
    path = os.path.join(study, "assets", analysis,
                        f"reference_{analysis}_data.json")
    with open(path) as fh:
        return json.load(fh)


def compare(name, field, expected, actual):
    if expected is None or isinstance(expected, bool):
        assert actual == expected, f"{name}.{field}: {expected!r} -> {actual!r}"
        return
    if isinstance(expected, list):
        assert actual == expected, (
            f"{name}.{field} changed shape: {expected} -> {actual}")
        return
    if isinstance(expected, str):
        assert actual == expected, f"{name}.{field}: {expected!r} -> {actual!r}"
        return

    tolerance = SIMULATED if field in SIMULATED_FIELDS else EXACT
    assert actual is not None, f"{name}.{field} disappeared (was {expected})"
    difference = abs(float(actual) - float(expected))
    assert difference <= tolerance, (
        f"{name}.{field}: {expected} -> {actual}  (moved {difference:.3g}, "
        f"tolerance {tolerance})")


@pytest.mark.parametrize("analysis,container,summarise", ANALYSES,
                         ids=[a[0] for a in ANALYSES])
def test_the_numbers_have_not_moved(recurrence, coherence_study,
                                    analysis, container, summarise):
    study = (coherence_study if analysis == "crosswavelet" else recurrence)[0]
    expected_all = BASELINE[analysis]["entries"]
    actual_payload = payload(study, analysis)

    assert set(actual_payload[container]) >= set(expected_all), (
        f"{analysis} lost entries: "
        f"{sorted(set(expected_all) - set(actual_payload[container]))}")

    for name, expected in sorted(expected_all.items()):
        actual = summarise(actual_payload[container][name])
        for field, value in sorted(expected.items()):
            compare(f"{analysis}/{name}", field, value, actual.get(field))


@pytest.mark.parametrize("analysis", [a[0] for a in ANALYSES])
def test_the_provenance_has_not_moved(recurrence, coherence_study, analysis):
    """A change to what produced a file is as much a change as a moved number,
    and easier to make by accident -- a default flipping, a version not bumped."""
    study = (coherence_study if analysis == "crosswavelet" else recurrence)[0]
    expected = BASELINE[analysis]["provenance"]
    actual = payload(study, analysis).get("provenance")
    for field, value in sorted(expected.items()):
        if field == "core_version":
            continue                    # moves with every release, on purpose
        assert actual.get(field) == value, (
            f"{analysis} provenance {field}: {value!r} -> {actual.get(field)!r}")
