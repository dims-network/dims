#!/usr/bin/env python3
"""
step_cRQA.py - Generate Cross-Recurrence Quantification Analysis data for the DIMS Dashboard.

Cross-RQA quantifies recurrence between TWO different time series (e.g. a teacher
and a student signal), as opposed to step_RQA.py which analyses a single series
against itself.

This step produces, per data-type pair:
  1. The FULL cross-recurrence plot (RP) - every recurrent point, downsampled to
     <=500x500 for the browser (same scheme as step_RQA.py). This is what the
     dashboard renders.
  2. Windowed RQA metrics (RR / DET / LAM / L_MAX) computed on the FULL-resolution
     matrix by sliding a square window along the line of synchronization (the main
     diagonal), so coupling strength can be tracked over time.

Reads 'videoIDs' and 'include_cRQA' from config.json. 'include_cRQA' is a list of
pairs, each a 2-element list of data-types to compare, e.g.
    "include_cRQA": [["bodysync", "neuralsync"]]
Loads assets/timeseries/{videoID}_{dataType}.csv and writes
    assets/crqa/{videoID}_crqa_data.json

Usage:
    python step_cRQA.py --config config.json --output-dir assets/crqa
"""

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
import json
import os

# Absolute, not relative: the tests load these steps by file path, where a
# relative import has no parent package to resolve against.
from dims_analysis.common import assets as _assets
from dims_analysis.common import config as _config
from dims_analysis.common import npz as _npz
from dims_analysis.common import series as _series
from dims_analysis.common import recurrence as _rec
from dims_analysis.common import reduce as _reduce
from dims_analysis.common import results as _results
import argparse

# Where the time series are read from. A private study keeps its data outside
# the repository, at the path data.local.json names, so main() rewrites this
# through the resolver. It was previously a default argument and only the OUTPUT
# directory was resolved -- so on a private study this step read from a
# directory that does not exist while reporting success.
INPUT_DIR = 'assets/timeseries'

# Browser payloads are rounded to significant figures; see the module docstring
# for why decimal places would be wrong here. The full-resolution analysis is
# the .npz written beside the JSON and is not affected.
try:
    from dims_analysis.common.payload import round_payload, precision_note
except ImportError:  # standalone script inside a case repo, without the package
    import math as _math

    PAYLOAD_SIGNIFICANT_FIGURES = 6

    def round_payload(o, figures=PAYLOAD_SIGNIFICANT_FIGURES):
        if isinstance(o, dict):
            return {k: round_payload(v, figures) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [round_payload(v, figures) for v in o]
        # Integers pass through: a sparse recurrence matrix is tens of
        # thousands of [row, col] index pairs, and "7.0" is both wrong and
        # larger than "7".
        if o is None or isinstance(o, bool) or isinstance(o, int):
            return o
        if not isinstance(o, float):
            return o
        if not _math.isfinite(o):
            return None
        if o == 0:
            return o
        return float(f"%.{figures}g" % o)

    def precision_note(figures=PAYLOAD_SIGNIFICANT_FIGURES):
        return {"significant_figures": figures,
                "note": ("This file is the browser payload and is rounded. The "
                         "full-resolution analysis is the .npz beside it.")}



MAX_POINTS = 500  # visualization cap, matching step_RQA.py


# ============================================================================
# ALGORITHMS
# ============================================================================

def calculate_cross_recurrence_matrix(emb1, emb2, threshold=None, target_recurrence=0.07):
    """Cross-recurrence matrix between two (embedded) series.

    emb1/emb2 are (N, d) arrays. Returns (matrix, threshold, actual_recurrence).
    Threshold is auto-picked as the target_recurrence percentile of all distances.
    """
    distance_matrix = cdist(emb1, emb2, metric='euclidean')

    # One rule, one implementation: see common/recurrence.py. Nothing is
    # excluded here -- the two series are different, so no cell recurs by
    # construction and there is no line of identity to ignore.
    if threshold is None:
        threshold = _rec.threshold_for_target(distance_matrix, target_recurrence,
                                              self_paired=False)
        print(f"    > Calculated threshold: {threshold:.4f} (Target RR: {target_recurrence*100}%)")

    recurrence_matrix = (distance_matrix <= threshold).astype(np.uint8)
    actual_recurrence = _rec.recurrence_rate(recurrence_matrix, self_paired=False)
    return recurrence_matrix, threshold, actual_recurrence


def matrix_to_sparse_format(matrix):
    """Convert a recurrence matrix to a sparse list of [row, col] pairs (all R==1).

    Unlike a banded variant, this keeps the COMPLETE recurrence plot so the full
    structure is visible in the dashboard.
    """
    rows, cols = np.where(matrix == 1)
    return [[int(r), int(c)] for r, c in zip(rows, cols)]


def downsample_for_visualization(ts1, ts2, time_values, recurrence_matrix, max_points=MAX_POINTS):
    """Reduce for the browser. Returns (ts1, ts2, time, matrix, factor).

    Series are block-averaged; the matrix keeps both its structure and its
    recurrence rate. See common/reduce.py. This matters here more than anywhere:
    cross-recurrence is about structure OFF the main diagonal -- that is what a
    lagged coupling looks like -- and a line one cell off the diagonal
    disappears entirely when you take every nth row and every nth column.
    """
    n_points = len(time_values)
    factor = _reduce.factor_for(n_points, max_points)
    if factor <= 1:
        return ts1, ts2, time_values, recurrence_matrix, 1
    return (
        _reduce.block_mean(ts1, factor),
        _reduce.block_mean(ts2, factor),
        _reduce.block_mean(time_values, factor),
        _reduce.block_binary(recurrence_matrix, factor),
        factor,
    )


def get_line_lengths(matrix, direction='diagonal', min_len=2):
    """Delegates to the shared implementation; see common/recurrence.py."""
    return _rec.line_lengths(matrix, direction, min_len, self_paired=False)

def calculate_window_metrics(matrix, dt, min_line=2):
    """Delegates to the shared implementation; see common/recurrence.py."""
    return _rec.window_metrics(matrix, dt, min_line, self_paired=False)

def _load_series(path):
    """Delegates to the shared reader; see common/series.py."""
    return _series.load(path)


def load_and_align_data(video_id, type1, type2, input_dir=None):
    """Load two CSVs and align them onto a common uniform time grid via linear
    interpolation (the two series rarely share identical timestamps), then
    z-normalize. Returns (s1_norm, s2_norm, common_time).

    input_dir defaults to the module-level INPUT_DIR, which main() has already
    resolved through data.local.json — a default argument would capture the
    unresolved value at import time.
    """
    input_dir = input_dir or INPUT_DIR
    path1 = os.path.join(input_dir, f"{video_id}_{type1}.csv")
    path2 = os.path.join(input_dir, f"{video_id}_{type2}.csv")

    if not os.path.exists(path1) or not os.path.exists(path2):
        print(f"  [Warning] Missing file(s) for pair {type1} <-> {type2}:")
        if not os.path.exists(path1):
            print(f"    Missing: {path1}")
        if not os.path.exists(path2):
            print(f"    Missing: {path2}")
        return None, None, None

    try:
        t1, v1 = _load_series(path1)
        t2, v2 = _load_series(path2)
    except Exception as e:
        print(f"  [Error] Failed to read CSVs: {e}")
        return None, None, None
    if t1 is None or t2 is None or len(t1) < 10 or len(t2) < 10:
        print("  [Error] Insufficient or malformed data in one of the series.")
        return None, None, None

    # Common overlapping time range, sampled on a uniform grid at the finer of the
    # two median sampling intervals.
    t_start = max(t1[0], t2[0])
    t_end = min(t1[-1], t2[-1])
    if t_end <= t_start:
        print(f"  [Error] Series time ranges do not overlap "
              f"([{t1[0]:.2f},{t1[-1]:.2f}] vs [{t2[0]:.2f},{t2[-1]:.2f}]).")
        return None, None, None

    dt = min(float(np.median(np.diff(t1))), float(np.median(np.diff(t2))))
    if dt <= 0:
        dt = (t_end - t_start) / 1000.0
    n = int(np.floor((t_end - t_start) / dt)) + 1
    if n < 10:
        print(f"  [Error] Insufficient overlapping samples ({n}).")
        return None, None, None
    common_time = t_start + np.arange(n) * dt

    raw_s1 = np.interp(common_time, t1, v1)
    raw_s2 = np.interp(common_time, t2, v2)

    s1_norm = (raw_s1 - np.mean(raw_s1)) / (np.std(raw_s1) + 1e-6)
    s2_norm = (raw_s2 - np.mean(raw_s2)) / (np.std(raw_s2) + 1e-6)
    return s1_norm, s2_norm, common_time


# ============================================================================
# MAIN
# ============================================================================

def save_full_resolution(out_dir, video_id, pair_key, entry, time_vals, ts1, ts2):
    """The analysis, beside the browser payload. See common/npz.py.

    Not the cross-recurrence matrix: it is quadratic in the recording. What is
    stored is the windowed metrics at full resolution, both prepared signals and
    the threshold -- enough to rebuild the matrix with one cdist at whatever
    resolution the reader can afford.
    """
    wm = entry.get('windowed_metrics') or {}
    arrays = {
        'time': np.asarray(time_vals, dtype=np.float64),
        'signal_x': np.asarray(ts1, dtype=np.float64),
        'signal_y': np.asarray(ts2, dtype=np.float64),
        'threshold': np.asarray([entry.get('threshold', np.nan)], dtype=np.float64),
        'global_recurrence_rate': np.asarray(
            [entry.get('global_recurrence_rate', np.nan)], dtype=np.float64),
    }
    for key in ('time', 'RR', 'DET', 'LAM', 'L_MAX'):
        if key in wm:
            arrays[f'windowed_{key}'] = np.asarray(wm[key], dtype=np.float64)
    return _npz.add_group(os.path.join(out_dir, f"{video_id}_crqa.npz"),
                          pair_key, arrays)


def main():
    global INPUT_DIR
    parser = argparse.ArgumentParser(description='Generate cross-RQA data for the DIMS Dashboard')
    parser.add_argument('--config', default='config.json', help='Path to config.json')
    parser.add_argument('--output-dir', default='assets/crqa', help='Output directory')
    parser.add_argument('--window', type=float, default=20.0, help='Sliding window size in seconds')
    parser.add_argument('--step', type=float, default=1.0, help='Window step in seconds')
    args = parser.parse_args()

    try:
        with open(args.config, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Error: Config file '{args.config}' not found.")
        return

    if not _config.enabled(config, 'include_cRQA'):
        print("No cRQA requested in config (include_cRQA not found or empty)")
        return

    raw_pairs = _config.as_list(config, 'include_cRQA', 'pairs of data types')
    valid_pairs = []
    for item in raw_pairs:
        if isinstance(item, list) and len(item) == 2:
            valid_pairs.append(item)
        else:
            print(f"Warning: Skipping invalid include_cRQA entry: {item}. Expected [type1, type2].")
    if not valid_pairs:
        print("Error: No valid pairs found in include_cRQA.")
        return

    video_ids = config.get('videoIDs', [])
    if not video_ids:
        print("Error: 'videoIDs' list is empty in config.")
        return

    _note = _assets.describe()
    if _note:
        print(_note)
    INPUT_DIR = _assets.resolve(INPUT_DIR)
    args.output_dir = _assets.resolve(args.output_dir)
    os.makedirs(args.output_dir, exist_ok=True)

    for vid in video_ids:
        print(f"\n{'='*60}")
        print(f"Processing video: {vid}")
        print(f"{'='*60}")

        video_results = {}
        for type1, type2 in valid_pairs:
            print(f"\nComparing: {type1} <-> {type2}")

            ts1, ts2, time_vals = load_and_align_data(vid, type1, type2)
            if ts1 is None:
                continue

            # Analyse the raw 1-D signals (column vectors for cdist).
            emb1, emb2 = ts1.reshape(-1, 1), ts2.reshape(-1, 1)
            ts1_1d, ts2_1d = ts1, ts2

            # Full-resolution cross-recurrence matrix (used for metrics).
            rec_matrix, threshold, global_rr = calculate_cross_recurrence_matrix(emb1, emb2)
            print(f"  > Global cross-recurrence rate: {global_rr*100:.2f}%")

            # Windowed metrics along the line of synchronization (main diagonal).
            dt = float(np.mean(np.diff(time_vals)))
            if dt <= 0:
                dt = 0.033
            n = len(emb1)
            win_points = max(2, int(args.window / dt))
            step_points = max(1, int(args.step / dt))
            # Short-series adaptation: cap the window to half the series and refine
            # the step so we always get several windows (otherwise a single trivial
            # window renders as a blank metric chart). Long series are unaffected.
            win_points = min(win_points, max(2, n // 2))
            n_eff = max(1, n - win_points)
            step_points = max(1, min(step_points, n_eff // 20))

            windowed_metrics = {'time': [], 'RR': [], 'DET': [], 'LAM': [], 'L_MAX': []}
            print(f"  > Windowed metrics (window={args.window}s, step={args.step}s)...")
            for start_idx in range(0, max(1, n - win_points), step_points):
                end_idx = start_idx + win_points
                w_matrix = rec_matrix[start_idx:end_idx, start_idx:end_idx]
                rr, det, lam, l_max = calculate_window_metrics(w_matrix, dt)
                center_time = time_vals[min(start_idx + win_points // 2, n - 1)]
                windowed_metrics['time'].append(float(center_time))
                windowed_metrics['RR'].append(rr)
                windowed_metrics['DET'].append(det)
                windowed_metrics['LAM'].append(lam)
                windowed_metrics['L_MAX'].append(l_max)

            # Full recurrence plot for visualization, downsampled to <=500x500.
            ts1_vis, ts2_vis, time_vis, matrix_vis, reduction_factor = downsample_for_visualization(
                ts1_1d, ts2_1d, time_vals, rec_matrix
            )
            sparse_matrix = matrix_to_sparse_format(matrix_vis)

            pair_key = f"{type1}_vs_{type2}"
            video_results[pair_key] = {
                'pair_name': pair_key,
                'series_names': [type1, type2],
                'threshold': float(threshold),
                'global_recurrence_rate': float(global_rr),
                'time_range': [float(time_vals[0]), float(time_vals[-1])],
                'windowed_metrics': windowed_metrics,
                'visualization': {
                    'time': time_vis.tolist(),
                    'data_x': ts1_vis.tolist(),
                    'data_y': ts2_vis.tolist(),
                    'matrix_size': len(time_vis),
                    'sparse_matrix': sparse_matrix,  # full RP, reduced
                    # What this plot is a reduction OF.
                    'reduction': {
                        'factor': int(reduction_factor),
                        'series': 'block-mean',
                        'matrix': 'density-preserving',
                        'n_points_full': int(n),
                        # What was actually drawn; see the note in rqa.py.
                        'rate_full': _reduce.rate_of(rec_matrix),
                        'rate_drawn': _reduce.rate_of(matrix_vis),
                    },
                },
                'full_stats': {
                    'n_points': int(n),
                    'window_size_sec': args.window,
                    'step_size_sec': args.step,
                },
            }
            try:
                save_full_resolution(args.output_dir, vid, pair_key,
                                     video_results[pair_key], time_vals, ts1_1d, ts2_1d)
            except Exception as exc:  # noqa: BLE001 - never lose a run over this
                print(f"  WARNING: could not write full-resolution output ({exc})")
            print(f"  > {pair_key}: matrix {len(time_vis)}x{len(time_vis)}, "
                  f"{len(sparse_matrix)} recurrent points, {len(windowed_metrics['time'])} windows")

        if video_results:
            output_path = os.path.join(args.output_dir, f"{vid}_crqa_data.json")
            kept = _results.write_payload(output_path, round_payload(
                {'video_id': vid, 'crqa_data': video_results,
                 'precision': precision_note()}))
            print(f"\nSaved cRQA data to {output_path}")
            for key, names in kept.get('kept', {}).items():
                print(f"  kept {len(names)} existing {key} entr"
                      f"{'y' if len(names) == 1 else 'ies'} from another "
                      f"analysis: {', '.join(names)}")
            for key, names in kept.get('replaced', {}).items():
                print(f"  replaced {len(names)} existing {key} entr"
                      f"{'y' if len(names) == 1 else 'ies'}: {', '.join(names)}")
        else:
            print(f"\n[INFO] No cRQA results generated for video {vid}")

    print("\ncRQA processing complete!")


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# Step contract adapter
#
# INTERIM. This wraps the script's existing main() by setting sys.argv, so the
# step is discoverable and runnable through `dims-analysis` today without
# rewriting the analysis itself. Replacing it means giving run() the real
# parameters and dropping main() -- tracked as a follow-up issue.
# ---------------------------------------------------------------------------
from dims_analysis.base import Step as _Step


class Step(_Step):
    id = "crqa"
    config_key = "include_cRQA"
    output_dir = "assets/crqa"
    output_name = "{video_id}_crqa_data.json"
    description = "Cross-recurrence quantification between pairs of series"

    def run(self, config, ctx):
        import os as _os
        import sys as _sys
        cwd = _os.getcwd()
        argv = _sys.argv[:]
        try:
            _os.chdir(ctx.project_dir)
            _sys.argv = ["crqa", "--config", "config.json",
                         "--output-dir", ctx.output_path(self, "_").rsplit(_os.sep, 1)[0]]
            main()
        finally:
            _sys.argv = argv
            _os.chdir(cwd)
