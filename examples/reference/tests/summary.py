"""What an output *means*, extracted from however it is currently stored.

The baseline below pins numbers, not bytes. The file format is about to change
-- index pairs become bit-packed, `.npz` goes away -- and a baseline of bytes
would fail on that by design while telling us nothing about whether the
analysis still gives the same answers. This module is the one place that knows
how to read a payload, so when the format changes only this file moves and
every expected value stays put.

Everything here is a scalar or a short list: enough to catch a changed number,
small enough to read in a diff.
"""
from __future__ import annotations

import numpy as np


def _grid(field):
    return np.array([[np.nan if c is None else c for c in row] for row in field],
                    dtype=float)


def _vector(field):
    return np.array([np.nan if x is None else x for x in field], dtype=float)


# --- how a recurrence matrix is read today -----------------------------------
#
# Step 4 replaces `sparse_matrix` with a bit-packed bitmap. When it does, this
# function grows a branch on `encoding` and nothing else in the baseline moves.

def recurrence_matrix(visualization) -> np.ndarray:
    n = visualization["matrix_size"]
    m = np.zeros((n, n), dtype=np.uint8)
    for row, col in visualization["sparse_matrix"]:
        if row < n and col < n:
            m[row, col] = 1
    return m


def diagonal_offsets(matrix, min_fraction=0.25):
    """Offsets whose diagonal is recurrent for at least `min_fraction` of it."""
    n = min(matrix.shape)
    out = []
    for k in range(-(n - 1), n):
        d = np.diagonal(matrix, offset=k)
        if d.size >= 0.5 * n and d.mean() >= min_fraction:
            out.append(int(k))
    return out


def _windowed(entry, name):
    values = [v for v in (entry.get("windowed_metrics") or {}).get(name, [])
              if v is not None]
    return round(float(np.mean(values)), 6) if values else None


def recurrence_summary(entry) -> dict:
    """One data type of an RQA or cRQA payload."""
    vis = entry["visualization"]
    matrix = recurrence_matrix(vis)
    return {
        "threshold": entry.get("threshold"),
        "recurrence_rate": entry.get("recurrence_rate"),
        "target_recurrence": entry.get("target_recurrence"),
        "warned": bool(entry.get("recurrence_rate_warning")),
        "matrix_size": vis["matrix_size"],
        "recurrent_cells": int(matrix.sum()),
        "reduction_factor": vis["reduction"]["factor"],
        "rate_full": vis["reduction"]["rate_full"],
        "rate_drawn": vis["reduction"]["rate_drawn"],
        # The structure itself, not just how much of it there is: this is what
        # a reduction that keeps the density and loses the lines would break.
        "diagonal_offsets": diagonal_offsets(matrix)[:12],
        "mean_DET": _windowed(entry, "DET"),
        "mean_LAM": _windowed(entry, "LAM"),
        "mean_RR": _windowed(entry, "RR"),
    }


def coherence_summary(entry) -> dict:
    """One pair of a cross-wavelet payload."""
    vis = entry["visualization"]
    coherence = _grid(vis["coherence"])
    period = np.asarray(vis["period"], dtype=float)
    coi = np.asarray(vis["coi"], dtype=float)
    level = _vector(vis["sig95_wtc"]) if vis.get("sig95_wtc") else None
    outside = period[:, None] < coi[None, :]
    phase = _grid(vis["phase"])

    summary = {
        "n_periods": len(period),
        "n_times": len(vis["time"]),
        "period_range": [round(float(period[0]), 6), round(float(period[-1]), 6)],
        "mean_coherence": round(float(np.nanmean(coherence)), 6),
        "mean_coherence_outside_coi": round(
            float(np.nanmean(np.where(outside, coherence, np.nan))), 6),
        "mean_power": round(float(np.nanmean(_grid(vis["power"]))), 6),
        # Circular mean: an angle averaged as a scalar turns +179 and -179
        # into 0, which is the defect this pins.
        "mean_phase_rad": round(
            float(np.angle(np.nanmean(np.exp(1j * phase)))), 6),
        "wtc_signif_fraction": entry["statistics"].get("wtc_signif_fraction"),
        # The *power* significance, which is a different field answering a
        # different question -- and which the baseline was blind to until a
        # 1.5x change in it passed unnoticed. It is what the built-in tab gates
        # its phase arrows on, so a change here changes what is drawn.
        "mean_sig95_xwt": round(float(np.nanmean(_grid(vis["sig95_xwt"]))), 6),
        "sig95_xwt_above_one": round(
            float(np.nanmean(_grid(vis["sig95_xwt"]) > 1.0)), 6),
        "alpha1": entry.get("alpha1"),
        "alpha2": entry.get("alpha2"),
    }
    if level is not None:
        summary["mean_sig95_wtc"] = round(float(np.nanmean(level)), 6)
        summary["n_unusable_levels"] = int(np.isnan(level).sum())
    return summary
