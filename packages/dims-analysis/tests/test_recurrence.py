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


# --------------------------------------------------------------------------
# The fast path in window_metrics, against line_lengths as the reference.
#
# line_lengths stays as the reference implementation: it is what the docs send
# a reader to for the ENTR and mean-L histograms this package does not compute,
# and it is what these tests compare against. The shortcut has to be a
# shortcut, not a second opinion -- baseline.json pins mean_DET, mean_LAM and
# mean_RR at 1e-6, and a numerator that is right on average is a regression
# that reaches a dashboard caption.
# --------------------------------------------------------------------------

def _degenerate_and_random_matrices():
    """Every shape and density that has ever broken a run-length scan.

    n=1 and n=2 (no interior to compare), all-zeros (no runs at all), all-ones
    (one run per line, full length), a single point (isolated in both
    directions), the identity (nothing but the line that self_paired removes),
    one long off-diagonal (what a lagged coupling looks like), and non-square,
    which is the cross-recurrence case and the one an auto-recurrence
    assumption silently gets wrong.
    """
    rng = np.random.default_rng(20240607)
    for rows in (1, 2, 3, 4, 5, 8, 13):
        for cols in (1, 2, 3, 4, 5, 8, 13):
            for density in (0.0, 0.03, 0.2, 0.5, 0.85, 1.0):
                yield (rng.random((rows, cols)) < density).astype(np.uint8)
    for n in (1, 2, 3, 7, 50, 101):
        zeros = np.zeros((n, n), dtype=np.uint8)
        yield zeros
        yield np.ones((n, n), dtype=np.uint8)
        identity = zeros.copy()
        np.fill_diagonal(identity, 1)
        yield identity
        point = zeros.copy()
        point[n // 2, n // 2] = 1
        yield point
        line = zeros.copy()
        for i in range(n - 1):
            line[i, i + 1] = 1
        yield line
        yield (rng.random((n, 3 * n)) < 0.25).astype(np.uint8)
        yield (rng.random((3 * n, n)) < 0.25).astype(np.uint8)


def test_the_fast_path_and_line_lengths_agree_exactly():
    """Exact equality, not approximate, on every degenerate shape there is."""
    checked = 0
    for m in _degenerate_and_random_matrices():
        square = m.shape[0] == m.shape[1]
        for self_paired in ((False, True) if square else (False,)):
            b = np.ascontiguousarray(m, dtype=bool)
            diag = rec.line_lengths(m, "diagonal", 2, self_paired)
            vert = rec.line_lengths(m, "vertical", 2)

            assert rec._on_line_sum(b, True, self_paired) == float(np.sum(diag)), (
                f"DET numerator, shape {m.shape}, self_paired={self_paired}")
            assert rec._on_line_sum(b, False) == float(np.sum(vert)), (
                f"LAM numerator, shape {m.shape}, self_paired={self_paired}")
            assert rec._longest_diagonal_run(b, self_paired) == (
                int(np.max(diag)) if diag.size else 0), (
                f"L_MAX, shape {m.shape}, self_paired={self_paired}")
            checked += 1
    assert checked > 400, f"the generator stopped producing cases: {checked}"


def test_a_longest_run_of_one_is_not_a_line():
    """`line_lengths` filters to >= 2, so a lone recurrent cell reports zero.

    Without the floor the fast path returns 1 here and L_MAX becomes one
    sampling interval of nothing.
    """
    lone = np.zeros((5, 5), dtype=bool)
    lone[1, 3] = True
    assert rec._longest_diagonal_run(lone, self_paired=False) == 0
    assert rec.line_lengths(lone, "diagonal", 2).size == 0


def test_the_self_paired_exclusion_needs_no_copy_of_the_matrix():
    """Blanking the line of identity is a subtraction, and it is exact."""
    m = _auto(40)
    b = np.ascontiguousarray(m, dtype=bool)
    before = b.copy()
    rec._on_line_sum(b, True, self_paired=True)
    rec._longest_diagonal_run(b, self_paired=True)
    assert np.array_equal(b, before), "the matrix was mutated"
