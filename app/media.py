"""Media alignment helpers: read durations, trim video, zero-pad time-series.

The builder maps a time-series `Time` column (seconds) directly onto the video
clock, so a session whose video and data have different lengths shows dead space
in the dashboard. These helpers let the wizard align the two, by either trimming
the video to a chosen window or padding the CSVs with zeros.

ffmpeg ships via the `imageio-ffmpeg` pip package (no system install needed). It
provides `ffmpeg` but not `ffprobe`, so we read durations by parsing `ffmpeg -i`.
"""
import csv
import os
import re
import subprocess
import tempfile

# Parses the "  Duration: 00:00:10.00, start: ..." line ffmpeg prints to stderr.
_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")

_ffmpeg_exe_cache = []  # [path] or [None]; one-element memo


def ffmpeg_exe():
    """Path to a usable ffmpeg binary, or None if unavailable.

    Prefers the binary bundled by imageio-ffmpeg (the builder's declared way to
    get ffmpeg without a system install); cached after the first lookup.
    """
    if _ffmpeg_exe_cache:
        return _ffmpeg_exe_cache[0]
    exe = None
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001 — missing package, download failure, etc.
        exe = None
    _ffmpeg_exe_cache.append(exe)
    return exe


def video_duration(path):
    """Return the video's duration in seconds, or None if it can't be read."""
    exe = ffmpeg_exe()
    if not exe or not os.path.exists(path):
        return None
    try:
        proc = subprocess.run(
            [exe, "-i", path], capture_output=True, text=True,
        )
    except Exception:  # noqa: BLE001
        return None
    # ffmpeg with no output target exits non-zero but still prints the metadata.
    m = _DURATION_RE.search(proc.stderr or "")
    if not m:
        return None
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)


def _read_times(csv_path):
    """Yield the float values of the `Time` column, skipping unparseable rows."""
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "Time" not in reader.fieldnames:
            return
        for row in reader:
            try:
                yield float(row["Time"])
            except (TypeError, ValueError):
                continue


def series_bounds(csv_path):
    """Return {min, max, step, rows} for a time-series CSV, or None if no data.

    `step` is the median gap between consecutive Time values (the sample
    interval), used to space out padding rows.
    """
    times = list(_read_times(csv_path))
    if not times:
        return None
    times_sorted = sorted(times)
    diffs = [b - a for a, b in zip(times_sorted, times_sorted[1:]) if b > a]
    if diffs:
        diffs.sort()
        step = diffs[len(diffs) // 2]
    else:
        step = 0.0
    return {
        "min": times_sorted[0],
        "max": times_sorted[-1],
        "step": step,
        "rows": len(times),
    }


def trim_video(src, start, end):
    """Keep only the window [start, end] (seconds) of `src`, in place.

    Re-encodes so the cut is frame-accurate at both ends. Raises RuntimeError if
    ffmpeg is unavailable or the cut fails.
    """
    exe = ffmpeg_exe()
    if not exe:
        raise RuntimeError(
            "ffmpeg is not available. Install it with: pip install imageio-ffmpeg"
        )
    if end <= start:
        raise ValueError("Trim window end must be greater than start.")
    fd, tmp = tempfile.mkstemp(suffix=".mp4", dir=os.path.dirname(src))
    os.close(fd)
    try:
        proc = subprocess.run(
            [exe, "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", src,
             "-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart", tmp],
            capture_output=True, text=True,
        )
        if proc.returncode != 0 or not os.path.getsize(tmp):
            raise RuntimeError(
                "ffmpeg failed to trim the video: "
                + (proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "unknown error")
            )
        os.replace(tmp, src)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def pad_timeseries(csv_path, pad_start, pad_end):
    """Zero-pad a time-series CSV in place by pad_start/pad_end seconds.

    Prepends `round(pad_start/step)` zero rows at times 0, step, 2*step…, shifts
    every existing Time by pad_start, then appends zero rows up to +pad_end. All
    measurement columns are filled with 0. No-ops when both pads are ~0.

    Returns the new max Time (the series' new duration).
    """
    pad_start = max(0.0, float(pad_start))
    pad_end = max(0.0, float(pad_end))

    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        rows = [r for r in reader if r]
    if not header or "Time" not in header:
        raise ValueError("CSV has no 'Time' column to pad against.")

    bounds = series_bounds(csv_path)
    if not bounds:
        raise ValueError("CSV has no numeric Time data to pad.")
    step = bounds["step"]
    if step <= 0:
        raise ValueError("Could not infer a sample interval from the Time column.")

    t_idx = header.index("Time")
    n_cols = len(header)

    def zero_row(t):
        r = ["0"] * n_cols
        r[t_idx] = f"{t:.6g}"
        return r

    # Lead-in zeros: 0, step, 2*step … strictly below pad_start.
    n_start = int(round(pad_start / step)) if pad_start > 0 else 0
    lead = [zero_row(i * step) for i in range(n_start)]

    # Shift existing rows so the original signal starts at pad_start.
    shifted = []
    last_time = 0.0
    for r in rows:
        if len(r) < n_cols:
            r = r + ["0"] * (n_cols - len(r))
        try:
            t = float(r[t_idx]) + pad_start
        except ValueError:
            continue
        r = list(r)
        r[t_idx] = f"{t:.6g}"
        shifted.append(r)
        last_time = t

    # Trailing zeros up to last_time + pad_end.
    tail = []
    if pad_end > 0:
        n_end = int(round(pad_end / step))
        tail = [zero_row(last_time + i * step) for i in range(1, n_end + 1)]

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(lead)
        writer.writerows(shifted)
        writer.writerows(tail)

    return (tail[-1][t_idx] if tail else (shifted[-1][t_idx] if shifted else "0"))
