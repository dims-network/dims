"""What the recurrence analyses need from their input, and what they refuse.

Every step had its own numbers, written as bare literals in three files: `10`
in rqa.py, a hard-coded `10` in crqa.py, another `10` in ORTHO's categorical
step, and `50` in crosswavelet.py. None of them had an upper bound at all,
which matters more than it sounds: a recurrence analysis builds a dense N x N
distance matrix, so the cost is quadratic and unbounded. A full Karnatak lesson
is ~58,000 samples, which is a 27 GB float64 matrix on a machine with 16 GB.

So the limits live here, with the arithmetic that produces them, and a refusal
names the number rather than letting an allocation fail somewhere inside SciPy.
"""
from __future__ import annotations

#: Fewer points than this cannot support a recurrence estimate worth drawing.
MIN_POINTS = 10

#: A series whose standard deviation is at or below this has nothing to
#: measure: every recurrence and coherence analysis here normalises by it.
MIN_VARIANCE = 0.0

#: How much memory a recurrence analysis may ask for, in bytes. `cdist` returns
#: float64, and the boolean matrix and the intermediates roughly double it, so
#: the real peak is about twice what `matrix_bytes` reports. 2 GB therefore
#: means "up to about 4 GB in practice", which is a reasonable ceiling on a
#: 16 GB laptop and leaves the machine usable.
MAX_MATRIX_BYTES = 2 * 1024 ** 3

_BYTES_PER_CELL = 8          # float64, what scipy.spatial.distance.cdist returns


class InputTooLarge(Exception):
    """Raised before allocating, not after failing to."""


def matrix_bytes(n_points: int) -> int:
    """The distance matrix a recurrence analysis of `n_points` would allocate."""
    return int(n_points) ** 2 * _BYTES_PER_CELL


def max_points(budget: int = MAX_MATRIX_BYTES) -> int:
    """The longest series that fits the budget."""
    return int((budget / _BYTES_PER_CELL) ** 0.5)


def check_length(n_points: int, what: str, budget: int = MAX_MATRIX_BYTES) -> None:
    """Refuse an input that cannot be analysed, and say what to do about it.

    The message names the actual size, the limit, and the two things a
    researcher can do -- because "MemoryError" from inside cdist tells them
    none of that.
    """
    needed = matrix_bytes(n_points)
    if needed <= budget:
        return
    limit = max_points(budget)
    raise InputTooLarge(
        f"{what}: {n_points:,} samples would need a {needed / 1024 ** 3:.1f} GB "
        f"distance matrix, and the limit is {budget / 1024 ** 3:.0f} GB "
        f"({limit:,} samples). A recurrence analysis is quadratic in the length "
        f"of the recording. Either analyse an excerpt, or resample to a lower "
        f"rate -- and note that resampling changes which timescales are "
        f"visible at all, so it is a decision about the analysis, not a "
        f"workaround.")
