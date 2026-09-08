"""RQA against signals whose answers are arithmetic.

A sine at a 2 s period recurs every 2 s; a signal with no variance has no
structure to find; a signal quantised to four levels cannot be thresholded to
an arbitrary recurrence rate. None of that is checkable on real data, where
`DET = 0.2571` is a number nobody can verify.

Shared fixtures and helpers: conftest.py.
"""
import json
import os

import numpy as np
import pytest

from conftest import PERIOD_SAMPLES, TARGET_RATE, dense, diagonal_offsets, entry


# --- K1: a periodic signal recurs at its period ------------------------------

def test_K1_a_sine_recurs_at_its_own_period(recurrence):
    """The spacing of the diagonals is the signal's period. Nothing else.

    Catches: a reduction that moves structure, and line extraction that finds
    lines where there are none.
    """
    study, _ = recurrence
    e = entry(study, "rqa", "rqa_data", "sine")
    vis = e["visualization"]
    factor = vis["reduction"]["factor"]
    expected = PERIOD_SAMPLES / factor

    offsets = [k for k in diagonal_offsets(dense(vis)) if k > 0]
    assert offsets, "a pure sine produced no recurrent diagonal at all"
    gaps = np.diff([0] + offsets)
    close = [g for g in gaps if abs(g - expected) <= max(2, 0.15 * expected)]
    assert close, (
        f"diagonals at {offsets[:8]} (factor {factor}); expected a spacing near "
        f"{expected:.0f} samples, got gaps {list(gaps[:8])}")


def det_from_definition(m, min_len=2, exclude_identity=True):
    """DET straight from its definition, sharing no code with the step.

    A test that recomputes the expected value with the implementation's own
    helpers proves only that the helper is self-consistent. This is the second
    opinion: the fraction of recurrent points lying on diagonal runs of at
    least `min_len`, with the line of identity excluded from **both** the
    numerator and the denominator -- which is exactly what the shipped code got
    wrong, deflating DET and LAM by roughly 14/W.
    """
    n = m.shape[0]
    total = int(m.sum()) - (n if exclude_identity else 0)
    if total <= 0:
        return 0.0
    on_lines = 0
    for k in range(-(n - 1), n):
        if exclude_identity and k == 0:
            continue
        diag = np.diagonal(m, offset=k)
        padded = np.concatenate(([0], diag, [0]))
        edges = np.diff(padded)
        lens = np.where(edges == -1)[0] - np.where(edges == 1)[0]
        on_lines += int(lens[lens >= min_len].sum())
    return on_lines / total


def test_K1_DET_matches_its_own_definition(recurrence):
    """The step's DET against DET computed independently on the same data.

    Measured while writing this: a pure sine gives 0.896 by the definition and
    0.899 from the step -- not the ~1.0 one might assume, because a discretely
    sampled sine leaves isolated points at the edges of the threshold band. The
    number to assert is therefore not a guess about what DET "should" be; it is
    whether the step computes the quantity it claims to.

    Catches: the DET denominator, which excluded the line of identity from the
    numerator and not the denominator. On real data correcting that moved DET
    by 17-25 %.
    """
    from scipy.spatial.distance import cdist
    study, _ = recurrence

    series = np.genfromtxt(
        os.path.join(study, "assets", "timeseries", "reference_sine.csv"),
        delimiter=",", names=True)
    x = series["value"]
    z = (x - x.mean()) / x.std()
    d = cdist(z.reshape(-1, 1), z.reshape(-1, 1))
    threshold = entry(study, "rqa", "rqa_data", "sine")["threshold"]
    m = (d <= threshold).astype(np.uint8)

    expected = det_from_definition(m)
    reported = [v for v in entry(study, "rqa", "rqa_data", "sine")["windowed_metrics"]["DET"]
                if v is not None]
    assert reported, "no windowed DET at all"
    assert abs(np.mean(reported) - expected) < 0.03, (
        f"the step reports mean DET {np.mean(reported):.4f}; computing it from "
        f"the definition on the same matrix gives {expected:.4f}")


def test_K1_DET_and_LAM_match_a_published_implementation(recurrence):
    """The strongest check available: agreement with somebody else's code.

    `det_from_definition` above is my reading of the definition, and a test
    that only agrees with my own reimplementation would agree with my own
    misconception too. pyrqa (Rawald et al.) is an independent, published RQA
    implementation, so this is a second opinion from outside the project.

    Measured on this sine at a 7 % threshold: pyrqa gives DET 0.8996 and LAM
    0.9548; this step gives 0.899. Note that neither is near 1.0 -- a
    discretely sampled sine leaves isolated points at the edges of the
    threshold band -- which is exactly why "DET should be about 1" was the
    wrong thing to assert and agreement is the right one.

    Optional: pyrqa needs OpenCL and is not a runtime dependency. Where it is
    absent this skips, and `test_K1_DET_matches_its_own_definition` still runs.
    """
    pyrqa_ts = pytest.importorskip("pyrqa.time_series")
    from pyrqa.analysis_type import Classic
    from pyrqa.computation import RQAComputation
    from pyrqa.metric import EuclideanMetric
    from pyrqa.neighbourhood import FixedRadius
    from pyrqa.settings import Settings

    study, _ = recurrence
    series = np.genfromtxt(
        os.path.join(study, "assets", "timeseries", "reference_sine.csv"),
        delimiter=",", names=True)
    x = series["value"]
    z = (x - x.mean()) / x.std()

    e = entry(study, "rqa", "rqa_data", "sine")
    settings = Settings(
        pyrqa_ts.TimeSeries(z.tolist(), embedding_dimension=1, time_delay=1),
        analysis_type=Classic,
        neighbourhood=FixedRadius(float(e["threshold"])),
        similarity_measure=EuclideanMetric,
        # Excludes the main diagonal, matching this project's self_paired rule:
        # a point recurring with itself is not a finding.
        theiler_corrector=1)
    result = RQAComputation.create(settings, verbose=False).run()
    result.min_diagonal_line_length = 2
    result.min_vertical_line_length = 2

    for metric, theirs in (("DET", result.determinism), ("LAM", result.laminarity)):
        ours = [v for v in e["windowed_metrics"][metric] if v is not None]
        assert ours, f"no windowed {metric}"
        assert abs(np.mean(ours) - theirs) < 0.05, (
            f"{metric}: this step reports {np.mean(ours):.4f}, pyrqa computes "
            f"{theirs:.4f} on the same signal at the same threshold")


def test_K1_a_sine_is_mostly_deterministic(recurrence):
    """And the value itself is where a periodic signal should put it."""
    study, _ = recurrence
    det = [v for v in entry(study, "rqa", "rqa_data", "sine")["windowed_metrics"]["DET"]
           if v is not None]
    assert np.mean(det) > 0.85, f"a pure sine gave mean DET {np.mean(det):.3f}"


# --- K2: noise does not look periodic ----------------------------------------

def test_K2_noise_is_far_less_deterministic_than_a_sine(recurrence):
    """The other half of K1: a metric that says everything is deterministic is
    not measuring determinism."""
    study, _ = recurrence
    sine = [v for v in entry(study, "rqa", "rqa_data", "sine")["windowed_metrics"]["DET"]
            if v is not None]
    noise = [v for v in entry(study, "rqa", "rqa_data", "noise_a")["windowed_metrics"]["DET"]
             if v is not None]
    assert np.mean(noise) < np.mean(sine) - 0.2, (
        f"noise DET {np.mean(noise):.3f} vs sine DET {np.mean(sine):.3f}")


# --- K4: the achieved rate, and saying so when it cannot be reached ----------

def test_K4_the_target_recurrence_rate_is_reached_on_clean_signals(recurrence):
    study, _ = recurrence
    for name in ("sine", "noise_a"):
        rate = entry(study, "rqa", "rqa_data", name)["recurrence_rate"]
        assert abs(rate - TARGET_RATE) < 0.01, (
            f"{name} reached {rate:.4f} against a {TARGET_RATE} target")


def test_K4_an_unreachable_target_is_reported_not_silently_missed(recurrence):
    """A quantised signal has many exactly-equal distances, so the threshold
    lands on a plateau and the rate overshoots.

    ORTHO does this for real -- a game piece at rest gives ties, and `vy`
    reaches 12.7 % against a 7 % target with nothing said. DET and LAM depend
    strongly on the rate, so comparing recordings at 7 % and 12.7 % compares
    incomparable numbers.
    """
    study, _ = recurrence
    e = entry(study, "rqa", "rqa_data", "quantised")
    rate = e["recurrence_rate"]
    if abs(rate - TARGET_RATE) < 0.01:
        pytest.skip("this signal did reach the target; the case needs a harsher one")
    assert "target_recurrence" in e, (
        f"achieved {rate:.4f} against a {TARGET_RATE} target and the payload "
        f"does not record what was asked for")
    assert e.get("recurrence_rate_warning"), (
        f"achieved {rate:.4f} against {TARGET_RATE} and nothing says so")


# --- K7: a signal with no variance -------------------------------------------

def test_K7_a_constant_signal_has_a_stated_result(recurrence):
    """A constant signal is refused, and the refusal says why.

    It used to divide by zero in normalisation -- `rqa.py` had no guard where
    `crqa.py` had an epsilon -- giving NaN throughout. `nan <= threshold` is
    False everywhere, so the matrix came out empty, and subtracting the line of
    identity from a count of zero produced **recurrence_rate =
    -0.000977517**: a negative share of cells, on a dashboard caption.

    Now `series.load` requires the caller's stated minimum variance and
    `recurrence_rate` refuses a matrix with no line of identity, so neither the
    cause nor the symptom can recur.
    """
    study, out = recurrence
    path = os.path.join(study, "assets", "rqa", "reference_rqa_data.json")
    with open(path) as fh:
        payload = json.load(fh)

    if "flat" not in payload["rqa_data"]:
        assert "flat" in out, "a constant signal was skipped without saying so"
        return

    e = payload["rqa_data"]["flat"]
    vis = e["visualization"]
    values = [v for row in [vis["sparse_matrix"]] for v in row]
    assert e["recurrence_rate"] > 0.99 or e.get("degenerate"), (
        f"a constant signal gave recurrence_rate {e['recurrence_rate']} and no "
        f"note that it is degenerate. Every point is identical to every other, "
        f"so the rate is either 1 or the input should have been refused; "
        f"{len(values)} recurrent cells were drawn")


# --- K8: reduction preserves what it claims to ------------------------------

def test_K8_the_reduction_keeps_the_rate_it_reports(recurrence):
    study, _ = recurrence
    for analysis, container, name in (("rqa", "rqa_data", "sine"),
                                      ("rqa", "rqa_data", "noise_a"),
                                      ("crqa", "crqa_data", "sine_vs_sine_lagged")):
        vis = entry(study, analysis, container, name)["visualization"]
        red = vis["reduction"]
        drawn = dense(vis).mean()
        assert abs(drawn - red["rate_drawn"]) < 0.01, (
            f"{name}: the payload says it drew {red['rate_drawn']:.4f}, the "
            f"picture is {drawn:.4f}")
        assert abs(red["rate_drawn"] - red["rate_full"]) < 0.02, (
            f"{name}: drew {red['rate_drawn']:.4f} for an analysis at "
            f"{red['rate_full']:.4f}")


def test_K8_the_drawn_picture_never_exceeds_its_cap(recurrence):
    study, _ = recurrence
    for analysis, container in (("rqa", "rqa_data"), ("crqa", "crqa_data")):
        path = os.path.join(study, "assets", analysis, f"reference_{analysis}_data.json")
        with open(path) as fh:
            payload = json.load(fh)
        for name, e in payload[container].items():
            size = e["visualization"]["matrix_size"]
            assert size <= 500, f"{analysis}/{name} drew a {size}-point matrix"




# --- what produced this file -------------------------------------------------

def test_the_payload_records_what_produced_it(recurrence):
    """An output that does not say how it was made cannot be compared to
    another. Two real cases: a study computed partly at 100 surrogates and
    partly at 300 was silently inconsistent because the count appeared nowhere;
    and an analysis that *reached* 33.7% looked identical to one that was
    *asked for* 33.7%.
    """
    study, _ = recurrence
    for analysis, container in (("rqa", "rqa_data"), ("crqa", "crqa_data")):
        path = os.path.join(study, "assets", analysis,
                            f"reference_{analysis}_data.json")
        with open(path) as fh:
            payload = json.load(fh)
        prov = payload.get("provenance")
        assert prov, f"{analysis} records nothing about what produced it"
        assert prov.get("core_version"), f"{analysis} has no core version"
        assert prov.get("target_recurrence") == TARGET_RATE
        assert prov.get("max_points_drawn") == 500


def test_each_entry_records_the_rate_asked_for_and_the_rate_reached(recurrence):
    study, _ = recurrence
    for name in ("sine", "noise_a", "quantised"):
        e = entry(study, "rqa", "rqa_data", name)
        assert e["target_recurrence"] == TARGET_RATE
        assert abs(e["achieved_recurrence"] - e["recurrence_rate"]) < 1e-9
        # The warning is present exactly when the target was missed.
        missed = abs(e["achieved_recurrence"] - TARGET_RATE) > 0.01
        assert bool(e["recurrence_rate_warning"]) == missed, (
            f"{name}: achieved {e['achieved_recurrence']:.4f} against "
            f"{TARGET_RATE}, warning={e['recurrence_rate_warning']!r}")
