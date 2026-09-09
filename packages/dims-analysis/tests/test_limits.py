"""The bounds a recurrence analysis refuses at, and the arithmetic behind them.

`limits.py` exists because a recurrence analysis is quadratic and was unbounded:
a full Karnatak lesson is ~58,000 samples, which is a 27 GB float64 matrix on a
16 GB machine, and what a researcher saw was a MemoryError from inside SciPy.
The module's whole job is to refuse *before* allocating and to say what to do
instead -- so the tests that matter are that the refusal happens at the right
size, and that its message carries the three things the old failure did not:
how big the input is, what the limit is, and what to do about it.

None of this had a test. It was reached only when an end-to-end run happened to
pass through `rqa.py`, so the refusal branch -- the only branch anyone ever
meets -- was never once executed by the suite.
"""
import math

import pytest

from dims_analysis.common import limits


def test_the_matrix_is_quadratic_and_float64():
    """The number the budget is spent against.

    Eight bytes a cell because that is what `scipy.spatial.distance.cdist`
    returns; a bound computed against float32 would be wrong by 2x in the
    direction that runs the machine out of memory.
    """
    assert limits.matrix_bytes(1) == 8
    assert limits.matrix_bytes(1000) == 8_000_000
    assert limits.matrix_bytes(2000) == 4 * limits.matrix_bytes(1000)


def test_the_longest_series_that_fits_the_budget():
    """`max_points` is the inverse of `matrix_bytes`, and rounds down.

    Rounding up would name a length that does not fit, in the error message
    telling someone what would.
    """
    assert limits.max_points() == int(math.isqrt(limits.MAX_MATRIX_BYTES // 8))
    assert limits.matrix_bytes(limits.max_points()) <= limits.MAX_MATRIX_BYTES
    assert limits.matrix_bytes(limits.max_points() + 1) > limits.MAX_MATRIX_BYTES
    assert limits.max_points(8 * 100 ** 2) == 100


def test_the_documented_bound_is_the_one_the_code_enforces():
    """16,384 samples, which the analyses' documentation states.

    A bound that only exists in prose is a bound nobody is held to.
    """
    assert limits.max_points() == 16384
    assert limits.MAX_MATRIX_BYTES == 2 * 1024 ** 3


def test_an_input_that_fits_passes_silently():
    limits.check_length(limits.max_points(), "a series")
    limits.check_length(0, "an empty series")


def test_an_input_that_does_not_fit_is_refused_before_allocating():
    with pytest.raises(limits.InputTooLarge):
        limits.check_length(limits.max_points() + 1, "a series")


def test_the_refusal_says_what_to_do_about_it():
    """The message is the feature.

    A MemoryError from inside cdist names none of this, which is why the
    analyses used to fail in a way a researcher could not act on.
    """
    with pytest.raises(limits.InputTooLarge) as raised:
        limits.check_length(58_000, "bodysync")
    message = str(raised.value)
    assert "bodysync" in message                 # which input
    assert "58,000 samples" in message           # how big it is
    assert "16,384 samples" in message           # what would fit
    assert "2 GB" in message                     # the budget
    assert "excerpt" in message and "resample" in message   # the two options
    # And the caveat, because resampling is a decision about the analysis.
    assert "timescales" in message


def test_the_budget_is_a_parameter_so_a_test_need_not_allocate_2_gb():
    with pytest.raises(limits.InputTooLarge) as raised:
        limits.check_length(101, "a small series", budget=8 * 100 ** 2)
    assert "100 samples" in str(raised.value)
    limits.check_length(100, "a small series", budget=8 * 100 ** 2)


def test_the_minimums_are_the_ones_the_steps_share():
    """One number, not the four bare literals in four files this replaced."""
    assert limits.MIN_POINTS == 10
    assert limits.MIN_VARIANCE == 0.0
