"""Where the sliding analysis windows go, for RQA and cross-RQA.

DET, LAM, RR and L_MAX are all shares of the structure inside one window, and
every one of them moves with how long that window is. So the window is a
parameter of the result in exactly the way the recurrence rate is -- and the
same rule applies: **what was asked for and what was used are both recorded**,
because a number that is not the one that was ordered is only honest if it says
so.

Two things were wrong before this existed, and both were invisible.

The requested window and step were silently overridden::

    win_points  = min(win_points, max(2, n // 2))
    step_points = max(1, min(step_points, n_eff // 20))

Measured on the reference study: 20 s and 1 s were requested, 10.24 s and 0.5 s
were used, and nothing said so. The adaptation itself is right -- a 20 s window
does not fit twice in a 20.48 s recording, and one trivial window renders a
blank chart -- so it stays. Only the silence goes.

And it was done in *samples*, so the answer moved with the sampling rate. The
reference study carries the same 2 s sine at 50 Hz and at 100 Hz for exactly
this: the two came out with steps of 0.5 s and 0.51 s and last window centres
of 15.12 s and 15.32 s. Everything here is therefore decided in seconds, and
sample indices are derived from times at the end.

`crqa.py` carried a second copy of the old logic, so a change to one of them
was a change to one of them.
"""
from __future__ import annotations

import numpy as np

#: Fewer windows than this makes a metric chart unreadable, so a window that
#: would produce fewer is shortened rather than honoured. Twenty is what the
#: two step implementations already used, kept so this refactor moves no number
#: it does not have to.
MIN_WINDOWS = 20

#: A window shorter than this many samples cannot contain a line of length 2 in
#: any useful number, so there is nothing to quantify.
MIN_WINDOW_POINTS = 2


class WindowPlan:
    """Where the windows are, and the difference between that and the request.

    `starts` and `length` are sample indices, because that is what slices a
    matrix; everything reported is seconds, because that is what a reader
    compares between recordings.
    """

    def __init__(self, starts, length, dt, requested, used, warning):
        self.starts = starts
        self.length = length
        self.dt = dt
        self.requested = requested          # (length_sec, step_sec)
        self.used = used                    # (length_sec, step_sec)
        self.warning = warning

    def __len__(self):
        return len(self.starts)

    def centres(self, time_values):
        """The time at the middle of each window, from the real time axis.

        Taken from `time_values` rather than computed, so a recording with a
        gap or a non-zero start reports where its windows actually were.
        """
        last = len(time_values) - 1
        return [float(time_values[min(s + self.length // 2, last)])
                for s in self.starts]

    def report(self) -> dict:
        """The payload block. Requested and used, both, always."""
        block = {
            "length_requested_sec": round(float(self.requested[0]), 6),
            "length_used_sec": round(float(self.used[0]), 6),
            "step_requested_sec": round(float(self.requested[1]), 6),
            "step_used_sec": round(float(self.used[1]), 6),
            "n_windows": len(self.starts),
        }
        if self.warning:
            block["warning"] = self.warning
        return block


def plan(n: int, dt: float, window_sec: float, step_sec: float,
         min_windows: int = MIN_WINDOWS) -> WindowPlan:
    """Windows of `window_sec`, every `step_sec`, over `n` samples at `dt`.

    Shortened when the recording cannot hold `min_windows` of them, which is
    the adaptation the two steps already made -- stated here instead of
    happening quietly, and decided in seconds so it does not move with `dt`.
    """
    if dt <= 0:
        raise ValueError(f"a sampling interval must be positive, not {dt}")
    span = n * dt
    requested = (float(window_sec), float(step_sec))

    # The longest window that still leaves room for `min_windows` of them at
    # any step, plus the floor of two samples. Both halves are in seconds.
    longest = max(span / 2.0, MIN_WINDOW_POINTS * dt)
    length_sec = min(float(window_sec), longest)
    length = max(MIN_WINDOW_POINTS, int(round(length_sec / dt)))
    length = min(length, n)
    length_sec = length * dt

    # What is left for the windows to slide over, and a step that fits
    # `min_windows` into it.
    slide_sec = max(span - length_sec, 0.0)
    step_used = min(float(step_sec), slide_sec / min_windows) if slide_sec > 0 \
        else float(step_sec)
    step_used = max(step_used, dt)          # never finer than the data

    # Starts are placed by rounding *times*, not by striding samples: that is
    # what keeps the axis the same at 50 Hz and at 100 Hz.
    n_windows = int(np.floor(slide_sec / step_used)) + 1 if slide_sec > 0 else 1
    starts = []
    for k in range(n_windows):
        start = int(round(k * step_used / dt))
        if start + length > n:
            break
        if not starts or start > starts[-1]:
            starts.append(start)
    if not starts:
        starts = [0]

    used = (length_sec, step_used)
    return WindowPlan(starts, length, dt, requested, used,
                      _warning(requested, used, len(starts), span))


def _warning(requested, used, n_windows, span):
    """Why the windows are not the ones that were asked for, or None.

    Worth a sentence rather than a flag: a reader comparing two studies needs
    to know that the metrics differ partly because the windows do, and DET and
    LAM are not comparable across window lengths any more than across
    recurrence rates.
    """
    length_moved = abs(used[0] - requested[0]) > 1e-9
    step_moved = abs(used[1] - requested[1]) > 1e-9
    if not (length_moved or step_moved):
        return None
    parts = []
    if length_moved:
        parts.append(f"the {requested[0]:g} s window was shortened to "
                     f"{used[0]:.4g} s")
    if step_moved:
        parts.append(f"the {requested[1]:g} s step was shortened to "
                     f"{used[1]:.4g} s")
    return (f"{' and '.join(parts)}, because a {span:.4g} s recording cannot "
            f"hold {MIN_WINDOWS} of the requested windows. DET and LAM depend "
            f"on the window length, so these are not comparable with an "
            f"analysis at {requested[0]:g} s.")
