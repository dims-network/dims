"""How an analysis is reduced for the browser.

A recurrence plot carries two things a reader takes from it: where the structure
is, and how much of the plot is recurrent -- the rate printed beside it. There
are two obvious reductions and each keeps one and destroys the other:

  striding   keeps the rate, deletes the structure. A line one cell off the main
             diagonal vanishes entirely, because the sampled rows and columns
             never intersect it -- and an off-diagonal line is what a lagged
             coupling looks like, which is what cross-recurrence is for.
  block-OR   keeps the structure, inflates the rate. Any block with one point
             becomes recurrent, so density grows with the square of the factor.
             Measured on ORTHO at factor 9: 10.9% became 54.4%.

Both were shipped, in that order, and each test below fails on one of them.
"""
import numpy as np
import pytest

from dims_analysis.common import reduce as red


def _line(n, offset=0, dtype=np.uint8):
    m = np.zeros((n, n), dtype=dtype)
    for i in range(n):
        j = i + offset
        if 0 <= j < n:
            m[i, j] = 1
    return m


def _noise(n, density, seed=0):
    rng = np.random.default_rng(seed)
    return (rng.random((n, n)) < density).astype(np.uint8)


# --- the two failures, each pinned ------------------------------------------

def test_an_off_diagonal_line_survives():
    """Striding deletes this outright. The fixture asserts that first, so the
    test cannot quietly stop testing anything."""
    n, factor, offset = 360, 12, 1
    m = _line(n, offset)
    assert m[::factor, ::factor].sum() == 0, \
        "fixture wrong: this line is supposed to vanish under striding"
    reduced = red.block_binary(m, factor)
    assert reduced.sum() > 0, "the line was lost"
    # and it is still a line, not scattered points
    diagonals = [k for k in range(-reduced.shape[0] + 1, reduced.shape[1])
                 if reduced.diagonal(k).mean() > 0.5]
    assert diagonals, f"the line did not survive as a line: {reduced.sum()} points"


@pytest.mark.parametrize("density,factor", [(0.07, 4), (0.109, 9), (0.25, 6)])
def test_the_reduced_plot_has_the_same_recurrence_rate(density, factor):
    """Block-OR fails this badly: at factor 9 it turned 10.9% into 54.4%, so the
    picture contradicted the number printed beside it."""
    m = _noise(600, density)
    reduced = red.block_binary(m, factor)
    assert reduced.mean() == pytest.approx(m.mean(), abs=0.01), (
        f"input {m.mean():.3f} -> output {reduced.mean():.3f}")


def test_both_properties_hold_at_once():
    """Structure and rate together, which is the whole point."""
    n, factor = 900, 9
    m = _noise(n, 0.109, seed=1)
    for i in range(n - 20):
        m[i, i + 20] = 1                      # a clearly off-diagonal line
    reduced = red.block_binary(m, factor)

    assert reduced.mean() == pytest.approx(m.mean(), abs=0.01)
    k = 20 // factor                          # the block diagonal it maps onto
    assert reduced.diagonal(k).mean() > 2 * reduced.mean(), \
        "the line is not denser than the background it sits in"


# --- basic properties -------------------------------------------------------

def test_the_result_is_binary():
    """Averaging a recurrence matrix gives fractions, which are not recurrences."""
    reduced = red.block_binary(_noise(400, 0.07), 4)
    assert set(np.unique(reduced)).issubset({0, 1})


def test_an_empty_matrix_stays_empty():
    assert red.block_binary(np.zeros((30, 30), np.uint8), 5).sum() == 0


def test_a_full_matrix_stays_full():
    assert red.block_binary(np.ones((30, 30), np.uint8), 5).mean() == 1.0


def test_a_factor_of_one_is_the_identity():
    a = np.arange(9, dtype=np.uint8).reshape(3, 3)
    assert np.array_equal(red.block_binary(a, 1), a)
    assert np.array_equal(red.block_mean(a, 1), a)
    assert red.factor_for(100, 500) == 1


def test_the_output_is_deterministic():
    """Ties among equally dense blocks are broken arbitrarily but must not vary
    between runs, or two rebuilds of the same study would differ."""
    m = _noise(300, 0.07, seed=3)
    assert np.array_equal(red.block_binary(m, 6), red.block_binary(m, 6))


def test_series_are_averaged_not_sampled():
    a = np.arange(12, dtype=float)
    out = red.block_mean(a, 4)
    assert np.allclose(out, [1.5, 5.5, 9.5])
    assert not np.allclose(out, a[::4])


def test_factor_and_the_ragged_tail():
    assert red.factor_for(6000, 500) == 12
    # a partial trailing block is dropped, not padded: a padded block would
    # report recurrence over cells that were never computed.
    assert red.block_binary(np.ones((10, 10), np.uint8), 4).shape == (2, 2)
    assert red.block_mean(np.ones(10), 4).shape == (2,)


def test_block_mode_keeps_a_code_that_was_actually_there():
    """Averaging AOI codes would produce a code nobody looked at."""
    codes = np.array([1, 1, 3, 2, 2, 2, 5, 5, 9])
    out = red.block_mode(codes, 3)
    assert list(out) == [1, 2, 5]
    assert set(out) <= set(codes)


def test_block_mode_reduces_to_the_same_length_as_block_mean():
    """The display series and the reduced matrix have to line up."""
    codes = np.arange(23) % 4
    time = np.linspace(0, 1, 23)
    assert len(red.block_mode(codes, 5)) == len(red.block_mean(time, 5))


def test_block_mode_leaves_a_short_series_alone():
    codes = np.array([1, 2])
    assert list(red.block_mode(codes, 5)) == [1, 2]
    assert list(red.block_mode(codes, 1)) == [1, 2]
