"""The reference study: signals whose answers are known before anything runs.

Every other test here asks "did it crash?" or checks a helper in isolation. On
real data that is all that is available -- `DET = 0.2571` is a number nobody can
verify. These signals are constructed so the right answer is arithmetic: a sine
at a 2 s period recurs every 2 s, a copy delayed 0.4 s puts its cross-recurrence
line 0.4 s off the diagonal, and two independent red noises exceed a 95 % level
in 5 % of cells by construction.

Each test names the defect it would have caught. Nine were found in one session
by accident; these are what finding them on purpose looks like.

The study is generated, not committed: `examples/reference/make_reference_study.py`.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
REFERENCE = os.path.join(ROOT, "examples", "reference")
GENERATOR = os.path.join(REFERENCE, "make_reference_study.py")

# Straight from the generator, and deliberately restated rather than imported:
# a test that reads its expectations from the code under test proves nothing.
DT = 0.02
PERIOD_S = 2.0
LAG_S = 0.4
PERIOD_SAMPLES = 100
LAG_SAMPLES = 20
TARGET_RATE = 0.07


def build(tmp_path_factory, steps: str):
    """Generate the study into a temp dir and run `steps` over it."""
    work = tmp_path_factory.mktemp("reference")
    study = str(work / "reference")
    shutil.copytree(REFERENCE, study, ignore=shutil.ignore_patterns("assets", "__pycache__"))
    subprocess.run([sys.executable, os.path.join(study, "make_reference_study.py")],
                   check=True, capture_output=True)
    run = subprocess.run(
        [sys.executable, "-m", "dims_analysis.cli", "run",
         "--config", "config.json", "--steps", steps],
        cwd=study, capture_output=True, text=True)
    if run.returncode != 0:
        pytest.fail(f"the analyses failed:\n{run.stdout[-4000:]}\n{run.stderr[-4000:]}")
    return study, run.stdout


@pytest.fixture(scope="session")
def recurrence(tmp_path_factory):
    """RQA and cross-RQA. Seconds, so these tests stay usable."""
    study, out = build(tmp_path_factory, "rqa,crqa")
    return study, out


def entry(study, analysis, container, name):
    path = os.path.join(study, "assets", analysis, f"reference_{analysis}_data.json")
    with open(path) as fh:
        payload = json.load(fh)
    assert container in payload, f"{path} has no {container}"
    assert name in payload[container], (
        f"{path} has no entry for {name}; it has {sorted(payload[container])}")
    return payload[container][name]


def dense(vis):
    """The drawn matrix, however the payload happens to encode it."""
    n = vis["matrix_size"]
    m = np.zeros((n, n), dtype=np.uint8)
    for r, c in vis["sparse_matrix"]:
        if r < n and c < n:
            m[r, c] = 1
    return m


def diagonal_offsets(m, min_fraction=0.25):
    """Offsets k whose diagonal is recurrent for at least `min_fraction` of it.

    A recurrence line is a diagonal that is mostly filled. Reading the offsets
    back out is how the known lag and the known period become checkable.
    """
    n = min(m.shape)
    found = []
    for k in range(-(n - 1), n):
        d = np.diagonal(m, offset=k)
        if d.size >= 0.5 * n and d.mean() >= min_fraction:
            found.append(k)
    return found


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


# --- K3: a known lag lands where it should -----------------------------------

def test_K3_cross_recurrence_finds_the_lag_it_was_given(recurrence):
    """The line sits LAG off the diagonal, and that is the whole point.

    Catches: **striding**. Sampling every nth row and column keeps a line on
    the main diagonal and deletes one beside it -- and a lagged coupling is
    precisely a line beside it. This is the test the real studies could never
    have provided, because nobody knows their true lag.
    """
    study, _ = recurrence
    vis = entry(study, "crqa", "crqa_data", "sine_vs_sine_lagged")["visualization"]
    factor = vis["reduction"]["factor"]
    expected = LAG_SAMPLES / factor

    offsets = diagonal_offsets(dense(vis))
    assert offsets, "two identical signals, one delayed, produced no line at all"
    nearest = min(offsets, key=lambda k: abs(abs(k) - expected))
    assert abs(abs(nearest) - expected) <= max(2, 0.2 * expected), (
        f"the dominant line is at offset {nearest} (factor {factor}); a {LAG_S} s "
        f"lag should put it near {expected:.0f}. Offsets found: {offsets[:12]}")


# --- K4: the achieved rate, and saying so when it cannot be reached ----------

def test_K4_the_target_recurrence_rate_is_reached_on_clean_signals(recurrence):
    study, _ = recurrence
    for name in ("sine", "noise_a"):
        rate = entry(study, "rqa", "rqa_data", name)["recurrence_rate"]
        assert abs(rate - TARGET_RATE) < 0.01, (
            f"{name} reached {rate:.4f} against a {TARGET_RATE} target")


@pytest.mark.xfail(strict=True, reason=(
    "Known, and the spec for the next step: measured on this study, a quantised "
    "signal achieves 0.337 against a 0.07 target -- nearly five times over -- "
    "and the payload records neither the target nor a warning. Remove this "
    "marker when A5 lands; strict=True means it fails the moment it starts "
    "passing, so the fix cannot go unnoticed."))
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

@pytest.mark.xfail(strict=True, reason=(
    "Known, and worse than expected: a constant signal produces "
    "recurrence_rate = -0.000977517. A negative rate is arithmetically "
    "impossible for a fraction of cells -- it comes from subtracting the line "
    "of identity from a count that is already zero -- and it reaches the "
    "dashboard as a caption. Remove this marker when A1 lands."))
def test_K7_a_constant_signal_has_a_stated_result(recurrence):
    """Zero variance divides by zero in normalisation -- `rqa.py` has no guard
    where `crqa.py` has an epsilon. The failure is silent: NaN throughout, then
    `nan <= threshold` is False everywhere, so the matrix is empty and the rate
    is 0, reported as a finding.

    Either the step refuses this input, or it produces something documented. It
    must not produce a confident zero.
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


# --- K5: a known lag has a known phase ---------------------------------------

@pytest.fixture(scope="session")
def coherence_study(tmp_path_factory):
    """Cross-wavelet. ~40 s at the reference study's mcCount of 20."""
    study, out = build(tmp_path_factory, "crosswavelet")
    return study, out


def pair(study, name):
    path = os.path.join(study, "assets", "crosswavelet",
                        "reference_crosswavelet_data.json")
    with open(path) as fh:
        payload = json.load(fh)
    assert name in payload["crosswavelet_pairs"], (
        f"no pair {name}; found {sorted(payload['crosswavelet_pairs'])}")
    return payload["crosswavelet_pairs"][name]["visualization"]


def as_array(field):
    return np.array([[np.nan if c is None else c for c in row] for row in field],
                    dtype=float)


def band_mask(period, low=1.6, high=2.5):
    """Scales around the 2 s component the signals actually contain."""
    return (np.asarray(period, dtype=float) > low) & (np.asarray(period) < high)


def test_K5_two_shifted_copies_are_coherent_at_their_shared_period(coherence_study):
    study, _ = coherence_study
    vis = pair(study, "sine_vs_sine_lagged")
    coh = as_array(vis["coherence"])
    band = band_mask(vis["period"])
    assert band.any(), "the 2 s band is not in the analysed range at all"
    assert np.nanmean(coh[band]) > 0.9, (
        f"two shifted copies of one sine gave mean coherence "
        f"{np.nanmean(coh[band]):.4f} at their own period")


def test_K5_the_phase_is_the_lag_that_was_put_in(coherence_study):
    """phase = 2*pi*f*tau = 2*pi*0.5*0.4 = 1.257 rad = 72 degrees.

    Confirmed independently by `scipy.signal.csd`, which gives 72.0 deg on the
    same two signals by a completely different route (Welch, not wavelets).

    Catches: the smoothing defect, which destroyed phase before it could
    cancel; and averaging phase as a scalar rather than through the unit
    circle, which turns +179 and -179 into 0.
    """
    study, _ = coherence_study
    vis = pair(study, "sine_vs_sine_lagged")
    phase = as_array(vis["phase"])
    band = band_mask(vis["period"])

    # Circular mean: the only correct way to average an angle.
    mean_phase = np.angle(np.nanmean(np.exp(1j * phase[band])))
    expected = 2 * np.pi * (1.0 / PERIOD_S) * LAG_S

    assert abs(abs(mean_phase) - expected) < np.radians(8), (
        f"phase is {np.degrees(mean_phase):.1f} deg; a {LAG_S} s lag at a "
        f"{PERIOD_S} s period is {np.degrees(expected):.1f} deg")


def test_K5_the_sign_of_the_phase_says_who_leads(coherence_study):
    """`sine_lagged` is `sine` delayed, so `sine` leads -- and the convention
    here is W1 * conj(W2), which makes that positive.

    This is worth its own test because a flipped sign is invisible in the
    number and inverts every phase arrow on the dashboard: a study would read
    "the student leads the teacher" from data saying the opposite.
    """
    study, _ = coherence_study
    vis = pair(study, "sine_vs_sine_lagged")
    band = band_mask(vis["period"])
    mean_phase = np.angle(np.nanmean(np.exp(1j * as_array(vis["phase"])[band])))
    assert mean_phase > 0, (
        f"phase {np.degrees(mean_phase):.1f} deg: the first signal leads the "
        f"second by {LAG_S} s, so under W1*conj(W2) this must be positive")
