#!/usr/bin/env python3
"""Recurrence quantification analysis of one time series against itself.

Where a signal repeats its own earlier states: a recurrence plot per measure,
plus DET, LAM, RR and L_MAX over a sliding window. Runs for every data type
named in `include_RQA`, and writes `assets/rqa/{video}_rqa_data.json`.

Run it through the pipeline, which is how a study runs it:

    dims-analysis run --config config.json            # every enabled analysis
    dims-analysis run --config config.json --steps rqa

Tuning is `analysis.rqa` in the study's config -- window, step and
targetRecurrence, all in seconds except the last, which is a fraction. See
docs/contracts/analysis-output.md.
"""

import numpy as np
from scipy.spatial.distance import cdist
import json
import os

# Absolute, not relative: the tests load these steps by file path, where a
# relative import has no parent package to resolve against.
from dims_analysis.common import assets as _assets
from dims_analysis.common import config as _config
from dims_analysis.common import limits as _limits
from dims_analysis.common import payload as _payload
from dims_analysis.common import arrays as _arrays
from dims_analysis.common import series as _series
from dims_analysis.common import window as _window
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

#: The recurrence rate the threshold search aims for.
TARGET_RECURRENCE = 0.07

#: The largest recurrence plot written into a browser payload, per side.
MAX_POINTS_DRAWN = 500

# Browser payloads are rounded to significant figures; see the module docstring
# for why decimal places would be wrong here. The large arrays travel as base64
# float32 and bitmaps and are not rounded at all.
#
# This used to be a try/except ImportError with a second copy of round_payload
# in the fallback, "for a standalone script inside a case repo, without the
# package". The package is imported unconditionally thirty lines above, so the
# fallback could never run -- and its precision_note carried a different note
# string, so if it ever had, it would have written a different payload.
from dims_analysis.common.payload import round_payload, precision_note



#: The step id this analysis is tuned under in `config.json`:
#: `analysis.rqa.{window, step, targetRecurrence}`. See common/config.tuning.
TUNING_KEY = "rqa"


def _provenance(target_recurrence=TARGET_RECURRENCE):
    """What produced this file, including the rate this run actually aimed at.

    The module default used to be recorded here whatever the run asked for,
    which is the A6 defect in miniature: an output that does not say what it was
    asked for cannot be compared with another.
    """
    return _payload.provenance(target_recurrence=target_recurrence,
                               max_points_drawn=MAX_POINTS_DRAWN)


def calculate_recurrence_matrix(time_series, threshold=None,
                                target_recurrence=TARGET_RECURRENCE):
    """
    Calculate recurrence matrix for a time series.
    
    Parameters:
    - time_series: 1D array of time series data
    - threshold: fixed threshold (if None, will be calculated for target_recurrence)
    - target_recurrence: target recurrence rate (default 5%)
    """
    # One normalisation, shared with cRQA; see common/series.py.
    ts_normalized = _series.normalise(time_series)
    
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

def compute_windowed_metrics(matrix, time_values, window_sec=20.0, step_sec=1.0):
    """Slide a square window along the main diagonal of `matrix`.

    Returns `(metrics, plan)`: `{time, RR, DET, LAM, L_MAX}` and the
    `WindowPlan` that says where those windows were and how they differ from
    the ones asked for. See common/window.py -- the placement used to be
    computed here and again in `crqa.py`, in samples, so it moved with the
    sampling rate and nothing recorded it.
    """
    n = matrix.shape[0]
    dt = float(np.mean(np.diff(time_values))) if len(time_values) > 1 else 0.0
    if dt <= 0:
        raise ValueError(
            "the time column does not advance, so no window length in seconds "
            "means anything; a recurrence analysis needs a real time axis.")

    plan = _window.plan(n, dt, window_sec, step_sec)
    out = {'time': plan.centres(time_values),
           'RR': [], 'DET': [], 'LAM': [], 'L_MAX': []}
    for start in plan.starts:
        w = matrix[start:start + plan.length, start:start + plan.length]
        # Exclude the line of identity (k=0) -- in single-series RQA it is
        # trivially recurrent and would otherwise dominate DET / L_MAX.
        rr, det, lam, l_max = _rec.window_metrics(w, dt, self_paired=True)
        out['RR'].append(rr)
        out['DET'].append(det)
        out['LAM'].append(lam)
        out['L_MAX'].append(l_max)
    return out, plan


def matrix_to_bitmap(matrix):
    """One bit per cell, base64. See common/arrays.py.

    This used to be a list of `[row, col]` pairs, which costs about ten bytes
    per recurrent cell against a bitmap's one bit per cell whatever the
    density. Measured on one ORTHO gaze matrix: 7,300,452 bytes as pairs
    against 133,803 as a bitmap. Sparse only wins below about 1.2 % density,
    and RQA targets 7 %.
    """
    return _arrays.pack_bitmap(matrix)

def downsample_for_visualization(time_series, time_values, recurrence_matrix,
                                 max_points=MAX_POINTS_DRAWN):
    """Reduce for the browser. Returns (data, time, matrix, factor).

    The series is block-averaged; the matrix keeps both its structure and its
    recurrence rate -- see common/reduce.py, which explains why striding and
    block-OR each destroy one of the two. It matters most for the matrix: under
    striding a recurrent line one cell off the main diagonal disappears
    completely, and that is exactly where a lagged coupling lives; under block-OR
    the plot fills in until its density no longer matches the rate printed
    beside it.
    """
    n_points = len(time_series)
    factor = _reduce.factor_for(n_points, max_points)
    if factor <= 1:
        return time_series, time_values, recurrence_matrix, 1

    data_ds = _reduce.block_mean(time_series, factor)
    time_ds = _reduce.block_mean(time_values, factor)
    matrix_ds = _reduce.block_binary(recurrence_matrix, factor)

    print(f"  Reduced {n_points} -> {len(time_ds)} points for the browser "
          f"(block average / density-preserving, factor {factor})")

    return data_ds, time_ds, matrix_ds, factor

def process_rqa_for_datatype(video_id, data_type, window_sec=20.0, step_sec=1.0,
                             target_recurrence=TARGET_RECURRENCE):
    """
    Process RQA for a specific data type.
    """
    csv_path = os.path.join(INPUT_DIR, f"{video_id}_{data_type}.csv")

    print(f"\nProcessing {video_id} - {data_type}")

    # One reader, shared with cRQA and the notebooks: canonical Time column,
    # NaNs dropped, sorted by time. This step did not sort, so on an
    # out-of-order CSV it and cRQA disagreed about what the data was.
    # A constant series is refused here rather than producing a confident
    # nothing: it used to normalise to NaN, fail every threshold comparison,
    # and report recurrence_rate = -0.000977517.
    loaded = _series.load_or_none(csv_path, min_points=_limits.MIN_POINTS,
                                  min_variance=_limits.MIN_VARIANCE)
    time_clean, data_clean = loaded if loaded else (None, None)
    if data_clean is None:
        return None

    # Quadratic in the length of the recording, so the refusal comes before the
    # allocation and names the limit. See common/limits.py.
    try:
        _limits.check_length(len(data_clean), f"{video_id} {data_type}")
    except _limits.InputTooLarge as exc:
        print(f"  [skip] {exc}")
        return None

    print(f"  Processing {len(data_clean)} data points")
    
    # Calculate full recurrence matrix
    rec_matrix_full, threshold, rec_rate = calculate_recurrence_matrix(
        data_clean, target_recurrence=target_recurrence)
    
    # Downsample for visualization
    data_vis, time_vis, rec_matrix_vis, reduction_factor = downsample_for_visualization(
        data_clean, time_clean, rec_matrix_full
    )
    
    # Pack the drawn matrix, one bit per cell.
    bitmap = matrix_to_bitmap(rec_matrix_vis)

    # Windowed metrics on the full-resolution matrix (sliding window along the diagonal)
    windowed_metrics, window_plan = compute_windowed_metrics(
        rec_matrix_full, time_clean, window_sec=window_sec, step_sec=step_sec
    )
    if window_plan.warning:
        print(f"  WARNING: {window_plan.warning}")

    # Prepare output data
    target, achieved, rate_warning = _rec.rate_report(target_recurrence, rec_rate)
    if rate_warning:
        print(f"  WARNING: {rate_warning}")

    result = {
        'data_type': data_type,
        'threshold': float(threshold),
        'recurrence_rate': float(rec_rate),
        # What was asked for, beside what was achieved. Without the first, a
        # reader cannot tell a 33% rate from a deliberate choice.
        'target_recurrence': target,
        'achieved_recurrence': achieved,
        'recurrence_rate_warning': rate_warning,
        'time_range': [float(time_clean[0]), float(time_clean[-1])],
        'windowed_metrics': windowed_metrics,
        # DET and LAM are shares of the structure inside one window, so the
        # window is a parameter of the result exactly as the recurrence rate
        # is -- and it is recorded the same way, asked-for beside used.
        'window': window_plan.report(),
        'visualization': {
            'time': time_vis.tolist(),
            'data': data_vis.tolist(),
            'matrix_size': len(time_vis),
            'matrix': bitmap,          # bitmap-b64; common/arrays.py
            # What this plot is a reduction OF. Without it a reader cannot tell
            # a 500-point picture from the 6000-point analysis behind it.
            'reduction': {
                'factor': int(reduction_factor),
                'series': 'block-mean',
                'matrix': 'density-preserving',
                'n_points_full': int(len(data_clean)),
                # What was actually drawn. These normally agree; they can differ
                # on a very sparse matrix, where keeping the rate would reduce a
                # line to a couple of dots. Recorded either way, so the picture
                # never silently contradicts the rate beside it.
                'rate_full': _reduce.rate_of(rec_matrix_full),
                'rate_drawn': _reduce.rate_of(rec_matrix_vis),
            },
        },
        # The analysis at full resolution, in the same file as the picture.
        # There is no second artifact any more: everything here except the
        # matrix is one-dimensional and small -- a 6000-point signal is 24 kB
        # as float32 -- and the matrix is one `cdist` from the signal and the
        # threshold, at whatever resolution the reader can afford. Storing it
        # is not an option at any resolution: it is quadratic, and one Karnatak
        # lesson would be 3.4 billion cells.
        'full_data': {
            'n_points': len(data_clean),
            'time_range': [float(time_clean[0]), float(time_clean[-1])],
            'time': _arrays.pack_f32(time_clean),
            'signal': _arrays.pack_f32(data_clean),
        },
    }

    return result


def main():
    global INPUT_DIR
    parser = argparse.ArgumentParser(description='Generate RQA data for DIMS Dashboard')
    parser.add_argument('--config', default='config.json', help='Path to config.json')
    parser.add_argument('--output-dir', default='assets/rqa', help='Output directory for RQA data')
    parser.add_argument('--window', type=float, default=None,
                        help='Windowed-metric window size in seconds '
                             '(default: analysis.rqa.window, else 20)')
    parser.add_argument('--step', type=float, default=None,
                        help='Windowed-metric step in seconds '
                             '(default: analysis.rqa.step, else 1)')
    args = parser.parse_args()
    
    # Load config
    with open(args.config, 'r') as f:
        config = json.load(f)

    # Tuning belongs in the study's config, not in this file and not only on a
    # command line the step adapter never uses. A flag still wins where one is
    # given, so a one-off run can override without editing the study.
    window_sec = args.window if args.window is not None else \
        _config.tuned_number(config, TUNING_KEY, 'window', 20.0)
    step_sec = args.step if args.step is not None else \
        _config.tuned_number(config, TUNING_KEY, 'step', 1.0)
    target_recurrence = _config.tuned_number(
        config, TUNING_KEY, 'targetRecurrence', TARGET_RECURRENCE)
    
    # Check if RQA is requested
    if not _config.enabled(config, 'include_RQA'):
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
        rqa_data_types = list(dict.fromkeys(
            _config.as_list(config, 'include_RQA', 'data types')))
        
        # Process each data type
        rqa_results = {}
        for data_type in rqa_data_types:
            result = process_rqa_for_datatype(
                video_id, data_type, window_sec=window_sec, step_sec=step_sec,
                target_recurrence=target_recurrence)
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
                'payload_version': _arrays.PAYLOAD_VERSION,
                'rqa_data': rqa_results,
                'provenance': _provenance(target_recurrence),
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
                print(f"    - Bitmap: {result['visualization']['matrix']['rows']}"
                      f"x{result['visualization']['matrix']['cols']}")
    
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
