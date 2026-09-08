"""Is this time series what it claims to be?

Sampling rate, gaps, drift, and whether it lines up with its video. These are
the failures that produce a plot which looks fine and means nothing.
"""
from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd


def load_series(path):
    """Read a DIMS time-series CSV as (time, values), in seconds.

    Matches the time column case-insensitively and takes the first other column,
    which is the same rule the analyses and the dashboard use.
    """
    df = pd.read_csv(path)
    df = df.rename(columns={c: "Time" for c in df.columns
                            if str(c).strip().lower() == "time"})
    if "Time" not in df.columns:
        raise ValueError(f"{path}: no Time column")
    value_cols = [c for c in df.columns if c != "Time"]
    if not value_cols:
        raise ValueError(f"{path}: no measurement column")
    mask = ~pd.isna(df[value_cols[0]])
    return df["Time"][mask].to_numpy(float), df[value_cols[0]][mask].to_numpy(float)


def signal_report(path, video_duration=None):
    """Facts about one series, and what looks wrong.

    `video_duration` in seconds, if you have it: a series that does not span its
    recording is the most common cause of a dashboard that looks empty at one
    end.
    """
    t, v = load_series(path)
    dt = np.diff(t)
    report = {
        "file": os.path.basename(path),
        "n": len(t),
        "duration_s": float(t[-1] - t[0]) if len(t) > 1 else 0.0,
        "dt_median_s": float(np.median(dt)) if len(dt) else float("nan"),
        "rate_hz": float(1 / np.median(dt)) if len(dt) and np.median(dt) > 0 else float("nan"),
        "dt_jitter": float(np.std(dt) / np.median(dt)) if len(dt) and np.median(dt) > 0 else float("nan"),
        "n_nan": int(np.sum(~np.isfinite(v))),
        "constant": bool(np.nanstd(v) == 0),
        "warnings": [],
    }

    if len(t) < 50:
        report["warnings"].append(f"only {len(t)} samples; most analyses need more")
    if np.any(dt <= 0):
        report["warnings"].append("time is not strictly increasing — rows out of order, or a wrap")
    if len(dt) and report["dt_jitter"] > 0.5:
        report["warnings"].append(
            f"sampling is uneven (jitter {report['dt_jitter']:.2f}); analyses assume a regular grid")
    gaps = np.where(dt > 5 * np.median(dt))[0] if len(dt) else []
    if len(gaps):
        report["warnings"].append(
            f"{len(gaps)} gap(s) longer than 5x the sampling interval, "
            f"largest {dt[gaps].max():.2f}s at t={t[gaps[np.argmax(dt[gaps])]]:.1f}s")
    if report["constant"]:
        report["warnings"].append("the signal never changes — tracking probably failed")
    if report["n_nan"]:
        report["warnings"].append(f"{report['n_nan']} non-finite value(s)")

    # A slow drift is not an error, but it dominates a wavelet spectrum, and the
    # analyses detrend for exactly this reason.
    if len(t) > 10:
        slope = np.polyfit(t - t[0], v, 1)[0]
        span = abs(slope) * (t[-1] - t[0])
        if np.nanstd(v) > 0 and span > 2 * np.nanstd(v):
            report["warnings"].append(
                f"strong linear drift ({span:.2g} over the recording, "
                f"{span / np.nanstd(v):.1f}x the standard deviation)")

    if video_duration:
        report["video_duration_s"] = float(video_duration)
        covered = report["duration_s"] / video_duration
        if covered < 0.8:
            report["warnings"].append(
                f"covers only {covered:.0%} of the video — the dashboard will look "
                f"empty for the rest")
        elif covered > 1.2:
            report["warnings"].append(
                f"runs {covered:.0%} of the video length — wrong units, or the wrong file?")

    return report


def study_report(project_dir="."):
    """Run signal_report over every time series a study has."""
    out = []
    for path in sorted(glob.glob(os.path.join(project_dir, "assets/timeseries/*.csv"))):
        try:
            out.append(signal_report(path))
        except Exception as exc:  # noqa: BLE001 - one bad file must not stop the sweep
            out.append({"file": os.path.basename(path), "error": str(exc), "warnings": [str(exc)]})
    return out
