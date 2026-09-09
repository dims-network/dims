"""Reducing an analysis for the browser without lying about it.

The rule differs by what is being reduced, and for a recurrence matrix there are
two ways to be wrong, not one.

A **continuous series** is block-averaged. Taking every nth sample is decimation
with no low-pass filter: it does not remove detail, it folds it back onto the
frequencies that remain.

A **recurrence matrix is binary**, and it has two properties a reader takes from
the picture: where the recurrent structure is, and how much of the plot is
recurrent -- the recurrence rate printed beside it. A reduction has to keep both,
and the two obvious methods each keep one and destroy the other:

  striding    keeps the density (7% stays 7%) and destroys the structure. It does
              not blur a diagonal line, it punches holes in it, and a line one
              cell OFF the main diagonal disappears completely, because the
              sampled rows and columns never intersect it. That is exactly the
              structure cross-recurrence exists to find: a lagged coupling is an
              off-diagonal line.

  block-OR    keeps the structure and destroys the density. Any block containing
              one recurrent point becomes recurrent, so density rises with the
              square of the factor. Measured on an ORTHO recording at factor 9,
              a 10.9% matrix reduced to 54.4%: half the plot solid, beside a
              caption saying 10.9%.

So: block-average the binary matrix into a per-block recurrence *fraction*, then
keep the densest blocks -- as many as reproduce the original recurrence rate.
Structure survives because a block on a line is denser than the background
around it; the rate survives because it is what the selection is calibrated to.

One regime cannot have both, and the code says so rather than pretending: when a
block holds less than one recurrent point on average, a structure spanning
n/factor blocks does not fit in a budget of rate*(n/factor)^2 blocks. There
structure wins and the payload records the rate it actually drew, so nothing
silently contradicts the caption. A thresholded recurrence matrix never lands
there -- its rate is chosen, typically 7%.

Whichever is used, the factor is recorded in the payload, because a reader who
cannot tell a 500-point plot from a 6000-point one has no way to know what the
axis means.
"""
from __future__ import annotations

import numpy as np


def factor_for(n_points: int, max_points: int) -> int:
    """The integer reduction factor, or 1 when nothing needs reducing.

    Rounds **up**, so that `n_points // factor <= max_points` actually holds.
    Floor division does not: 999 points against a cap of 500 gave a factor of
    1 and drew all 999, twice the cap and four times the matrix cells. Anything
    between max_points and 2*max_points was not reduced at all.

    That was invisible in a series plot -- 530 points where 500 was asked for
    looks fine -- and expensive in a recurrence plot, which is quadratic in it.
    On an ORTHO recording whose categorical gaze recurrence rate is 69%, the
    unreduced 896-point matrix wrote 615,095 sparse index pairs and a 67 MB
    browser payload.
    """
    if max_points <= 0 or n_points <= max_points:
        return 1
    return max(1, -(-n_points // max_points))


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


def block_mode(a, factor: int):
    """Block-reduce a categorical series by taking each block's commonest code.

    The categorical counterpart of `block_mean`. Averaging area-of-interest
    codes would produce a code nobody looked at; taking every nth sample folds
    detail back onto the samples that remain, exactly as it does for a
    continuous series. The mode is the value that was actually true for most of
    the block.

    Ties go to the smaller code, which is arbitrary but deterministic.
    """
    a = np.asarray(a)
    if factor <= 1:
        return a
    keep = (a.shape[0] // factor) * factor
    if keep == 0:
        return a
    blocks = a[:keep].reshape(keep // factor, factor)
    out = np.empty(blocks.shape[0], dtype=a.dtype)
    for i, block in enumerate(blocks):
        values, counts = np.unique(block, return_counts=True)
        out[i] = values[np.argmax(counts)]
    return out


def block_binary(m, factor: int):
    """Reduce a binary matrix keeping both its structure and its density.

    Returns a uint8 matrix whose recurrence rate matches the input's to within
    one block, and in which a recurrent line remains a line.

    Selection is by rank rather than by a density threshold: the number of
    blocks to keep is fixed at ``round(rate * n_blocks)``, so the output rate is
    exact rather than depending on where a quantile happens to land among ties.
    Ties among equally dense blocks are broken by ``argpartition``'s ordering --
    arbitrary, but deterministic for a given input.
    """
    m = np.asarray(m)
    if factor <= 1:
        return m

    rows = (m.shape[0] // factor) * factor
    cols = (m.shape[1] // factor) * factor
    if rows == 0 or cols == 0:
        return m

    trimmed = m[:rows, :cols]
    blocks = trimmed.reshape(rows // factor, factor, cols // factor, factor)
    density = blocks.mean(axis=(1, 3))

    rate = float(trimmed.mean())
    n_blocks = density.size
    if rate <= 0 or n_blocks == 0:
        return np.zeros(density.shape, dtype=np.uint8)
    if rate >= 1:
        return np.ones(density.shape, dtype=np.uint8)

    # Can the budget hold a full-length structure at all? A line spans
    # n/factor blocks; the budget is rate * (n/factor)^2 blocks. It fits when
    #     rate * n >= factor.
    # Below that the two goals are genuinely incompatible and keeping the rate
    # would reduce a line to a couple of dots, so structure wins and the caller
    # records the rate it actually drew. A thresholded recurrence matrix is far
    # above this line -- at 7% of 1228 points the budget covers a line 43 times
    # over -- so this branch is for degenerate input, not for real studies.
    span = min(rows, cols)
    if rate * span < factor:
        return (density > 0).astype(np.uint8)

    keep = int(round(rate * n_blocks))
    keep = max(1, min(n_blocks, keep))

    flat = density.ravel()
    winners = np.argpartition(flat, n_blocks - keep)[n_blocks - keep:]
    out = np.zeros(n_blocks, dtype=np.uint8)
    out[winners] = 1
    return out.reshape(density.shape)


def rate_of(m) -> float:
    """Share of a binary matrix that is recurrent. For the reduction report."""
    a = np.asarray(m)
    return float(a.mean()) if a.size else 0.0
