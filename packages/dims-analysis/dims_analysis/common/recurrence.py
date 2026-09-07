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


def recurrence_rate(matrix, self_paired: bool) -> float:
    """Share of the non-trivial cells that are recurrent."""
    m = np.asarray(matrix)
    total = m.size
    count = float(np.sum(m))
    if self_paired:
        n = m.shape[0]
        count -= n           # the line of identity: every point recurs with itself
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
    """(RR, DET, LAM, L_MAX) over one window, with a consistent denominator.

    DET and LAM are shares of the recurrent points that lie on lines. Whatever
    the line extraction ignores, the denominator must ignore too, or the metric
    is deflated by construction.
    """
    m = np.asarray(matrix)
    if m.size == 0:
        return 0.0, 0.0, 0.0, 0.0

    rr = recurrence_rate(m, self_paired)
    counted = float(np.sum(m))
    if self_paired:
        counted -= min(m.shape)      # the same points the line extraction skips
    if counted <= 0:
        return float(rr), 0.0, 0.0, 0.0

    diag = line_lengths(m, "diagonal", min_line, self_paired)
    vert = line_lengths(m, "vertical", min_line)

    det = float(np.sum(diag) / counted)
    lam = float(np.sum(vert) / counted)
    l_max = float(np.max(diag) * dt) if diag.size else 0.0
    return float(rr), det, lam, l_max
