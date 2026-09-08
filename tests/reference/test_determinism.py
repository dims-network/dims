"""Two runs over the same input produce the same output.

`docs/contracts/step.md` states this as an acceptance check -- "running twice
over identical input produces byte-identical output" -- and nothing tested it.
It matters most right before the Monte Carlo is parallelised: work reordered
across processes is exactly the change that can perturb a floating-point sum or
consume a random stream in a different order, and the result would still look
entirely plausible.

Byte-identity is the strong form and the one worth having. Where it does not
hold, that is a finding, not a reason to loosen the test.
"""
from __future__ import annotations

import hashlib
import json
import os

import pytest

from conftest import build


def digest(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def outputs(study):
    """Every analysis file a run produced, by path relative to the study."""
    found = {}
    for analysis in ("rqa", "crqa", "crosswavelet"):
        directory = os.path.join(study, "assets", analysis)
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if name.startswith("."):
                continue
            found[f"{analysis}/{name}"] = os.path.join(directory, name)
    return found


#: Filled by the first fixture that builds, so the merge test can copy a study
#: instead of building its own.
REFERENCE_BUILD: list = []


@pytest.fixture(scope="module")
def two_runs(tmp_path_factory):
    """The same study built twice, independently, in two directories."""
    first, _ = build(tmp_path_factory, "rqa,crqa")
    second, _ = build(tmp_path_factory, "rqa,crqa")
    REFERENCE_BUILD[:] = [first]
    return first, second


def test_the_recurrence_analyses_are_byte_identical_across_runs(two_runs):
    first, second = two_runs
    a, b = outputs(first), outputs(second)
    assert set(a) == set(b), (
        f"the two runs produced different files: "
        f"{sorted(set(a) ^ set(b))}")
    differing = [name for name in sorted(a) if digest(a[name]) != digest(b[name])]
    assert not differing, (
        f"identical input, different output: {differing}. Something in these "
        f"analyses depends on more than the data -- a clock, a dict ordering, "
        f"an unseeded generator.")


def test_the_seeded_monte_carlo_is_identical_across_runs(tmp_path_factory):
    """The expensive half, and the one with an actual random stream in it.

    The seed exists because it was not reproducible: unseeded runs disagreed by
    up to 0.04 on the 95 % level, enough to move a borderline finding.
    """
    first, _ = build(tmp_path_factory, "crosswavelet")
    second, _ = build(tmp_path_factory, "crosswavelet")
    a = outputs(first)["crosswavelet/reference_crosswavelet_data.json"]
    b = outputs(second)["crosswavelet/reference_crosswavelet_data.json"]
    assert digest(a) == digest(b), (
        "two cross-wavelet runs over identical input differ. The Monte Carlo "
        "seed is what makes this reproducible; check it is still applied.")


def test_rerunning_one_step_does_not_erase_another(two_runs, tmp_path):
    """ORTHO's real failure, in miniature.

    `assets/rqa/{video}_rqa_data.json` is keyed by video, so a study-owned
    analysis writes its results into the same `rqa_data` dict as the shared
    step. Before merging existed, whichever ran second won -- and the loss was
    silent, because the file was still there and still valid.
    """
    import shutil

    from dims_analysis.common import results

    # A copy, never the session fixture: this test *writes* into the payload,
    # and the shared study is read by every other file. Mutating it made an
    # unrelated test fail on an entry with no `visualization` -- and only when
    # the whole suite ran, which is the worst way to find out.
    study = tmp_path / "study"
    shutil.copytree(REFERENCE_BUILD[0], study)
    path = os.path.join(study, "assets", "rqa", "reference_rqa_data.json")
    with open(path) as fh:
        before = json.load(fh)
    assert len(before["rqa_data"]) >= 2

    # A second analysis writes one new entry into the same file. It stamps the
    # payload version, as every step must: without it the write is refused
    # rather than silently dropping what is already there.
    from dims_analysis.common import arrays

    report = results.write_payload(path, {
        "video_id": "reference",
        "payload_version": arrays.PAYLOAD_VERSION,
        "rqa_data": {"from_another_step": {"x": 1}},
    })

    with open(path) as fh:
        after = json.load(fh)
    for name in before["rqa_data"]:
        assert name in after["rqa_data"], f"{name} was erased by the second write"
    assert "from_another_step" in after["rqa_data"]
    assert sorted(report["kept"].get("rqa_data", [])) == sorted(before["rqa_data"]), (
        "the write reported keeping something other than what it kept")


def test_parallel_and_serial_cross_wavelet_are_byte_identical(tmp_path_factory):
    """The acceptance check for running pairs concurrently.

    Reordering work across processes is exactly the change that can perturb a
    floating-point sum or consume a random stream in a different order, and the
    result would still look entirely plausible -- a coherence field is not a
    thing anyone eyeballs for correctness. So the bar is byte-identity, not
    closeness.

    Two things make it hold and both are deliberate: the Monte Carlo null is
    seeded on its own parameters rather than drawn from a shared stream, and
    results are collected in the order the pairs were listed rather than as
    they finish, because the payload is a dict written in insertion order.

    Measured on this study with a cold null cache, ten cores, seven pairs:
    95.3 s serially against 37.1 s in parallel. The reason to care is ORTHO,
    where the same run takes about 2.8 hours.
    """
    import shutil
    import subprocess
    import sys

    from conftest import REFERENCE

    produced = {}
    for label, jobs in (("serial", "1"), ("parallel", "-1")):
        work = tmp_path_factory.mktemp(f"jobs_{label}")
        study = str(work / "reference")
        shutil.copytree(REFERENCE, study,
                        ignore=shutil.ignore_patterns("assets", "__pycache__"))
        subprocess.run([sys.executable, os.path.join(study, "make_reference_study.py")],
                       check=True, capture_output=True)
        run = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.argv = ['crosswavelet', '--config', 'config.json',"
             " '--output-dir', 'assets/crosswavelet', '--jobs', %r];"
             " from dims_analysis.steps.crosswavelet import main; main()" % jobs],
            cwd=study, capture_output=True, text=True)
        if run.returncode != 0:
            pytest.fail(f"the {label} run failed:\n{run.stdout[-3000:]}{run.stderr[-3000:]}")
        produced[label] = {name: digest(path)
                           for name, path in outputs(study).items()}

    assert produced["serial"], "the serial run wrote nothing to compare"
    assert produced["serial"] == produced["parallel"], (
        "parallel output differs from serial: "
        + ", ".join(sorted(k for k in produced["serial"]
                           if produced["serial"][k] != produced["parallel"].get(k))))
