"""Reducing an analysis for the browser without lying about it.

Two rules, and they differ by what is being reduced.

A **continuous series** is block-averaged. Taking every nth sample is decimation
with no low-pass filter: it does not remove detail, it folds it back onto the
frequencies that remain. The cross-wavelet step learned this and block-averages;
the recurrence steps kept striding.

A **recurrence matrix is binary**, and averaging it is meaningless -- the result
is a fraction, not a recurrence. The right reduction is block-OR: a block that
contains a recurrent point stays recurrent. Striding is worse here than for a
series, because it does not blur a diagonal line, it punches holes in it: a
diagonal of length L survives at length L/factor only if it happens to land on
the sampled indices, so DET and L_MAX read from a strided plot are wrong in a
direction nobody can predict.

Whichever is used, the factor is recorded in the payload, because a reader who
cannot tell a 500-point plot from a 6000-point one has no way to know what the
axis means.
"""
from __future__ import annotations

import numpy as np


def factor_for(n_points: int, max_points: int) -> int:
    """The integer reduction factor, or 1 when nothing needs reducing."""
    if max_points <= 0 or n_points <= max_points:
        return 1
    return max(1, n_points // max_points)


def block_mean(a, factor: int):
    """Block-average along the first axis. For continuous series and time."""
    a = np.asarray(a)
    if factor <= 1:
        return a
    keep = (a.shape[0] // factor) * factor
    if keep == 0:
        return a
    head = a[:keep].reshape(keep // factor, factor, *a.shape[1:])
    return head.mean(axis=1)


def block_any(m, factor: int):
    """Block-OR a binary matrix: a block with any recurrence stays recurrent."""
    m = np.asarray(m)
    if factor <= 1:
        return m
    rows = (m.shape[0] // factor) * factor
    cols = (m.shape[1] // factor) * factor
    if rows == 0 or cols == 0:
        return m
    blocks = m[:rows, :cols].reshape(rows // factor, factor, cols // factor, factor)
    return blocks.max(axis=(1, 3))
