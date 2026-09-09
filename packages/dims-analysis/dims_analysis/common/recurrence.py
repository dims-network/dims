"""One implementation of the recurrence quantities, for RQA and cross-RQA.

The two steps had their own copies and the numbers were not comparable. The
difference looked like two conventions:

    RQA :  RR = (sum(R) - n) / (n^2 - n)      threshold from the upper triangle
    cRQA:  RR =  sum(R)      /  n*m           threshold from the whole matrix

They are the same rule -- *ignore the trivially recurrent comparison of a point
with itself* -- written two ways, because in cross-recurrence there is nothing
trivial to ignore: the two series are different, so no cell is recurrent by
construction. Unifying the formulas rather than the rule would have put the
artefact INTO auto-RQA: the line of identity is a single diagonal of length n,
so counting it makes L_MAX the length of the whole recording, always.

So there is one rule and one implementation here, and `self_paired` says which
situation it is applied to. That also fixes a real defect: DET and LAM took
their line lengths with the line of identity excluded and divided by a
recurrence count that included it, deflating both by roughly 14/W at a 7% target
-- 2% over a 600-point window, 24% over a 60-point one.
"""
from __future__ import annotations

import numpy as np


def threshold_for_target(distance_matrix, target_recurrence: float,
                         self_paired: bool) -> float:
    """The distance at which `target_recurrence` of the non-trivial cells recur.

    For a self-paired (auto-recurrence) matrix the zero diagonal is excluded --
    it is n zeros that would drag the percentile down. The matrix is symmetric,
    so the strict upper triangle gives the same percentile as the full
    off-diagonal set, from half as many values.

    It is selected with a boolean mask, and that is where this used to claim a
    saving and spend it instead. `np.triu_indices_from` returns two int64 index
    arrays -- sixteen bytes of index per eight bytes of distance -- built from
    an n x n boolean array it then discards. Measured at n=4000, the transient
    peak above the matrix was 1.50x the matrix with the index arrays and 1.00x
    with a mask; the ratio is flat in n. At the 16,384-sample bound in limits.py
    that is 3 GiB of scratch beside a 2 GiB matrix, against 2 GiB -- and this
    module's budget comment allows "about twice what matrix_bytes reports".

    Boolean indexing selects row-major, exactly the order `triu_indices`
    produces its pairs in, so the two build the same array element for element
    and the same percentile bit for bit. That equality is the point: the full
    off-diagonal set is *not* interchangeable here. It lands between different
    order statistics and moves the threshold by ~5e-5 relative, against a
    baseline that pins it at 1e-6.
    """
    d = np.asarray(distance_matrix)
    if self_paired:
        rows = np.arange(d.shape[0])[:, None]
        cols = np.arange(d.shape[-1])[None, :]
        values = d[rows < cols]
    else:
        values = d.ravel()
    if values.size == 0:
        return 0.0
    return float(np.percentile(values, target_recurrence * 100))


#: How far the achieved recurrence rate may sit from the target before it is
#: worth saying so. DET and LAM depend strongly on the rate, so two recordings
#: analysed at materially different rates are not comparable -- and that is a
#: fact about the data, not an error, so it is reported rather than raised.
RATE_TOLERANCE = 0.01


def rate_report(target: float, achieved: float, tolerance: float = RATE_TOLERANCE):
    """`(target, achieved, warning-or-None)` for the payload.

    The threshold is a percentile of the distance matrix, so a signal with many
    exactly-equal distances lands on a plateau and the target cannot be hit.
    That is common in real data -- a game piece at rest, a quantised sensor --
    and it went unrecorded: an ORTHO series reached 12.7% against a 7% target,
    and a signal quantised to four levels reaches 33.7%, both silently.
    """
    target = float(target)
    achieved = float(achieved)
    if abs(achieved - target) <= tolerance:
        return target, achieved, None
    return target, achieved, (
        f"the threshold could not reach the {target:.1%} target; this analysis "
        f"is at {achieved:.1%}. Many exactly-equal distances (a quantised or "
        f"partly-still signal) put the percentile on a plateau. Metrics that "
        f"depend on the recurrence rate, DET and LAM among them, are not "
        f"comparable with a recording analysed at {target:.1%}.")


def recurrence_rate(matrix, self_paired: bool) -> float:
    """Share of the non-trivial cells that are recurrent.

    `self_paired` says the matrix has a line of identity -- every point recurs
    with itself -- which is not a finding and is removed from both the count
    and the total. That subtraction is only valid if the line is actually
    there, and when it is not the result goes **negative**: a constant signal
    once produced -0.000977517, which is -n/(n^2-n), and it reached a dashboard
    caption. A negative share of cells is not a small error to tolerate, it is
    a sign that the input is not a recurrence matrix, so this says so.
    """
    m = np.asarray(matrix)
    total = m.size
    count = float(np.sum(m))
    if self_paired:
        n = m.shape[0]
        if count < n:
            raise ValueError(
                f"self_paired says every point recurs with itself, so a "
                f"{n}x{n} matrix must have at least {n} recurrent cells; this "
                f"one has {count:.0f}. Either the matrix is not a recurrence "
                f"matrix, or it was built from a signal with no variance.")
        count -= n
        total -= n
    return float(count / total) if total > 0 else 0.0


def line_lengths(matrix, direction: str = "diagonal", min_len: int = 2,
                 self_paired: bool = False) -> np.ndarray:
    """Lengths of consecutive recurrent runs, diagonally or vertically.

    One signature. The two steps shipped two incompatible ones -- one took
    `exclude_main_diagonal`, the other did not -- in adjacent files, while the
    contract claimed the shared helpers had ended exactly that.
    """
    m = np.asarray(matrix)
    lengths: list = []
    rows, cols = m.shape

    if direction == "diagonal":
        for k in range(-rows + 1, cols):
            if self_paired and k == 0:
                continue          # the line of identity is not a finding
            diag = m.diagonal(k)
            if len(diag) < min_len:
                continue
            lengths.extend(_runs(diag, min_len))
    elif direction == "vertical":
        for j in range(cols):
            col = m[:, j]
            if np.sum(col) < min_len:
                continue
            lengths.extend(_runs(col, min_len))
    else:
        raise ValueError(f"unknown direction: {direction!r}")

    return np.array(lengths)


def _runs(line, min_len: int) -> list:
    padded = np.pad(np.asarray(line), (1, 1), "constant").astype(int)
    diff = np.diff(padded)
    starts = np.where(diff == 1)[0]
    ends = np.where(diff == -1)[0]
    lens = ends - starts
    return list(lens[lens >= min_len])


def _on_line_sum(b, diagonal: bool, self_paired: bool = False) -> int:
    """`sum(run lengths >= 2)` along one direction, without listing the runs.

    `window_metrics` consumes `line_lengths` only through `np.sum` and
    `np.max`, and building the histogram to throw it away is the dominant cost
    of the recurrence analyses: at a 1000-sample window the two calls are 48 ms
    of Python looping over 2n-1 diagonals and n columns, against 0.57 s for the
    whole `cdist` the windows are cut from.

    The identity that removes the loop: every recurrent cell belongs to exactly
    one run, so the runs of length >= 2 hold every recurrent cell except the
    isolated ones -- those with no recurrent neighbour on either side along the
    line. Counting *those* is two shifted comparisons of the matrix with itself:

        adjacent = cells whose predecessor along the line is also recurrent
        interior = cells recurrent on both sides

    A cell has at least one neighbour iff it is in the predecessor set or the
    successor set; both have `adjacent` members and they intersect in
    `interior`, so

        sum(runs >= 2) = total - isolated = 2 * adjacent - interior

    The two guards in `line_lengths` drop nothing, which is why this agrees with
    it exactly rather than nearly: a run inside a line of length L is at most L
    long, so a line shorter than `min_len` can hold no qualifying run, and a run
    of length L needs L recurrent cells, so a column summing to less than
    `min_len` can hold none either. Both are speed guards.

    This is the `min_len == 2` case only. Above it the excluded runs are no
    longer just the isolated cells -- at min_len 3 they are the length-1 and
    length-2 runs, which an isolated-cell count cannot separate -- so
    `window_metrics` falls back to `line_lengths` there.
    """
    n, m = b.shape
    if diagonal:
        adjacent = int(np.count_nonzero(b[1:, 1:] & b[:-1, :-1])) \
            if n > 1 and m > 1 else 0
        interior = int(np.count_nonzero(b[1:-1, 1:-1] & b[:-2, :-2] & b[2:, 2:])) \
            if n > 2 and m > 2 else 0
        if self_paired:
            # The line of identity is not scanned. Subtracting its own counts is
            # exact rather than approximate: a cell's neighbours along a diagonal
            # lie on that same diagonal, so each diagonal contributes to
            # `adjacent` and `interior` independently of every other. That is
            # also why no copy of the matrix is needed to blank it out.
            k = np.diagonal(b)
            if k.size > 1:
                adjacent -= int(np.count_nonzero(k[1:] & k[:-1]))
            if k.size > 2:
                interior -= int(np.count_nonzero(k[1:-1] & k[:-2] & k[2:]))
    else:
        adjacent = int(np.count_nonzero(b[1:] & b[:-1])) if n > 1 else 0
        interior = int(np.count_nonzero(b[1:-1] & b[:-2] & b[2:])) if n > 2 else 0
    return 2 * adjacent - interior


def _longest_diagonal_run(b, self_paired: bool, min_len: int = 2) -> int:
    """The longest diagonal run, in one pass with O(columns) working memory.

    DET and LAM need only sums, but L_MAX needs a real maximum, so this is the
    one quantity that still has to look at run lengths. It carries the standard
    recurrence -- the run ending at (i, j) is one longer than the run ending at
    (i-1, j-1), or zero -- a row at a time, so the state is two int32 vectors of
    `m` and nothing grows with `n`.

    The alternative considered was skewing the matrix so diagonals become
    columns and taking one fully vectorised run-length pass. It is exact, but it
    costs about three copies of an n x (n + m) array -- 1.6 GB at the
    16,384-sample bound in limits.py, beside a distance matrix that is already
    2 GB -- and it measured slower at every window size tried, being bound by
    allocation rather than arithmetic. This is here so nobody re-proposes it.

    `self_paired` blanks the line of identity by zeroing the counter at (i, i),
    which both excludes that cell and restarts the run below it -- exactly what
    "this diagonal is not scanned" means. The `min_len` floor is `line_lengths`'
    filter: a longest run of one is not a line, and it reports zero.
    """
    n, m = b.shape
    ending = np.zeros(m, dtype=np.int32)
    carried = np.empty(m, dtype=np.int32)
    longest = 0
    for i in range(n):
        carried[1:] = ending[:m - 1]
        carried[1:] += 1
        carried[0] = 1
        carried *= b[i]                  # zero wherever the cell is not recurrent
        if self_paired and i < m:
            carried[i] = 0
        row_longest = int(carried.max())
        if row_longest > longest:
            longest = row_longest
        ending, carried = carried, ending
    return longest if longest >= min_len else 0


def window_metrics(matrix, dt: float, min_line: int = 2,
                   self_paired: bool = False) -> tuple:
    """(RR, DET, LAM, L_MAX) over one window, each with its own denominator.

    DET and LAM are shares of the recurrent points that lie on lines, and the
    rule is that whatever a line extraction ignores, its denominator must
    ignore too. **The two extractions ignore different things**, so they cannot
    share one:

      * the diagonal scan skips the line of identity (`k == 0`), so DET's
        denominator excludes those `n` points;
      * the vertical scan does not skip anything, so LAM's denominator is every
        recurrent point.

    The line quantities are computed without building the run-length histogram;
    `line_lengths` still returns it for anyone who needs it -- ENTR and mean-L
    do, and docs/analyses/rqa.md points at it -- and is the reference
    implementation this path is tested against, on 408 matrices including every
    degenerate shape. Measured 23x faster at a 1000-sample window, on the phase
    that dominates a recurrence analysis.

    One shared denominator got this wrong in both directions in turn. It first
    deflated DET, by excluding the identity line from the numerator and not the
    denominator -- 17-25 % low on real data. Correcting that by subtracting `n`
    from the shared denominator then **inflated LAM**, whose numerator does
    include those points: measured on a pure sine, LAM came out 0.9681 where
    pyrqa gives 0.9548, and on other signals it exceeded 1.0 -- which a share
    of points cannot do. With the denominators separated, LAM is 0.9548, the
    same to four decimals as the published implementation.
    """
    m = np.asarray(matrix)
    if m.size == 0:
        return 0.0, 0.0, 0.0, 0.0

    rr = recurrence_rate(m, self_paired)
    recurrent = float(np.sum(m))
    # DET's population: what the diagonal scan could have found.
    diagonal_population = recurrent - (min(m.shape) if self_paired else 0)
    if recurrent <= 0 or diagonal_population <= 0:
        return float(rr), 0.0, 0.0, 0.0

    if min_line == 2:
        b = np.ascontiguousarray(m, dtype=bool)
        diagonal_sum = _on_line_sum(b, True, self_paired)
        vertical_sum = _on_line_sum(b, False)
        longest = _longest_diagonal_run(b, self_paired, min_line)
    else:
        # The identity behind the fast path is the min_line == 2 case; above it
        # the excluded runs are no longer just the isolated cells.
        diag = line_lengths(m, "diagonal", min_line, self_paired)
        vert = line_lengths(m, "vertical", min_line)
        diagonal_sum = float(np.sum(diag))
        vertical_sum = float(np.sum(vert))
        longest = float(np.max(diag)) if diag.size else 0.0

    det = float(diagonal_sum / diagonal_population)
    lam = float(vertical_sum / recurrent)
    l_max = float(longest * dt)
    return float(rr), det, lam, l_max
