"""Every recurrence metric, for both analyses, on signals with known answers.

DET had two tests and RR one; LAM and L_MAX had none, and LAM was wrong -- it
came out at 1.0137 on `sine_2x`, which a share of points cannot be. The two
line extractions ignore different things (the diagonal scan skips the line of
identity, the vertical scan does not) so they cannot share a denominator.

Each metric is checked three ways where it can be: against pyrqa, an
independent published implementation; against the contrast a periodic signal
and a noise must produce; and against the bound a share of points cannot leave.

RQA and cross-RQA are both covered, and they differ in one important way --
cross-recurrence has no line of identity to exclude, because the two series are
different by construction. `sine_vs_sine` is the case where that assumption is
false, and it is here on purpose.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

from conftest import entry

pyrqa_ts = pytest.importorskip("pyrqa.time_series")
from pyrqa.analysis_type import Classic, Cross              # noqa: E402
from pyrqa.computation import RQAComputation                # noqa: E402
from pyrqa.metric import EuclideanMetric                    # noqa: E402
from pyrqa.neighbourhood import FixedRadius                 # noqa: E402
from pyrqa.settings import Settings                         # noqa: E402

MIN_LINE = 2

RQA_SIGNALS = ["sine", "noise_a", "quantised", "sine_x10", "sine_2x"]
CRQA_PAIRS = ["sine_vs_sine_lagged", "noise_a_vs_noise_b", "sine_vs_sine"]


def mean_metric(entry_, name):
    values = [v for v in entry_["windowed_metrics"][name] if v is not None]
    assert values, f"no windowed {name}"
    return float(np.mean(values))


def normalised(study, name):
    series = np.genfromtxt(
        os.path.join(study, "assets", "timeseries", f"reference_{name}.csv"),
        delimiter=",", names=True)
    x = series["value"]
    return (x - x.mean()) / x.std()


def pyrqa_result(series, threshold, second=None):
    """pyrqa's own answer: Classic for auto-recurrence, Cross for a pair."""
    if second is None:
        args = dict(analysis_type=Classic, theiler_corrector=1)
        data = pyrqa_ts.TimeSeries(series.tolist(), embedding_dimension=1,
                                   time_delay=1)
    else:
        args = dict(analysis_type=Cross, theiler_corrector=0)
        data = (pyrqa_ts.TimeSeries(series.tolist(), embedding_dimension=1,
                                    time_delay=1),
                pyrqa_ts.TimeSeries(second.tolist(), embedding_dimension=1,
                                    time_delay=1))
    settings = Settings(data, neighbourhood=FixedRadius(float(threshold)),
                        similarity_measure=EuclideanMetric, **args)
    result = RQAComputation.create(settings, verbose=False).run()
    result.min_diagonal_line_length = MIN_LINE
    result.min_vertical_line_length = MIN_LINE
    return result


# --- the bound no share of points may leave ----------------------------------

@pytest.mark.parametrize("metric", ["RR", "DET", "LAM"])
@pytest.mark.parametrize("name", RQA_SIGNALS)
def test_rqa_shares_stay_between_zero_and_one(recurrence, name, metric):
    """LAM was 1.0137 on `sine_2x` and 1.0052 on `quantised`."""
    study, _ = recurrence
    value = mean_metric(entry(study, "rqa", "rqa_data", name), metric)
    assert 0.0 <= value <= 1.0, f"rqa/{name} {metric} = {value}"


@pytest.mark.parametrize("metric", ["RR", "DET", "LAM"])
@pytest.mark.parametrize("pair", CRQA_PAIRS)
def test_crqa_shares_stay_between_zero_and_one(recurrence, pair, metric):
    study, _ = recurrence
    value = mean_metric(entry(study, "crqa", "crqa_data", pair), metric)
    assert 0.0 <= value <= 1.0, f"crqa/{pair} {metric} = {value}"


# --- against an independent implementation -----------------------------------

@pytest.mark.parametrize("name", ["sine", "noise_a"])
def test_rqa_metrics_agree_with_pyrqa(recurrence, name):
    """Measured on the sine: pyrqa DET 0.8996 LAM 0.9548, this step 0.8992 and
    0.9548. The LAM agreement is what settled the denominator question -- the
    shipped value was 0.9681, and pyrqa is what said which of the two was
    right."""
    study, _ = recurrence
    e = entry(study, "rqa", "rqa_data", name)
    theirs = pyrqa_result(normalised(study, name), e["threshold"])
    for metric, expected in (("DET", theirs.determinism),
                             ("LAM", theirs.laminarity)):
        ours = mean_metric(e, metric)
        assert abs(ours - expected) < 0.05, (
            f"rqa/{name} {metric}: this step {ours:.4f}, pyrqa {expected:.4f}")
    assert abs(e["recurrence_rate"] - theirs.recurrence_rate) < 0.01


def test_crqa_metrics_agree_with_pyrqa(recurrence):
    """Cross-recurrence, where pyrqa uses its `Cross` analysis type and no
    Theiler correction -- the two series are different, so there is no line of
    identity to exclude."""
    study, _ = recurrence
    e = entry(study, "crqa", "crqa_data", "sine_vs_sine_lagged")
    theirs = pyrqa_result(normalised(study, "sine"), e["threshold"],
                          second=normalised(study, "sine_lagged"))
    for metric, expected in (("DET", theirs.determinism),
                             ("LAM", theirs.laminarity)):
        ours = mean_metric(e, metric)
        assert abs(ours - expected) < 0.10, (
            f"crqa {metric}: this step {ours:.4f}, pyrqa {expected:.4f}")


# --- what each metric must say about each kind of signal --------------------

def test_a_periodic_signal_is_deterministic_and_laminar(recurrence):
    study, _ = recurrence
    e = entry(study, "rqa", "rqa_data", "sine")
    assert mean_metric(e, "DET") > 0.85
    assert mean_metric(e, "LAM") > 0.85


@pytest.mark.parametrize("metric", ["DET", "LAM"])
def test_rqa_separates_structure_from_noise(recurrence, metric):
    """A metric that says everything is structured is not measuring structure."""
    study, _ = recurrence
    sine = mean_metric(entry(study, "rqa", "rqa_data", "sine"), metric)
    noise = mean_metric(entry(study, "rqa", "rqa_data", "noise_a"), metric)
    assert noise < sine - 0.2, f"{metric}: noise {noise:.3f} vs sine {sine:.3f}"


@pytest.mark.parametrize("metric", ["DET", "LAM"])
def test_crqa_separates_a_real_relationship_from_none(recurrence, metric):
    """The same contrast, for the pairwise analysis. Measured: DET 0.84 for two
    shifted copies of one sine, 0.29 for two independent noises."""
    study, _ = recurrence
    related = mean_metric(entry(study, "crqa", "crqa_data",
                                "sine_vs_sine_lagged"), metric)
    unrelated = mean_metric(entry(study, "crqa", "crqa_data",
                                  "noise_a_vs_noise_b"), metric)
    assert unrelated < related - 0.2, (
        f"{metric}: unrelated {unrelated:.3f} vs related {related:.3f}")


@pytest.mark.parametrize("analysis,container,structured,noisy", [
    ("rqa", "rqa_data", "sine", "noise_a"),
    ("crqa", "crqa_data", "sine_vs_sine_lagged", "noise_a_vs_noise_b"),
])
def test_the_longest_line_separates_structure_from_noise(
        recurrence, analysis, container, structured, noisy):
    """L_MAX is the longest diagonal, in seconds. A periodic relationship keeps
    a line going for many periods; an unrelated pair breaks it within a sample
    or two. Measured: 8.24 s against 0.11 s for RQA, 9.84 s against 0.11 s for
    cross-RQA."""
    study, _ = recurrence
    long_ = mean_metric(entry(study, analysis, container, structured), "L_MAX")
    short = mean_metric(entry(study, analysis, container, noisy), "L_MAX")
    assert long_ > 20 * short, f"{analysis}: {long_:.3f} s against {short:.3f} s"
    assert short < 1.0, f"{analysis}/{noisy} sustained a {short:.3f} s line"


def test_cross_recurrence_keeps_the_line_that_auto_recurrence_removes(recurrence):
    """Why `self_paired` exists, made visible.

    RQA excludes the line of identity: a point recurring with itself is not a
    finding, and counting it would make L_MAX the length of the recording
    always. Cross-recurrence has no such line to exclude, because the two
    series are different by construction -- so running a signal against
    *itself* through cRQA keeps it, and L_MAX becomes the whole window.

    Measured: RQA(sine) 8.24 s, cRQA(sine, sine) 10.24 s, the full window.
    """
    study, _ = recurrence
    auto = mean_metric(entry(study, "rqa", "rqa_data", "sine"), "L_MAX")
    cross = mean_metric(entry(study, "crqa", "crqa_data", "sine_vs_sine"), "L_MAX")
    assert cross > auto, (
        f"cRQA(sine, sine) {cross:.2f} s should exceed RQA(sine) {auto:.2f} s, "
        f"because it keeps the identity line the other removes")


@pytest.mark.parametrize("analysis,container,names", [
    ("rqa", "rqa_data", ["sine", "noise_a"]),
    ("crqa", "crqa_data", ["sine_vs_sine_lagged", "noise_a_vs_noise_b"]),
])
def test_the_windowed_rate_comes_back_to_the_target(recurrence, analysis,
                                                    container, names):
    """RR is the one metric whose value is chosen rather than measured: the
    threshold is set to produce it, so the windowed mean must return to it."""
    study, _ = recurrence
    for name in names:
        e = entry(study, analysis, container, name)
        assert abs(mean_metric(e, "RR") - 0.07) < 0.015, (
            f"{analysis}/{name}: windowed RR {mean_metric(e, 'RR'):.4f}")
