"""How an analysis is reduced for the browser, and why it is not striding.

The cross-wavelet step block-averages and records the factor. The two recurrence
steps took every nth sample and every nth row/column, and recorded nothing.

For a continuous series, striding is decimation with no low-pass filter: it folds
detail back onto the frequencies that remain. For a recurrence matrix it is worse
than that, and worse in a way specific to what RQA measures.
"""
import numpy as np

from dims_analysis.common import reduce as red


def _diagonal(n, offset=0):
    m = np.zeros((n, n), dtype=np.uint8)
    for i in range(n):
        j = i + offset
        if 0 <= j < n:
            m[i, j] = 1
    return m


def test_striding_erases_an_off_diagonal_line_and_block_any_does_not():
    """The headline. Cross-recurrence is about structure OFF the main diagonal
    -- a lagged coupling is exactly that -- and striding deletes it outright."""
    m = _diagonal(60, offset=1)
    factor = 12
    strided = m[::factor, ::factor]
    reduced = red.block_any(m, factor)
    assert strided.sum() == 0, "fixture wrong: this line should vanish under striding"
    assert reduced.sum() > 0, "block-OR lost a line that striding was expected to lose"


def test_a_diagonal_survives_as_a_diagonal():
    m = _diagonal(60)
    reduced = red.block_any(m, 12)
    assert reduced.shape == (5, 5)
    assert np.array_equal(reduced, np.eye(5, dtype=reduced.dtype))


def test_block_any_stays_binary():
    rng = np.random.default_rng(0)
    m = (rng.random((40, 40)) < 0.07).astype(np.uint8)
    reduced = red.block_any(m, 4)
    assert set(np.unique(reduced)).issubset({0, 1}), \
        "averaging a recurrence matrix produces fractions, which are not recurrences"


def test_block_any_never_invents_recurrence():
    m = np.zeros((30, 30), dtype=np.uint8)
    assert red.block_any(m, 5).sum() == 0


def test_block_mean_averages_a_series_rather_than_sampling_it():
    a = np.arange(12, dtype=float)
    out = red.block_mean(a, 4)
    assert np.allclose(out, [1.5, 5.5, 9.5]), "series must be block-averaged"
    assert not np.allclose(out, a[::4]), "this is what striding would have given"


def test_a_factor_of_one_is_the_identity():
    a = np.arange(9, dtype=float).reshape(3, 3)
    assert np.array_equal(red.block_mean(a, 1), a)
    assert np.array_equal(red.block_any(a, 1), a)
    assert red.factor_for(100, 500) == 1


def test_factor_and_ragged_tails():
    assert red.factor_for(6000, 500) == 12
    # 10 rows at factor 4 -> the ragged tail is dropped, not padded with zeros,
    # because a padded block would report recurrence that was never computed.
    m = np.ones((10, 10), dtype=np.uint8)
    assert red.block_any(m, 4).shape == (2, 2)
    assert red.block_mean(np.ones(10), 4).shape == (2,)
