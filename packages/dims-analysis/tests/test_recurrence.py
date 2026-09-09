"""The recurrence quantities, and why the two steps' formulas differed.

They looked like two conventions -- RQA subtracted the diagonal, cRQA did not --
and the audit read them as incomparable. They are the same rule applied to two
situations: ignore the trivially recurrent comparison of a point with itself,
which in cross-recurrence is an empty instruction because the two series differ.

Unifying the formulas rather than the rule would have put the artefact into
auto-RQA rather than taking one out, and the L_MAX test below is why.
"""
import numpy as np
import pytest

from dims_analysis.common import recurrence as rec


def _auto(n, density=0.07, seed=0):
    rng = np.random.default_rng(seed)
    m = (rng.random((n, n)) < density).astype(np.uint8)
    m = np.maximum(m, m.T)
    np.fill_diagonal(m, 1)
    return m


def test_the_identity_line_is_excluded_from_l_max():
    """Counting it makes L_MAX the length of the whole recording, always."""
    m = _auto(200)
    dt = 0.02
    _, _, _, l_max = rec.window_metrics(m, dt, self_paired=True)
    assert l_max < 200 * dt / 2, \
        "L_MAX picked up the line of identity, so it reports the whole window"


def test_det_denominator_matches_what_the_lines_exclude():
    """DET is the share of recurrent points lying on lines. Excluding the
    identity from the numerator and not the denominator deflates it."""
    m = _auto(200)
    _, det, _, _ = rec.window_metrics(m, 0.02, self_paired=True)
    diag = rec.line_lengths(m, "diagonal", 2, self_paired=True)
    deflated = float(np.sum(diag) / np.sum(m))       # the old denominator
    assert det > deflated
    assert det == pytest.approx(np.sum(diag) / (np.sum(m) - m.shape[0]))


def test_recurrence_rate_ignores_the_identity_only_when_self_paired():
    n = 50
    m = np.zeros((n, n), dtype=np.uint8)
    np.fill_diagonal(m, 1)
    assert rec.recurrence_rate(m, self_paired=True) == 0.0, \
        "a matrix with nothing but the identity line has no recurrence to report"
    assert rec.recurrence_rate(m, self_paired=False) == pytest.approx(1 / n)


def test_cross_recurrence_counts_every_cell():
    m = np.ones((4, 6), dtype=np.uint8)
    assert rec.recurrence_rate(m, self_paired=False) == 1.0


def test_the_threshold_hits_its_target_in_both_situations():
    rng = np.random.default_rng(1)
    a = rng.standard_normal((300, 1))
    b = rng.standard_normal((300, 1))
    from scipy.spatial.distance import cdist

    d_auto = cdist(a, a)
    t = rec.threshold_for_target(d_auto, 0.07, self_paired=True)
    rr = rec.recurrence_rate((d_auto <= t).astype(np.uint8), self_paired=True)
    assert rr == pytest.approx(0.07, abs=0.005)

    d_cross = cdist(a, b)
    t = rec.threshold_for_target(d_cross, 0.07, self_paired=False)
    rr = rec.recurrence_rate((d_cross <= t).astype(np.uint8), self_paired=False)
    assert rr == pytest.approx(0.07, abs=0.005)


def test_the_symmetric_shortcut_gives_the_same_answer():
    """The upper triangle is a memory saving, not a different rule.

    For a symmetric matrix the off-diagonal cells are the upper triangle
    doubled, so the two routes select the same distance. They are not
    bit-identical, because numpy interpolates linearly between order statistics
    and a doubled sample lands between different neighbours -- measured at 2.5e-5
    relative here. What has to match is the recurrence rate that comes out, and
    that is identical.
    """
    from scipy.spatial.distance import cdist
    rng = np.random.default_rng(2)
    d = cdist(rng.standard_normal((150, 1)), rng.standard_normal((150, 1)))
    d = (d + d.T) / 2
    np.fill_diagonal(d, 0.0)

    upper = rec.threshold_for_target(d, 0.07, self_paired=True)
    off = float(np.percentile(d[~np.eye(len(d), dtype=bool)], 7))
    assert upper == pytest.approx(off, rel=1e-3)

    rr_upper = rec.recurrence_rate((d <= upper).astype(np.uint8), self_paired=True)
    rr_off = rec.recurrence_rate((d <= off).astype(np.uint8), self_paired=True)
    assert rr_upper == pytest.approx(rr_off, abs=1e-9)


def test_both_steps_now_import_the_same_implementation():
    """Neither step keeps a private copy of the recurrence quantities.

    They used to, with two incompatible signatures in adjacent files. The fix
    left behind one-line wrappers that only forwarded, and this test asserted
    on their *docstrings* -- so it passed as long as the delegation existed,
    whether or not anything used it. The wrappers are gone and the steps call
    the shared module by name, which is the thing actually worth asserting.
    """
    from dims_analysis.steps import rqa, crqa
    assert rqa._rec is crqa._rec is rec
    for step in (rqa, crqa):
        for gone in ("get_line_lengths", "calculate_window_metrics"):
            assert not hasattr(step, gone), (
                f"{step.__name__}.{gone} is a wrapper that forwards and nothing "
                f"else; call common/recurrence.py directly")


def test_an_unknown_direction_is_refused():
    with pytest.raises(ValueError):
        rec.line_lengths(np.eye(4), direction="sideways")


def test_the_triangle_is_selected_by_mask_and_not_by_index_arrays():
    """Same values, same order, same percentile -- and a quarter of the memory.

    `np.triu_indices_from` spends two int64 index arrays to reach half a float64
    matrix; at the 16,384-sample bound that is 2 GiB of indices beside a 2 GiB
    matrix. A mask is 0.25 GiB and selects row-major, which is the order
    `triu_indices` produces, so the arrays are equal element for element.

    The full off-diagonal set is NOT an equivalent simplification: it lands
    between different order statistics and moves the threshold by ~5e-5
    relative, against a baseline that pins it at 1e-6.
    """
    rng = np.random.default_rng(4)
    d = rng.random((120, 120))
    d = (d + d.T) / 2
    np.fill_diagonal(d, 0.0)
    rows = np.arange(120)

    assert np.array_equal(d[rows[:, None] < rows[None, :]],
                          d[np.triu_indices_from(d, k=1)])

    by_triangle = rec.threshold_for_target(d, 0.07, self_paired=True)
    by_off_diagonal = float(np.percentile(d[~np.eye(120, dtype=bool)], 7.0))
    assert by_triangle != by_off_diagonal
    assert abs(by_off_diagonal - by_triangle) / by_triangle > 1e-6
