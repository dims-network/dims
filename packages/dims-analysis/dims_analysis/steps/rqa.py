#!/usr/bin/env python3
"""
generate_rqa.py - Generate Recurrence Quantification Analysis data for DIMS Dashboard

Usage:
    python generate_rqa.py --config config.json --output-dir assets/rqa
"""

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from scipy.sparse import csr_matrix
import json
import os

# Absolute, not relative: the tests load these steps by file path, where a
# relative import has no parent package to resolve against.
from dims_analysis.common import assets as _assets
from dims_analysis.common import series as _series
from dims_analysis.common import recurrence as _rec
from dims_analysis.common import reduce as _reduce
from dims_analysis.common import results as _results
import argparse

# Where the time series are read from. A private study keeps its data outside
# the repository, at the path data.local.json names, so main() rewrites this
# through the resolver. It was previously inlined at the one call site and only
# the OUTPUT directory was resolved -- so on a private study this step read from
# a directory that does not exist while printing "assets resolved" and reporting
# success.
INPUT_DIR = 'assets/timeseries'

# Fewer points than this cannot support a recurrence estimate worth drawing.
MIN_DATA_POINTS = 10

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



def calculate_recurrence_matrix(time_series, threshold=None, target_recurrence=0.07):
    """
    Calculate recurrence matrix for a time series.
    
    Parameters:
    - time_series: 1D array of time series data
    - threshold: fixed threshold (if None, will be calculated for target_recurrence)
    - target_recurrence: target recurrence rate (default 5%)
    """
    # Normalize the time series
    ts_normalized = (time_series - np.mean(time_series)) / np.std(time_series)
    
    # Reshape for distance calculation
    ts_reshaped = ts_normalized.reshape(-1, 1)
    
    # Calculate distance matrix
    distance_matrix = cdist(ts_reshaped, ts_reshaped, metric='euclidean')
    
    # One rule, one implementation: see common/recurrence.py. The threshold and
    # the recurrence rate both ignore the line of identity, because a point
    # recurring with itself is not a finding.
    if threshold is None:
        threshold = _rec.threshold_for_target(distance_matrix, target_recurrence,
                                              self_paired=True)
        print(f"  Calculated threshold: {threshold:.4f} for "
              f"{target_recurrence * 100}% recurrence")

    recurrence_matrix = (distance_matrix <= threshold).astype(np.uint8)
    actual_recurrence = _rec.recurrence_rate(recurrence_matrix, self_paired=True)
    print(f"  Actual recurrence rate: {actual_recurrence*100:.2f}%")

    return recurrence_matrix, threshold, actual_recurrence

def get_line_lengths(matrix, direction='diagonal', min_len=2, exclude_main_diagonal=False):
    """Delegates to the shared implementation; see common/recurrence.py."""
    return _rec.line_lengths(matrix, direction, min_len, self_paired=exclude_main_diagonal)

def calculate_window_metrics(matrix, dt, min_line=2, exclude_main_diagonal=False):
    """Delegates to the shared implementation; see common/recurrence.py."""
    return _rec.window_metrics(matrix, dt, min_line, self_paired=exclude_main_diagonal)

def compute_windowed_metrics(matrix, time_values, window_sec=20.0, step_sec=1.0):
    """Slide a square window along the main diagonal of `matrix`, returning
    {time, RR, DET, LAM, L_MAX} so coupling/structure can be tracked over time."""
    n = matrix.shape[0]
    dt = float(np.mean(np.diff(time_values))) if len(time_values) > 1 else 0.033
    if dt <= 0:
        dt = 0.033
    win_points = max(2, int(window_sec / dt))
    step_points = max(1, int(step_sec / dt))
    # Short-series adaptation: if the requested window doesn't fit, a single
    # trivial window is produced and the metric chart renders blank. Cap the
    # window to half the series and refine the step so we always get several
    # windows. Long series keep the requested window/step unchanged.
    win_points = min(win_points, max(2, n // 2))
    n_eff = max(1, n - win_points)
    step_points = max(1, min(step_points, n_eff // 20))
    out = {'time': [], 'RR': [], 'DET': [], 'LAM': [], 'L_MAX': []}
    for start_idx in range(0, max(1, n - win_points), step_points):
        end_idx = start_idx + win_points
        w = matrix[start_idx:end_idx, start_idx:end_idx]
        # Exclude the line of identity (k=0) — in single-series RQA it is
        # trivially recurrent and would otherwise dominate DET / L_MAX.
        rr, det, lam, l_max = calculate_window_metrics(w, dt, exclude_main_diagonal=True)
        center = time_values[min(start_idx + win_points // 2, n - 1)]
        out['time'].append(float(center))
        out['RR'].append(rr)
        out['DET'].append(det)
        out['LAM'].append(lam)
        out['L_MAX'].append(l_max)
    return out

def matrix_to_sparse_format(matrix):
    """
    Convert recurrence matrix to sparse format for efficient storage.
    Returns list of [row, col] pairs where recurrence is 1.
    """
    # Get indices where matrix is 1
    rows, cols = np.where(matrix == 1)
    
    # Combine into list of pairs
    sparse_data = [[int(r), int(c)] for r, c in zip(rows, cols)]
    
    return sparse_data

def downsample_for_visualization(time_series, time_values, recurrence_matrix, max_points=500):
    """Reduce for the browser. Returns (data, time, matrix, factor).

    The series is block-averaged and the matrix is block-OR'd -- see
    common/reduce.py for why each, and why striding was wrong for both. It
    matters most for the matrix: a recurrent line one cell off the main diagonal
    disappears completely under striding, and that is exactly where a lagged
    coupling lives.
    """
    n_points = len(time_series)
    factor = _reduce.factor_for(n_points, max_points)
    if factor <= 1:
        return time_series, time_values, recurrence_matrix, 1

    data_ds = _reduce.block_mean(time_series, factor)
    time_ds = _reduce.block_mean(time_values, factor)
    matrix_ds = _reduce.block_any(recurrence_matrix, factor)

    print(f"  Reduced {n_points} -> {len(time_ds)} points for the browser "
          f"(block average / block-OR, factor {factor})")

    return data_ds, time_ds, matrix_ds, factor

def process_rqa_for_datatype(video_id, data_type, window_sec=20.0, step_sec=1.0):
    """
    Process RQA for a specific data type.
    """
    csv_path = os.path.join(INPUT_DIR, f"{video_id}_{data_type}.csv")

    print(f"\nProcessing {video_id} - {data_type}")

    # One reader, shared with cRQA and the notebooks: canonical Time column,
    # NaNs dropped, sorted by time. This step did not sort, so on an
    # out-of-order CSV it and cRQA disagreed about what the data was.
    time_clean, data_clean = _series.load_or_none(csv_path, min_points=MIN_DATA_POINTS)
    if data_clean is None:
        return None

    print(f"  Processing {len(data_clean)} data points")
    
    # Calculate full recurrence matrix
    rec_matrix_full, threshold, rec_rate = calculate_recurrence_matrix(data_clean)
    
    # Downsample for visualization
    data_vis, time_vis, rec_matrix_vis, reduction_factor = downsample_for_visualization(
        data_clean, time_clean, rec_matrix_full
    )
    
    # Convert to sparse format
    sparse_matrix = matrix_to_sparse_format(rec_matrix_vis)

    # Windowed metrics on the full-resolution matrix (sliding window along the diagonal)
    windowed_metrics = compute_windowed_metrics(
        rec_matrix_full, time_clean, window_sec=window_sec, step_sec=step_sec
    )

    # Prepare output data
    result = {
        'data_type': data_type,
        'threshold': float(threshold),
        'recurrence_rate': float(rec_rate),
        'time_range': [float(time_clean[0]), float(time_clean[-1])],
        'windowed_metrics': windowed_metrics,
        'visualization': {
            'time': time_vis.tolist(),
            'data': data_vis.tolist(),
            'matrix_size': len(time_vis),
            'sparse_matrix': sparse_matrix,  # List of [row, col] pairs
            # What this plot is a reduction OF. Without it a reader cannot tell
            # a 500-point picture from the 6000-point analysis behind it.
            'reduction': {
                'factor': int(reduction_factor),
                'series': 'block-mean',
                'matrix': 'block-any',
                'n_points_full': int(len(data_clean)),
            },
        },
        'full_data': {
            'n_points': len(data_clean),
            'time_range': [float(time_clean[0]), float(time_clean[-1])]
        }
    }

    return result

def main():
    global INPUT_DIR
    parser = argparse.ArgumentParser(description='Generate RQA data for DIMS Dashboard')
    parser.add_argument('--config', default='config.json', help='Path to config.json')
    parser.add_argument('--output-dir', default='assets/rqa', help='Output directory for RQA data')
    parser.add_argument('--window', type=float, default=20.0, help='Windowed-metric window size in seconds')
    parser.add_argument('--step', type=float, default=1.0, help='Windowed-metric step in seconds')
    args = parser.parse_args()
    
    # Load config
    with open(args.config, 'r') as f:
        config = json.load(f)
    
    # Check if RQA is requested
    if 'include_RQA' not in config or not config['include_RQA']:
        print("No RQA requested in config (include_RQA not found or empty)")
        return
    
    # Create output directory
    _note = _assets.describe()
    if _note:
        print(_note)
    INPUT_DIR = _assets.resolve(INPUT_DIR)
    args.output_dir = _assets.resolve(args.output_dir)
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Process each video
    for video_id in config['videoIDs']:
        print(f"\n{'='*50}")
        print(f"Processing video: {video_id}")
        print(f"{'='*50}")
        
        # Get data types to process for RQA (remove duplicates)
        rqa_data_types = list(dict.fromkeys(config['include_RQA']))
        
        # Process each data type
        rqa_results = {}
        for data_type in rqa_data_types:
            result = process_rqa_for_datatype(video_id, data_type,
                                              window_sec=args.window, step_sec=args.step)
            if result:
                rqa_results[data_type] = result
        
        # Save combined data
        if rqa_results:
            output_path = os.path.join(args.output_dir, f"{video_id}_rqa_data.json")
            # Merge, do not clobber: this file is keyed by video, so a
            # study-owned analysis (ORTHO's categorical RQA over its gaze
            # channels) writes its results into the same rqa_data dict.
            kept = _results.write_payload(output_path, round_payload({
                'video_id': video_id,
                'rqa_data': rqa_results,
                'precision': precision_note(),
            }))
            print(f"\nSaved RQA data to {output_path}")
            for key, names in kept.get('kept', {}).items():
                print(f"  kept {len(names)} existing {key} entr"
                      f"{'y' if len(names) == 1 else 'ies'} from another "
                      f"analysis: {', '.join(names)}")
            for key, names in kept.get('replaced', {}).items():
                print(f"  replaced {len(names)} existing {key} entr"
                      f"{'y' if len(names) == 1 else 'ies'}: {', '.join(names)}")
            
            # Print summary
            print("\nSummary:")
            for data_type, result in rqa_results.items():
                print(f"  {data_type}:")
                print(f"    - Recurrence rate: {result['recurrence_rate']*100:.2f}%")
                print(f"    - Matrix size: {result['visualization']['matrix_size']}x{result['visualization']['matrix_size']}")
                print(f"    - Sparse points: {len(result['visualization']['sparse_matrix'])}")
    
    print("\nRQA processing complete!")

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
    id = "rqa"
    config_key = "include_RQA"
    output_dir = "assets/rqa"
    output_name = "{video_id}_rqa_data.json"
    description = "Recurrence quantification analysis of single time series"

    def run(self, config, ctx):
        import os as _os
        import sys as _sys
        cwd = _os.getcwd()
        argv = _sys.argv[:]
        try:
            _os.chdir(ctx.project_dir)
            _sys.argv = ["rqa", "--config", "config.json",
                         "--output-dir", ctx.output_path(self, "_").rsplit(_os.sep, 1)[0]]
            main()
        finally:
            _sys.argv = argv
            _os.chdir(cwd)
