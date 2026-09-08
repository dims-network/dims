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
    off-diagonal set, and is half the memory.
    """
    d = np.asarray(distance_matrix)
    if self_paired:
        values = d[np.triu_indices_from(d, k=1)]
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

    diag = line_lengths(m, "diagonal", min_line, self_paired)
    vert = line_lengths(m, "vertical", min_line)

    det = float(np.sum(diag) / diagonal_population)
    lam = float(np.sum(vert) / recurrent)
    l_max = float(np.max(diag) * dt) if diag.size else 0.0
    return float(rr), det, lam, l_max
