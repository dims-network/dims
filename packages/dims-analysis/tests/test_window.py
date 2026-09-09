"""Where the sliding windows go, and whether the payload admits it.

`window.py` is the largest module in the package with no test of its own. It was
written to end two invisible defects: the requested window and step were
silently overridden, and the override was done in *samples*, so the answer moved
with the sampling rate. Both are the kind of defect that produces a plausible
number, so the tests here are mostly about what the plan *reports* rather than
what it computes -- a window that was shortened and says so is correct, and one
that was shortened in silence is the bug.

The reference study carries the same 2 s sine at 50 Hz and at 100 Hz for exactly
this reason; `test_the_plan_is_the_same_at_two_sampling_rates` is that pair,
made cheap.
"""
import numpy as np
import pytest

from dims_analysis.common import window as win


def test_a_window_that_fits_is_used_as_asked():
    """Nothing is adapted when nothing needs to be, and nothing is reported."""
    plan = win.plan(n=6000, dt=0.01, window_sec=12.0, step_sec=0.5)
    report = plan.report()
    assert report["length_requested_sec"] == report["length_used_sec"] == 12.0
    assert report["step_requested_sec"] == report["step_used_sec"] == 0.5
    assert "warning" not in report
    assert plan.warning is None
    assert report["n_windows"] == len(plan) > 20


def test_a_window_too_long_for_the_recording_is_shortened_to_half_of_it():
    """A 20 s window does not fit twice in a 20 s recording.

    The adaptation is right; it is the silence that was wrong. So the shortened
    value and the asked-for value are both in the payload.
    """
    plan = win.plan(n=1024, dt=0.02, window_sec=20.0, step_sec=1.0)  # 20.48 s
    report = plan.report()
    assert report["length_requested_sec"] == 20.0
    assert report["length_used_sec"] == pytest.approx(20.48 / 2, abs=0.02)
    assert report["length_used_sec"] < report["length_requested_sec"]


def test_the_step_is_shortened_so_at_least_twenty_windows_fit():
    """Fewer than twenty windows makes a metric chart unreadable.

    Twenty is written out here rather than read from `win.MIN_WINDOWS`. A test
    that takes its expectation from the code under test moves whenever the code
    does, which is the one thing it must not do -- the same rule the reference
    suite states about the study's constants.
    """
    plan = win.plan(n=1000, dt=0.01, window_sec=5.0, step_sec=4.0)   # 10 s span
    report = plan.report()
    assert report["step_requested_sec"] == 4.0
    # 5 s of slide, twenty windows in it.
    assert report["step_used_sec"] == pytest.approx(0.25)
    assert len(plan) == 21
    assert win.MIN_WINDOWS == 20


def test_the_step_never_goes_finer_than_the_data():
    """Sub-sample steps would place two windows at one index."""
    plan = win.plan(n=40, dt=0.5, window_sec=2.0, step_sec=0.001)
    assert plan.report()["step_used_sec"] >= 0.5
    assert len(set(plan.starts)) == len(plan.starts)


def test_an_adapted_plan_says_why_in_a_sentence():
    """Worth a sentence rather than a flag: a reader comparing two studies has
    to know the metrics differ partly because the windows do."""
    plan = win.plan(n=1024, dt=0.02, window_sec=20.0, step_sec=1.0)
    warning = plan.report()["warning"]
    assert "20 s window was shortened" in warning
    assert "DET and LAM" in warning          # what is not comparable
    assert "not comparable" in warning


def test_the_plan_is_the_same_at_two_sampling_rates():
    """The defect this module was written for.

    The old logic adapted in samples, so the same 20.48 s recording came out
    with steps of 0.5 s and 0.51 s and last window centres of 15.12 s and
    15.32 s depending on whether it was sampled at 50 Hz or 100 Hz. Everything
    is decided in seconds now, and sample indices are derived at the end.
    """
    slow = win.plan(n=1024, dt=0.02, window_sec=20.0, step_sec=1.0)
    fast = win.plan(n=2048, dt=0.01, window_sec=20.0, step_sec=1.0)
    assert slow.report()["length_used_sec"] == pytest.approx(
        fast.report()["length_used_sec"], abs=1e-9)
    assert slow.report()["step_used_sec"] == pytest.approx(
        fast.report()["step_used_sec"], abs=1e-9)
    assert len(slow) == len(fast)

    slow_centres = slow.centres(np.arange(1024) * 0.02)
    fast_centres = fast.centres(np.arange(2048) * 0.01)
    assert slow_centres[-1] == pytest.approx(fast_centres[-1], abs=0.02)


def test_window_starts_are_placed_by_rounding_a_time_not_by_striding_samples():
    """The other half of "everything is decided in seconds".

    With a step that is not a whole number of samples -- 0.1 s at 30 Hz is
    3 1/3 samples -- rounding each window's *time* and truncating it give
    different indices from the third window on. Truncating accumulates the
    error; rounding does not. The two-rate test above cannot see this, because
    both rates truncate the same way.
    """
    plan = win.plan(n=300, dt=0.03, window_sec=3.0, step_sec=0.1)
    assert plan.report()["step_used_sec"] == pytest.approx(0.1)
    # k * 0.1 / 0.03 = 0, 3.33, 6.67, 10.0, 13.33, 16.67 ...
    assert plan.starts[:6] == [0, 3, 7, 10, 13, 17]


def test_centres_come_from_the_real_time_axis():
    """Taken from the values, not computed, so a recording that does not start
    at zero reports where its windows actually were."""
    plan = win.plan(n=600, dt=0.1, window_sec=10.0, step_sec=1.0)
    offset = 120.0
    centres = plan.centres(np.arange(600) * 0.1 + offset)
    assert centres[0] == pytest.approx(offset + 5.0, abs=0.1)
    assert min(centres) >= offset


def test_a_centre_never_runs_off_the_end_of_the_axis():
    plan = win.plan(n=50, dt=0.1, window_sec=4.0, step_sec=0.1)
    time_values = np.arange(50) * 0.1
    assert max(plan.centres(time_values)) <= time_values[-1]


def test_every_window_fits_inside_the_recording():
    for n, dt in ((600, 0.1), (1024, 0.02), (137, 0.037)):
        plan = win.plan(n=n, dt=dt, window_sec=5.0, step_sec=0.25)
        assert plan.starts[0] >= 0
        assert plan.starts[-1] + plan.length <= n, (n, dt)
        assert plan.length >= win.MIN_WINDOW_POINTS


def test_a_recording_too_short_to_slide_gets_one_window():
    """When the shortened window is the whole recording there is nowhere to go.

    The floor is two samples, so this is the smallest input that produces a
    plan at all -- and it produces one window rather than zero, because a step
    that cannot advance must not mean an empty metric series.
    """
    plan = win.plan(n=2, dt=1.0, window_sec=60.0, step_sec=1.0)
    assert len(plan) == 1
    assert plan.starts == [0]
    assert plan.length == win.MIN_WINDOW_POINTS

    # A recording only twice that long can still slide, one sample at a time,
    # because the step is floored at dt rather than at the requested value.
    assert len(win.plan(n=4, dt=1.0, window_sec=60.0, step_sec=1.0)) == 3


def test_a_sampling_interval_must_be_positive():
    """A zero dt divides; the message says which number was wrong."""
    with pytest.raises(ValueError, match="must be positive"):
        win.plan(n=100, dt=0.0, window_sec=10.0, step_sec=1.0)
    with pytest.raises(ValueError, match="must be positive"):
        win.plan(n=100, dt=-0.1, window_sec=10.0, step_sec=1.0)


def test_the_report_is_rounded_but_not_truncated():
    """Six decimal places, so a step of 0.0333333... does not print as 0.03."""
    plan = win.plan(n=1000, dt=0.01, window_sec=5.0, step_sec=1 / 3)
    assert plan.report()["step_requested_sec"] == pytest.approx(1 / 3, abs=1e-6)
