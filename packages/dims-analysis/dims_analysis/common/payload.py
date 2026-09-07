"""How numbers are written into a browser payload.

The JSON a dashboard loads is a *picture*, not a measurement. Every value in it
becomes a pixel's colour on a heatmap, or a point on a line — a few hundred
distinguishable levels at best. Writing each one as a full float64
(``0.5940133868313864``, seventeen significant digits) claims a precision the
measurement never had and costs about four times the file size for it.

The analysis is unaffected: it lives in the .npz beside the JSON, at float32.
This module only governs the drawing layer.

**Significant figures, not decimal places.** This distinction is the whole
reason this module exists rather than being one call to round():

    value        6 significant figures     6 decimal places
    3.21e-08     3.21e-08                  0.0        <- destroyed
    0.594013…    0.594013                  0.594013

Cross-wavelet power spans eight orders of magnitude, so rounding it to a fixed
number of decimal places silently zeroes the quiet cells. That is the same
class of error — a quiet value replaced by a confident wrong one — that this
codebase has spent a lot of effort removing.
"""
from __future__ import annotations

import math

#: Significant figures kept in a browser payload. Six is far more than a screen
#: can show and about four times smaller on disk than float64 repr. Recorded in
#: every output file as `precision.significant_figures`, so a file says what it
#: is rather than leaving a reader to guess.
PAYLOAD_SIGNIFICANT_FIGURES = 6


def round_significant(x, figures: int = PAYLOAD_SIGNIFICANT_FIGURES):
    """Round one number to `figures` significant figures. Non-numbers pass through.

    Integers are returned untouched. Several fields are counts or array indices
    -- a recurrence plot's sparse matrix is tens of thousands of [row, col]
    pairs -- and turning those into floats is both wrong and larger on disk:
    "7.0" against "7", times seventeen thousand.
    """
    if x is None or isinstance(x, bool) or isinstance(x, int):
        return x
    if not isinstance(x, float):
        return x
    if not math.isfinite(x):
        return None                      # NaN/inf have no JSON literal
    if x == 0:
        return x
    return float(f"%.{figures}g" % x)


def round_payload(obj, figures: int = PAYLOAD_SIGNIFICANT_FIGURES):
    """Round every number in a nested structure, in place of writing full repr.

    NaN and infinity become None, because json.dump writes bare NaN/Infinity
    tokens that JSON.parse rejects outright — one such value makes a whole
    study's output unreadable in a browser.
    """
    if isinstance(obj, dict):
        return {k: round_payload(v, figures) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [round_payload(v, figures) for v in obj]
    return round_significant(obj, figures)


def precision_note(figures: int = PAYLOAD_SIGNIFICANT_FIGURES) -> dict:
    """The block every output carries, so the file describes its own precision."""
    return {
        "significant_figures": figures,
        "note": ("This file is the browser payload and is rounded. The full-resolution "
                 "analysis is the .npz beside it — read that, not this, for anything "
                 "beyond drawing."),
    }
