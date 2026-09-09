#!/usr/bin/env python3
"""Cross-recurrence between two time series.

Where two signals repeat *each other*, and with what delay -- a teacher and a
student, say -- as opposed to `rqa.py`, which compares one series against
itself. Runs for every pair in `include_cRQA` and writes
`assets/crqa/{video}_crqa_data.json`.

Per pair:

  1. The full cross-recurrence plot, reduced to at most 500x500 for the browser
     by the density-preserving rule in common/reduce.py. Striding would delete
     the off-diagonal line a lagged coupling *is*.
  2. Windowed RR, DET, LAM and L_MAX along the line of synchronisation.
  3. Both prepared signals at full resolution, from which the matrix is one
     `cdist` away -- it is quadratic in the recording and is never stored.

Run it through the pipeline, which is how a study runs it:

    dims-analysis run --config config.json
    dims-analysis run --config config.json --steps crqa

Tuning is `analysis.crqa`: window, step and targetRecurrence. See
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
from dims_analysis.common import step_io as _step_io
from dims_analysis.common import window as _window
from dims_analysis.common import recurrence as _rec
from dims_analysis.common import reduce as _reduce
from dims_analysis.common import results as _results

# Where the time series are read from. A private study keeps its data outside
# the repository, at the path data.local.json names, so main() rewrites this
# through the resolver. It was previously a default argument and only the OUTPUT
# directory was resolved -- so on a private study this step read from a
# directory that does not exist while reporting success.
INPUT_DIR = 'assets/timeseries'

# Browser payloads are rounded to significant figures; see the module docstring
# for why decimal places would be wrong here. The full-resolution analysis is
# the base64 arrays, which are not rounded at all.
#
# This used to be a try/except ImportError with a second copy of round_payload
# in the fallback, "for a standalone script inside a case repo, without the
# package". The package is imported unconditionally thirty lines above, so the
# fallback could never run -- and its precision_note carried a different note
# string, so if it ever had, it would have written a different payload.
from dims_analysis.common.payload import round_payload, precision_note



MAX_POINTS = 500  # visualization cap, matching step_RQA.py

#: The recurrence rate the threshold search aims for, and the step id this
#: analysis is tuned under: `analysis.crqa.{window, step, targetRecurrence}`.
TARGET_RECURRENCE = 0.07
TUNING_KEY = "crqa"


# ============================================================================
# ALGORITHMS
# ============================================================================

def calculate_cross_recurrence_matrix(emb1, emb2, threshold=None,
                                      target_recurrence=TARGET_RECURRENCE):
    """Cross-recurrence matrix between two (embedded) series.

    emb1/emb2 are (N, d) arrays. Returns (matrix, threshold, actual_recurrence).
    Threshold is auto-picked as the target_recurrence percentile of all distances.
    """
    # cdist, not `np.abs(x[:, None] - x[None, :])`. The broadcast looks
    # like the simpler thing and is not: it allocates a temporary for the
    # subtraction and another for the absolute value, measuring 2.5x slower
    # and 2x the peak memory at n=8000. cdist writes one output buffer.
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


def matrix_to_bitmap(matrix):
    """One bit per cell, base64; the COMPLETE plot, not a band. See
    common/arrays.py for why this replaced a list of [row, col] pairs."""
    return _arrays.pack_bitmap(matrix)


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


def _load_series(path):
    """Delegates to the shared reader; see common/series.py."""
    return _series.load(path)


def load_and_align_data(video_id, type1, type2, input_dir=INPUT_DIR):
    """Load two CSVs and align them onto a common uniform time grid via linear
    interpolation (the two series rarely share identical timestamps), then
    z-normalize. Returns (s1_norm, s2_norm, common_time).

    `input_dir` is passed in. It used to default to None and fall back to the
    module global, with a docstring explaining that a default argument would
    capture the unresolved value at import time -- a correct diagnosis of the
    wrong problem. The global was the problem; the fallback was its second
    symptom, and both are gone.
    """
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
    if t1 is None or t2 is None or len(t1) < _limits.MIN_POINTS \
            or len(t2) < _limits.MIN_POINTS:
        print("  [Error] Insufficient or malformed data in one of the series.")
        return None, None, None
    for name, values in (("first", v1), ("second", v2)):
        if float(np.std(values)) <= _limits.MIN_VARIANCE:
            print(f"  [Error] The {name} series does not vary; there is nothing "
                  f"to measure against it.")
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
    # The grid takes the finer of the two sampling intervals, so a pair can be
    # far longer than either series -- and the matrix is quadratic in it.
    try:
        _limits.check_length(n, "this pair on its common grid")
    except _limits.InputTooLarge as exc:
        print(f"  [skip] {exc}")
        return None, None, None

    common_time = t_start + np.arange(n) * dt

    raw_s1 = np.interp(common_time, t1, v1)
    raw_s2 = np.interp(common_time, t2, v2)

    # One normalisation, shared with RQA; see common/series.py. This used to
    # add 1e-6 to the standard deviation where rqa.py did not, which made the
    # two steps' stored thresholds incomparable.
    s1_norm = _series.normalise(raw_s1)
    s2_norm = _series.normalise(raw_s2)
    return s1_norm, s2_norm, common_time


# ============================================================================
# MAIN
# ============================================================================

def process_crqa_for_pair(video_id, type1, type2, input_dir=INPUT_DIR,
                          window_sec=20.0, step_sec=1.0,
                          target_recurrence=TARGET_RECURRENCE):
    """One pair of one video, as `(pair_key, entry)`, or None if unusable.

    This was ninety lines inline inside a 172-line main(), where rqa.py had long
    since factored the equivalent into process_rqa_for_datatype. Two files doing
    one job in two shapes is how they drift apart.
    """
    ts1, ts2, time_vals = load_and_align_data(video_id, type1, type2, input_dir)
    if ts1 is None:
        return None

    # Analyse the raw 1-D signals (column vectors for cdist).
    emb1, emb2 = ts1.reshape(-1, 1), ts2.reshape(-1, 1)
    ts1_1d, ts2_1d = ts1, ts2

    # Full-resolution cross-recurrence matrix (used for metrics).
    rec_matrix, threshold, global_rr = calculate_cross_recurrence_matrix(
        emb1, emb2, target_recurrence=target_recurrence)
    print(f"  > Global cross-recurrence rate: {global_rr*100:.2f}%")

    # Asked-for beside achieved, as contract A6 requires wherever an analysis
    # aims at something it may not hit. The threshold is a percentile, so a
    # quantised or partly-still signal lands on a plateau and the target cannot
    # be reached -- 33.7 % against a 7 % request, in silence. rqa.py has
    # reported this since A6 was written; this step never called rate_report at
    # all, so its payload carried a rate with nothing to compare it against.
    target, achieved, rate_warning = _rec.rate_report(target_recurrence, global_rr)
    if rate_warning:
        print(f"  > WARNING: {rate_warning}")

    # Windowed metrics along the line of synchronization (main diagonal).
    # The placement is common/window.py, shared with rqa.py: this file
    # used to carry its own copy, in samples, so the reported time axis
    # moved with the sampling rate and nothing recorded what window was
    # actually used.
    dt = float(np.mean(np.diff(time_vals)))
    n = len(emb1)
    window_plan = _window.plan(n, dt, window_sec, step_sec)
    if window_plan.warning:
        print(f"  > WARNING: {window_plan.warning}")

    windowed_metrics = {'time': window_plan.centres(time_vals),
                        'RR': [], 'DET': [], 'LAM': [], 'L_MAX': []}
    print(f"  > Windowed metrics ({len(window_plan)} windows of "
          f"{window_plan.used[0]:.4g}s, step {window_plan.used[1]:.4g}s)...")
    for start_idx in window_plan.starts:
        end_idx = start_idx + window_plan.length
        w_matrix = rec_matrix[start_idx:end_idx, start_idx:end_idx]
        rr, det, lam, l_max = _rec.window_metrics(w_matrix, dt, self_paired=False)
        windowed_metrics['RR'].append(rr)
        windowed_metrics['DET'].append(det)
        windowed_metrics['LAM'].append(lam)
        windowed_metrics['L_MAX'].append(l_max)

    # Full recurrence plot for visualization, downsampled to <=500x500.
    ts1_vis, ts2_vis, time_vis, matrix_vis, reduction_factor = downsample_for_visualization(
        ts1_1d, ts2_1d, time_vals, rec_matrix
    )
    bitmap = matrix_to_bitmap(matrix_vis)

    pair_key = f"{type1}_vs_{type2}"
    entry = {
        'pair_name': pair_key,
        'series_names': [type1, type2],
        'threshold': float(threshold),
        # Two names for one number. `global_recurrence_rate` is what
        # packages/dims-tabs/crqa.js reads into its plot titles, so it stays;
        # `recurrence_rate` is what rqa.py calls it and what the reference
        # summary has always looked for, finding null.
        'global_recurrence_rate': float(global_rr),
        'recurrence_rate': float(global_rr),
        'target_recurrence': target,
        'achieved_recurrence': achieved,
        'recurrence_rate_warning': rate_warning,
        'time_range': [float(time_vals[0]), float(time_vals[-1])],
        'windowed_metrics': windowed_metrics,
        # Asked-for beside used; see common/window.py.
        'window': window_plan.report(),
        'visualization': {
            'time': time_vis.tolist(),
            'data_x': ts1_vis.tolist(),
            'data_y': ts2_vis.tolist(),
            'matrix_size': len(time_vis),
            'matrix': bitmap,          # bitmap-b64, the full plot reduced
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
        # The analysis at full resolution, in the same file as the
        # picture: both prepared signals on the common grid, from which
        # the matrix is one `cdist` away given the threshold above.
        'full_stats': {
            'n_points': int(n),
            'window_size_sec': window_sec,
            'step_size_sec': step_sec,
            'time': _arrays.pack_f32(time_vals),
            'signal_x': _arrays.pack_f32(ts1_1d),
            'signal_y': _arrays.pack_f32(ts2_1d),
        },
    }
    print(f"  > {pair_key}: matrix {len(time_vis)}x{len(time_vis)}, "
          f"{len(windowed_metrics['time'])} windows")
    return pair_key, entry


def valid_pairs(config):
    """The `[type1, type2]` entries of include_cRQA, with the rest reported.

    Unlike include_crosswavelet, a flat list of data types is NOT expanded to
    all pairs here -- the schema shares one definition between the two keys, so
    it will not catch that for you, and this says so rather than writing
    nothing in silence.
    """
    out = []
    for item in _config.as_list(config, 'include_cRQA', 'pairs of data types'):
        if isinstance(item, list) and len(item) == 2:
            out.append(item)
        else:
            print(f"Warning: Skipping invalid include_cRQA entry: {item}. "
                  f"Expected [type1, type2].")
    return out


def analyse(config, *, input_dir, write, window_sec=20.0, step_sec=1.0,
            target_recurrence=TARGET_RECURRENCE):
    """Every valid pair of every video, written through `write`.

    Everything this needs is an argument. main() builds them from a command line
    and Step.run() builds them from its StepContext; neither calls the other,
    and no module global is reassigned along the way.
    """
    pairs = valid_pairs(config)
    if not pairs:
        print("Error: No valid pairs found in include_cRQA.")
        return

    video_ids = config.get('videoIDs', [])
    if not video_ids:
        print("Error: 'videoIDs' list is empty in config.")
        return

    for vid in video_ids:
        print(f"\n{'='*60}")
        print(f"Processing video: {vid}")
        print(f"{'='*60}")

        video_results = {}
        for type1, type2 in pairs:
            print(f"\nComparing: {type1} <-> {type2}")
            produced = process_crqa_for_pair(
                vid, type1, type2, input_dir=input_dir, window_sec=window_sec,
                step_sec=step_sec, target_recurrence=target_recurrence)
            if produced:
                pair_key, entry = produced
                video_results[pair_key] = entry

        if not video_results:
            print(f"\n[INFO] No cRQA results generated for video {vid}")
            continue

        _step_io.report_merge(write(vid, round_payload({
            'payload_version': _arrays.PAYLOAD_VERSION,
            'crqa_data': video_results,
            'provenance': _payload.provenance(
                target_recurrence=target_recurrence,
                max_points_drawn=MAX_POINTS),
            'precision': precision_note(),
        })))

    print("\ncRQA processing complete!")


def main(argv=None):
    args = _step_io.parse_args(
        'crqa', 'Generate cross-RQA data for the DIMS Dashboard',
        'assets/crqa', argv)

    try:
        with open(args.config, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Error: Config file '{args.config}' not found.")
        return

    if not _config.enabled(config, 'include_cRQA'):
        print("No cRQA requested in config (include_cRQA not found or empty)")
        return

    window_sec, step_sec, target_recurrence = _step_io.tuning(
        config, TUNING_KEY, args.window, args.step, TARGET_RECURRENCE)
    input_dir, output_dir = _step_io.resolve_io(INPUT_DIR, args.output_dir)

    analyse(config, input_dir=input_dir,
            write=_step_io.payload_writer(output_dir, Step.output_name, "cRQA data"),
            window_sec=window_sec, step_sec=step_sec,
            target_recurrence=target_recurrence)


from dims_analysis.base import Step as _Step


class Step(_Step):
    id = "crqa"
    config_key = "include_cRQA"
    output_dir = "assets/crqa"
    output_name = "{video_id}_crqa_data.json"
    description = "Cross-recurrence quantification between pairs of time series"

    #: What `analysis.crqa` in the study's config overrides, key by key.
    defaults = {"window": 20.0, "step": 1.0,
                "targetRecurrence": TARGET_RECURRENCE}

    def run(self, config, ctx):
        """No sys.argv, no chdir, no globals -- see steps/rqa.py for the whole
        story, including the cross-project read this shape removes."""
        params = ctx.params(self, self.defaults)
        analyse(
            config,
            input_dir=ctx.input_dir(INPUT_DIR),
            write=lambda video_id, payload: ctx.write_result(
                self, video_id, payload),
            window_sec=float(params["window"]),
            step_sec=float(params["step"]),
            target_recurrence=float(params["targetRecurrence"]),
        )


# The entry point goes last, after the Step class main() names.
if __name__ == "__main__":
    main()
