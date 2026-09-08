#!/usr/bin/env python3
"""
optional_step_crosswavelet.py https://pycwt.readthedocs.io/en/latest/tutorial/cwt/

Usage:
    python optional_step_crosswavelet.py --config config.json --output-dir assets/rqa
"""
import numpy as np
import pandas as pd
import pycwt as wavelet
from pycwt.helpers import find
import json
import os

# Absolute, not relative: the tests load these steps by file path, where a
# relative import has no parent package to resolve against.
from dims_analysis.common import assets as _assets
from dims_analysis.common import coherence as _coh
from dims_analysis.common import config as _config
from dims_analysis.common import reduce as _reduce
from dims_analysis.common import results as _results
import argparse
from scipy import signal
import warnings

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


warnings.filterwarnings('ignore')

# ==============================================================================
# CONFIGURABLE PARAMETERS - Adjust these as needed
# ==============================================================================

# ---------- Wavelet Transform Parameters ----------
MOTHER_WAVELET = 'morlet'  # Options: 'morlet', 'paul', 'dog', 'mexican_hat'
OMEGA0 = 6                  # Parameter for Morlet wavelet (typically 6)
DJ = 1/12                   # Frequency resolution (1/12 = 12 sub-octaves per octave)
S0_FACTOR = 2               # Smallest scale as multiple of dt (s0 = S0_FACTOR * dt)
J_AUTO = True               # Auto-calculate number of scales based on data length
J_MANUAL = 7                # Manual number of octaves (used if J_AUTO = False)

# ---------- Data Processing Parameters ----------
DETREND_DATA = True         # Whether to detrend the data (polynomial fit removal)
DETREND_ORDER = 1           # Polynomial order for detrending (1 = linear)
MIN_DATA_POINTS = 50        # Minimum number of data points required
INTERPOLATION_METHOD = 'linear'  # Method for interpolating to common time base

# ---------- Significance Testing Parameters ----------
SIGNIFICANCE_LEVEL = 0.95   # Confidence level for significance testing (0.95 = 95%)
USE_AR1_NOISE = True        # Use AR1 noise model for significance (vs white noise)
MONTE_CARLO_ITERATIONS = 0  # Number of Monte Carlo iterations (0 = use theoretical)

# Significance for the *coherence* itself, which is a different question from
# sig95_xwt. sig95_xwt asks "is there more joint energy here than red noise
# would give?" -- a statement about power. Coherence asks "is the phase lag
# steadier than red noise would give?", and it needs its own null, because a
# coherence estimate does not sit at 0 under independence: it is a ratio taken
# over a smoothing neighbourhood, so a handful of random phases still average
# to something well above zero. Measured on the Karnatak data the 95% level is
# ~0.59 and two independent signals score ~0.25 on average -- so an edge value
# of 0.27 is indistinguishable from no coupling at all, which is not something
# the raw number reveals. Only a Monte Carlo against AR(1) surrogates gives it.
WCT_SIGNIF_ENABLED = True   # Compute the Monte Carlo coherence significance level
WCT_SIGNIF_MC_COUNT = 300   # Surrogate pairs per null (pycwt's own default)
# The Monte Carlo is seeded, so the same input gives the same significance
# threshold every time. Unseeded, two runs over identical data disagreed by up
# to 0.04 on the 95% level (mean 0.012 across scales) -- which propagates into
# wtc_signif_fraction, i.e. the reported "% of cells significantly coupled"
# was not reproducible. Set to None to restore the old random behaviour.
#
# On mc_count: this was 100 for a while, as a compromise against the cold-run
# cost. A 95th percentile estimated from 100 samples is noisy -- unseeded, two
# runs over identical data disagreed by up to 0.04 on the level -- and that level
# is what decides whether an edge reads as real or as chance, so the study moved
# to pycwt's default of 300 before publication. The
# disk cache below means that cost is paid once per (alpha, grid) rather than
# per pair, per video and per re-run, so raising this toward pycwt's default
# of 300 is affordable if a tighter null is wanted for publication.
WCT_SIGNIF_SEED = 20250906

# ---------- Per-study tuning (config.json) ----------
# These exist because one study previously had to maintain its own copy of this
# entire file to change two numbers. They are read from
#   config.json -> "analysis": { "crosswavelet": { ... } }
# and fall back to the module defaults below.
#
#   maxPeriod      float | null   longest period to compute, in SECONDS
#   scaleAvgBand   [min, max]     scale-averaging band, in SECONDS
#   maxTimePoints  int            width of the stored picture, in samples
#   maxFreqPoints  int            height of the stored picture, in scales
#
# Note the units: the legacy SCALE_AVG_* constants below are multiples of dt,
# which is a different thing and easy to confuse. The config keys are always
# seconds, so a study never has to know which convention a constant follows.
CONFIG_TUNING_KEY = "crosswavelet"


#: Config keys that switch on a tab which reads `sig95_wtc`. The coherence
#: chance level is displayed by exactly one tab today -- case-karnatak's
#: cross-effector network -- while every study paid to compute it. So the
#: default follows what the study actually contains, and any study can ask for
#: it explicitly. See docs/contracts/analysis-output.md, A7.
COHERENCE_NULL_CONSUMERS = ("include_network",)

#: What to use when a consumer is present and the study did not say.
DEFAULT_MC_COUNT_WITH_CONSUMER = 100


def _payload_provenance(config):
    """Recorded per file: the core that produced it and the surrogate count."""
    from dims_analysis.common.payload import provenance
    tune = _tuning(config)
    return provenance(mc_count=mc_count_for(config),
                      significance_level=SIGNIFICANCE_LEVEL,
                      wct_signif_seed=WCT_SIGNIF_SEED,
                      max_time_points=int(tune.get("maxTimePoints",
                                                   MAX_TIME_POINTS_VIZ)),
                      max_freq_points=int(tune.get("maxFreqPoints",
                                                   MAX_FREQ_POINTS_VIZ)))


def mc_count_for(config):
    """How many surrogates to run, and it is a real decision, not a constant.

    An explicit `analysis.crosswavelet.mcCount` always wins, in both
    directions. Otherwise: 100 if this config enables a tab that reads the
    result, 0 if nothing does.
    """
    given = _tuning(config).get("mcCount")
    if given is not None:
        return int(given)
    for key in COHERENCE_NULL_CONSUMERS:
        if _config.enabled(config, key):
            return DEFAULT_MC_COUNT_WITH_CONSUMER
    return 0


def _tuning(config):
    return ((config or {}).get("analysis") or {}).get(CONFIG_TUNING_KEY) or {}


# ---------- Scale-Averaged Band Parameters ----------
SCALE_AVG_BAND_AUTO = True  # Auto-calculate scale-averaging band
SCALE_AVG_MIN_PERIOD = 2.0  # Minimum period for scale-averaging (in time units)
SCALE_AVG_MAX_PERIOD = 8.0  # Maximum period for scale-averaging (in time units)
# Note: If auto, uses 2*dt to min(8*dt, max_period/2)

# ---------- Coherence Calculation Parameters ----------
# DEPRECATED / UNUSED since the coherence rewrite (see compute_cross_wavelet_standard).
# Smoothing is now delegated to pycwt's validated operator for the chosen mother
# wavelet, which supplies its own time and scale kernels; these four knobs
# belonged to the hand-rolled smoother that produced the power-tracking
# coherence. They are kept only so that an existing config or script that
# references them does not break, and they have no effect.
COHERENCE_SMOOTH_TIME = True    # DEPRECATED, no effect
COHERENCE_SMOOTH_SCALE = True   # DEPRECATED, no effect
COHERENCE_TIME_FACTOR = 1.0     # DEPRECATED, no effect
COHERENCE_SCALE_WIDTH = 0.6     # DEPRECATED, no effect

# ---------- Visualization/Storage Parameters ----------
# Defaults. A study overrides them through analysis.crosswavelet.maxTimePoints
# and .maxFreqPoints: they set how large the browser payload is, and the right
# size depends on the recording. The contract says tuning that can only be
# changed by editing the source is how a fork ends up maintaining its own copy
# of an analysis, and these were exactly that.
MAX_TIME_POINTS_VIZ = 500    # Maximum time points for visualization (downsampling)
MAX_FREQ_POINTS_VIZ = 100    # Maximum frequency points for visualization
# Full-resolution output is NOT controlled here. It is written as a compressed
# .npz beside the JSON, on by default, and switched off per study with
# analysis.crosswavelet.saveFullResolution = false. The old module-level switch
# embedded full-resolution arrays as JSON *lists* inside the browser payload,
# which on a two-minute Karnatak recording would have added roughly half a
# gigabyte of text to a file a browser has to parse. It was removed rather than
# defaulted off, because the next person to find it would have turned it on.
OUTPUT_FORMAT = 'json'       # Output format: 'json', 'npz', or 'both'

# ---------- Analysis Coverage Parameters ----------
COMPUTE_ALL_PAIRS = True        # Compute all possible pairs (not just specified)
SYMMETRIC_PAIRS = False          # Compute both A vs B and B vs A (usually redundant)

# ---------- Quality Control Parameters ----------
HIGH_COHERENCE_THRESHOLD = 0.8  # Threshold for "high coherence" statistics
COI_EXCLUDE = True               # Exclude COI regions from statistics
MIN_COMMON_TIME_FRACTION = 0.5  # Minimum overlap fraction required for pairs
EDGE_TAPER = True                # Apply edge tapering (Tukey window)
TAPER_ALPHA = 0.05               # Tukey window parameter (0-1, smaller = less taper)

# ---------- File Path Parameters ----------
INPUT_DIR = 'assets/timeseries'     # Directory containing input CSV files
OUTPUT_DIR = 'assets/crosswavelet'  # Default output directory
_EFFECTIVE_OUTPUT_DIR = OUTPUT_DIR  # set from --output-dir in main()
FILE_PATTERN = '{video_id}_{data_type}.csv'  # Input file naming pattern

# ---------- Debugging/Logging Parameters ----------
VERBOSE = True              # Print detailed progress information
DEBUG_MODE = False          # Save intermediate results for debugging
PLOT_INPUTS = False         # Plot input time series before processing
SAVE_METADATA = True        # Save analysis metadata in output

# ==============================================================================
# END OF CONFIGURABLE PARAMETERS
# ==============================================================================

def load_and_prepare_timeseries(video_id, data_type, detrend=DETREND_DATA):
    """
    Load and prepare time series data for cross-wavelet analysis.
    Following Torrence and Compo (1998) approach for data preparation.
    
    Parameters:
    - video_id: Video identifier
    - data_type: Type of data (e.g., 'bodysync', 'neuralsync')
    - detrend: Whether to detrend the data
    """
    csv_path = os.path.join(INPUT_DIR, FILE_PATTERN.format(
        video_id=video_id, data_type=data_type
    ))
    
    if not os.path.exists(csv_path):
        if VERBOSE:
            print(f"Warning: File not found: {csv_path}")
        return None, None, None, None, None
    
    # Load data
    df = pd.read_csv(csv_path)
    # Accept the time column under any casing/whitespace -> canonical 'Time'.
    df = df.rename(columns={c: 'Time' for c in df.columns if str(c).strip().lower() == 'time'})

    # Get time column
    if 'Time' not in df.columns:
        if VERBOSE:
            print(f"Error: No 'Time' column in {csv_path}")
        return None, None, None, None, None
    
    # Get all non-time columns
    data_cols = [col for col in df.columns if col != 'Time']
    if not data_cols:
        if VERBOSE:
            print(f"Error: No data columns in {csv_path}")
        return None, None, None, None, None
    
    # Use the first data column
    data_col = data_cols[0]
    
    # Clean data - remove NaN values
    mask = ~pd.isna(df[data_col])
    time_clean = df['Time'][mask].values
    data_clean = df[data_col][mask].values
    
    if len(data_clean) < MIN_DATA_POINTS:
        if VERBOSE:
            print(f"  Insufficient data points ({len(data_clean)}) < {MIN_DATA_POINTS}")
        return None, None, None, None, None
    
    # Calculate sampling interval
    dt = np.median(np.diff(time_clean))
    
    # Detrend if requested
    if detrend and DETREND_ORDER > 0:
        p = np.polyfit(time_clean - time_clean[0], data_clean, DETREND_ORDER)
        data_detrended = data_clean - np.polyval(p, time_clean - time_clean[0])
        if DEBUG_MODE and VERBOSE:
            print(f"  Detrended with polynomial order {DETREND_ORDER}")
    else:
        data_detrended = data_clean - np.mean(data_clean)
    
    # Calculate statistics
    std = data_detrended.std()
    var = std ** 2
    
    # Normalize by standard deviation
    data_normalized = data_detrended / std
    
    if VERBOSE:
        print(f"  Loaded {data_type}: {len(data_clean)} points, dt={dt:.4f}, std={std:.4f}")
    
    return data_normalized, time_clean, dt, std, var

#: The AR(1) coefficient is clamped into this range. The upper bound avoids
#: >= 1, which breaks the significance test. The lower bound is **not** zero:
#: pycwt's rednoise() takes a separate branch at exactly g == 0 that calls
#: numpy.randn, removed in NumPy 2, so a signal with no autocorrelation raised
#: AttributeError and silently lost its coherence null. 0.01 is inside the
#: range where the null barely moves -- measured across alpha 0.3 to 0.97 the
#: 95% level varied by 0.005, within the Monte Carlo noise -- so this changes
#: no result, it only keeps the code out of a broken branch.
AR1_MIN, AR1_MAX = 0.01, 0.95


def _ar1_alpha(data):
    """Lag-1 autocorrelation (AR1 coefficient) for the red-noise significance test.

    pycwt's wavelet.ar1() raises a Warning when a series is short or strongly
    trended ("Cannot place an upperbound on the unbiased AR(1)"). Fall back to a
    plain lag-1 autocorrelation in that case so significance testing still runs
    instead of crashing the whole step.
    """
    try:
        alpha = float(wavelet.ar1(data)[0])
    except Exception:  # noqa: BLE001 — pycwt raises a bare Warning here
        x = np.asarray(data, dtype=float)
        x = x - np.mean(x)
        denom = np.sum(x * x)
        alpha = 0.0 if denom <= 0 else float(np.sum(x[:-1] * x[1:]) / denom)
    return min(max(alpha, AR1_MIN), AR1_MAX)

# Monte Carlo coherence nulls are expensive and highly reusable, so they are
# cached at two levels: in memory for this process, and on disk across runs.
#
# The null depends only on the AR(1) coefficients and the wavelet grid -- NOT on
# the data. pycwt's wct_significance() does not even take the data as an
# argument; it sizes its own surrogates as N = ceil(max_scale * 6), which for a
# typical grid is ~3000 samples. So an 8-second clip pays exactly the same ~45 s
# (at mc_count=100) as a 20-minute recording, and every pair, every video and
# every re-run would pay it again without a cache.
#
# pycwt has its own on-disk cache and it cannot be used: the cache filename is
# built from arctanh(alpha * 4), which is NaN for any alpha > 0.25, so every
# realistic red-noise coefficient collides into one "wct_sig_nan_nan_..." file
# and you silently get back a null computed for different coefficients. We pass
# cache=False and do it ourselves, keyed on everything that actually changes the
# result -- including mc_count and the wavelet parameters, whose omission is
# precisely what makes a cache dangerous rather than merely useless.
_WCT_SIGNIF_CACHE = {}

_WCT_CACHE_DIR = os.environ.get("DIMS_WCT_CACHE_DIR") or os.path.join(
    os.path.expanduser("~"), ".cache", "dims", "wct_significance")
WCT_SIGNIF_DISK_CACHE = os.environ.get("DIMS_WCT_CACHE", "1") != "0"


def _wct_cache_path(key):
    """Filename for a null. The key is hashed so no float formatting can collide."""
    import hashlib
    digest = hashlib.sha256(repr(key).encode("utf-8")).hexdigest()[:32]
    return os.path.join(_WCT_CACHE_DIR, f"wct_{digest}.npy")

def _wct_significance_level(alpha1, alpha2, dt, dj, s0, n_scales, mother_wavelet,
                           mc_count=None):
    """95% coherence level under an AR(1) null, as a per-scale vector.

    Returns None if the Monte Carlo is disabled or fails, in which case the
    caller simply omits the field and the dashboard falls back to its older
    power-significance mask.

    Two pycwt quirks are handled here:

    * Its on-disk cache is unusable. The cache filename is built from
      ``arctanh(alpha * 4)``, which is NaN for any alpha > 0.25 -- so every
      realistic red-noise coefficient collides into a single
      ``wct_sig_nan_nan_...`` file and you silently get back a null computed for
      different coefficients. We always pass cache=False and memoise ourselves.
    * For the largest scales, which lie entirely inside the cone of influence,
      it returns 0 rather than NaN. Zero would mean "every cell is significant",
      the exact opposite of the truth, so those rows are turned into NaN and the
      consumer skips them.

    ``n_scales`` is ``len(scales)`` as returned by ``wavelet.cwt``, NOT the J
    passed to it. With the default J_AUTO, J is a float (e.g. 95.55): cwt
    rounds it up to 97 scales while ``wct_significance(int(J))`` returns 96, and
    the length guard at the call site would then discard the field on every
    single run. Deriving J from the scale count keeps the two aligned.

    Cost is independent of the recording length: pycwt sizes its own surrogates
    from the scale range, so a 2-minute and a 20-minute video pay the same.
    """
    # Clamped here too, not only in _ar1_alpha: this is the function that hands
    # coefficients to pycwt, whose rednoise() has a separate branch at exactly
    # g == 0 calling numpy.randn, removed in NumPy 2. A caller passing 0
    # deserves a level, not an AttributeError swallowed into a missing field.
    alpha1 = min(max(float(alpha1), AR1_MIN), AR1_MAX)
    alpha2 = min(max(float(alpha2), AR1_MIN), AR1_MAX)
    if mc_count is None:
        mc_count = WCT_SIGNIF_MC_COUNT
    mc_count = int(mc_count)
    # 0 means: this study has nothing that reads the result, so do not
    # spend hours computing it. See docs/contracts/analysis-output.md.
    if not WCT_SIGNIF_ENABLED or mc_count <= 0:
        return None

    # Round the coefficients: the null is very insensitive to alpha (the 95%
    # level moves by <0.04 across alpha 0.90-0.97), so pairs that agree to two
    # decimals can share a result.
    key = (round(float(alpha1), 2), round(float(alpha2), 2),
           round(float(dt), 6), round(float(dj), 6), round(float(s0), 6),
           int(n_scales), float(SIGNIFICANCE_LEVEL), int(mc_count),
           str(MOTHER_WAVELET).lower(), float(OMEGA0), WCT_SIGNIF_SEED)
    if key in _WCT_SIGNIF_CACHE:
        return _WCT_SIGNIF_CACHE[key]

    cache_path = _wct_cache_path(key) if WCT_SIGNIF_DISK_CACHE else None
    if cache_path and os.path.exists(cache_path):
        try:
            level = np.load(cache_path)
            if level.ndim == 1 and len(level) == int(n_scales):
                if VERBOSE:
                    print("  Coherence significance: reusing cached null")
                _WCT_SIGNIF_CACHE[key] = level
                return level
        except Exception:  # noqa: BLE001 -- a corrupt cache entry just means recompute
            pass

    rng_state = None
    try:
        # pycwt draws its surrogates from numpy's global RNG, so seeding it here
        # is what makes the threshold reproducible. The previous state is saved
        # and restored so this does not quietly determine anyone else's randomness.
        if WCT_SIGNIF_SEED is not None:
            rng_state = np.random.get_state()
            np.random.seed(WCT_SIGNIF_SEED)
        # pycwt sizes its output with np.zeros(J + 1), so J here is the number
        # of scales minus one, and must be a Python int (it rejects a float).
        level = wavelet.wct_significance(
            float(alpha1), float(alpha2), dt, dj, s0, int(n_scales) - 1,
            significance_level=SIGNIFICANCE_LEVEL, wavelet=mother_wavelet,
            mc_count=mc_count, progress=False, cache=False
        )
    except Exception as exc:  # noqa: BLE001 -- never fail the whole step over this
        if VERBOSE:
            print(f"  WARNING: coherence significance failed ({exc}); "
                  f"field omitted")
        _WCT_SIGNIF_CACHE[key] = None
        return None
    finally:
        if rng_state is not None:
            np.random.set_state(rng_state)

    level = np.asarray(level, dtype=float).ravel()
    level[~np.isfinite(level) | (level <= 0)] = np.nan   # COI-only scales
    _WCT_SIGNIF_CACHE[key] = level

    if cache_path:
        # Write via a temporary file and rename, so an interrupted run cannot
        # leave a truncated .npy that every later run would happily load.
        # np.save() is handed an open file object deliberately: given a *path*
        # it appends ".npy" when the name does not already end in it, which
        # silently breaks the rename below.
        tmp = cache_path + f".{os.getpid()}.tmp"
        try:
            os.makedirs(_WCT_CACHE_DIR, exist_ok=True)
            with open(tmp, "wb") as fh:
                np.save(fh, level)
            os.replace(tmp, cache_path)
        except Exception as exc:  # noqa: BLE001 -- caching is an optimisation, not a requirement
            # Report it: a cache that silently never works is worse than none,
            # because the cost it was meant to remove is paid on every run.
            if VERBOSE:
                print(f"  WARNING: could not cache coherence null ({exc})")
            try:
                os.remove(tmp)
            except OSError:
                pass

    return level

#: Torrence & Compo (1998) eq. 31: for complex wavelets, nu = 2 and
#: Z_2(95%) = 3.999. A real-valued wavelet would use Z_1(95%) = 2.182.
Z2_95 = 3.999


def ar1_background(alpha, period, dt):
    """The AR(1) Fourier spectrum, Torrence & Compo eq. 16.

        P_k = (1 - a^2) / (1 + a^2 - 2a cos(2 pi k / N))

    evaluated at the Fourier frequency each wavelet scale corresponds to. This
    is the background both significance tests are against; multiplying it by
    chi2_2(0.95)/2 reproduces `pycwt.significance` exactly, which is how it was
    checked.
    """
    frequency = dt / np.asarray(period, dtype=float)
    return ((1 - alpha ** 2)
            / (1 + alpha ** 2 - 2 * alpha * np.cos(2 * np.pi * frequency)))


def cross_wavelet_significance(alpha1, alpha2, period, dt,
                               significance_level=None):
    """The 95% level for |W_x W_y*|, per Torrence & Compo eq. 31.

        |W^X W^Y*| / (sigma_X sigma_Y)  =>  (Z_nu(p) / nu) sqrt(P^X_k P^Y_k)

    This is **not** the single-spectrum level of eq. 18, and using that one
    here is the defect this replaces. Two things differ: the constant is
    Z_2(95%)/2 = 1.9995 rather than chi2_2(95%)/2 = 2.9957, and the background
    is the geometric mean of the two series' own spectra rather than one
    spectrum evaluated at the mean of their two coefficients.

    Measured against the paper before the fix: the level came out 1.50 times
    too high when the two coefficients matched, 1.71 at alpha = (0.9, 0.5), and
    2.39 at (0.95, 0.2). The payload stores power/level, so the stored
    `sig95_xwt` was that much too small -- and the cross-wavelet tab draws a
    phase arrow only where it exceeds 1, so it drew far too few.

    `significance_level` is accepted for symmetry with pycwt but only 0.95 has
    a published Z; anything else raises rather than quietly using the wrong
    constant.
    """
    level = SIGNIFICANCE_LEVEL if significance_level is None else significance_level
    if abs(level - 0.95) > 1e-9:
        raise ValueError(
            f"Torrence & Compo eq. 31 tabulates Z only at 95% (Z_2 = {Z2_95}); "
            f"a {level:.0%} cross-wavelet level would need a value this "
            f"implementation does not have.")
    background = (ar1_background(alpha1, period, dt)
                  * ar1_background(alpha2, period, dt))
    return (Z2_95 / 2.0) * np.sqrt(background)


def compute_cross_wavelet_standard(data1, data2, time, dt,
                                   mother=MOTHER_WAVELET, omega0=OMEGA0,
                                   dj=DJ, s0=None, J=None, max_period=None,
                                   mc_count=None):
    """
    Compute cross-wavelet transform between two time series using pycwt standard approach.
    
    Parameters:
    - data1, data2: Input time series (normalized)
    - time: Time array
    - dt: Sampling interval
    - mother: Mother wavelet name
    - omega0: Omega0 for Morlet wavelet
    - dj: Frequency resolution parameter
    - s0: Smallest scale
    - J: Number of scales
    """
    
    N = len(data1)
    
    # Set default parameters following Torrence & Compo
    if s0 is None:
        s0 = S0_FACTOR * dt  # Starting scale
    
    if J is None:
        if J_AUTO:
            J = np.log2(N * dt / s0) / dj  # Auto-calculate number of scales
        else:
            J = J_MANUAL / dj  # Use manual setting
    
    # Cap the longest period, if the study asked for one. For a Morlet wavelet
    # period ~= scale and scales follow s = s0 * 2^(j*dj), so this is the largest
    # scale index whose period still fits. Studies with a known upper bound on
    # the timescale of interest use this to avoid computing scales they will
    # never look at -- and to keep the scale-averaged band meaningful.
    if max_period is not None:
        J_cap = np.floor(np.log2(float(max_period) / s0) / dj)   # floor: stay <= max_period
        J = min(J, J_cap)

    # Select mother wavelet
    if mother.lower() == 'morlet':
        mother_wavelet = wavelet.Morlet(omega0)
    elif mother.lower() == 'paul':
        mother_wavelet = wavelet.Paul()
    elif mother.lower() == 'dog':
        mother_wavelet = wavelet.DOG()
    elif mother.lower() == 'mexican_hat':
        mother_wavelet = wavelet.MexicanHat()
    else:
        if VERBOSE:
            print(f"Unknown wavelet '{mother}', using Morlet")
        mother_wavelet = wavelet.Morlet(omega0)
    
    # Calculate lag-1 autocorrelation for AR1 noise model
    if USE_AR1_NOISE:
        alpha1 = _ar1_alpha(data1)
        alpha2 = _ar1_alpha(data2)
    else:
        alpha1 = alpha2 = 0.0  # White noise
    
    if DEBUG_MODE and VERBOSE:
        print(f"  AR1 coefficients: α1={alpha1:.3f}, α2={alpha2:.3f}")
    
    # Perform continuous wavelet transform for both series
    W1, scales, freqs, coi, fft1, fftfreqs = wavelet.cwt(
        data1, dt, dj, s0, J, mother_wavelet
    )
    
    W2, _, _, _, fft2, _ = wavelet.cwt(
        data2, dt, dj, s0, J, mother_wavelet
    )
    
    # Calculate cross-wavelet transform
    XWT = W1 * np.conj(W2)
    
    # Calculate cross-wavelet power
    power = np.abs(XWT)
    
    # Calculate phase difference
    phase = np.angle(XWT)

    # Convert frequencies to periods
    period = 1 / freqs

    # Significance for the cross-wavelet spectrum, which has its own
    # distribution -- Torrence & Compo eq. 31, not the single-spectrum eq. 18.
    # See cross_wavelet_significance below.
    signif_xwt = cross_wavelet_significance(alpha1, alpha2, period, dt)
    sig95_xwt = np.ones([1, N]) * signif_xwt[:, None]
    sig95_xwt = power / sig95_xwt
    
    # ------------------------------------------------------------------
    # Wavelet coherence (Torrence & Webster 1999):
    #
    #            | S( s^-1 * W1 * conj(W2) ) |^2
    #   R^2 = ---------------------------------------
    #         S( s^-1 |W1|^2 ) * S( s^-1 |W2|^2 )
    #
    # The smoothing operator S MUST be applied to the *complex* cross
    # spectrum. Where the phase relationship is unstable the complex terms
    # cancel under smoothing and coherence drops -- that cancellation is the
    # entire content of the measure.
    #
    # A previous implementation here rolled its own smoother that took
    # np.abs(W)**2 of every argument, including the complex XWT. That
    # destroyed phase before smoothing (so the numerator could never cancel)
    # and left the expression unnormalised -- O(|W|^4) over O(|W|^2) -- which
    # was masked by clipping the result at 1.0. The stored field ended up
    # tracking power instead of phase coupling: ~57-62% of cells sat at
    # exactly 1.0 and it correlated +0.87 with log power. See
    # notebooks/coherence_period_bands.ipynb in DIMS_Dashboard_Karnatak for
    # the full diagnosis.
    #
    # We now delegate the smoothing to pycwt's validated operator, which
    # applies the scale normalisation and the correct time/scale kernels for
    # the chosen mother wavelet.
    # ------------------------------------------------------------------
    # One implementation, shared with the regression tests that guard it:
    # dims_analysis.common.coherence. The tests used to carry their own copy
    # of this formula, and the copy had already fallen behind -- it omitted
    # the undefined-cell masking below, so the suite protecting the most
    # consequential defect in this project was checking something the product
    # no longer did.
    WCO, undefined = _coh.coherence(W1, W2, scales, dt, dj, mother_wavelet)

    if undefined.any():
        frac = float(undefined.mean())
        if VERBOSE or frac > 0.02:
            print(f"  {frac:.1%} of cells have too little power to define coherence "
                  f"(drawn as gaps, not as 1.0)")

    # 95% coherence level under an AR(1) null (see _wct_significance_level).
    # This is what makes an individual coherence value interpretable: without
    # it, 0.27 and 0.55 look like "some coupling" and "more coupling", when in
    # fact the first is exactly what independent signals produce.
    sig95_wtc = _wct_significance_level(alpha1, alpha2, dt, dj, s0, len(scales),
                                        mother_wavelet, mc_count=mc_count)
    if sig95_wtc is not None and len(sig95_wtc) != len(scales):
        if VERBOSE:
            print(f"  WARNING: coherence significance length {len(sig95_wtc)} "
                  f"!= {len(scales)} scales; field omitted")
        sig95_wtc = None

    # Phase angles for plotting (only where coherence is significant)
    phase_angle = np.angle(XWT)
    
    # Global wavelet spectrum (time-averaged)
    global_power = power.mean(axis=1)
    
    # KNOWN WRONG, and deliberately left so rather than half-corrected.
    #
    # This is the same defect that eq. 31 fixed for the local spectrum: it
    # applies a *single-spectrum* significance to a cross-wavelet quantity, and
    # evaluates the background at the mean of the two alphas rather than
    # combining the two spectra. `power` here is |W_x W_y*|.
    #
    # Torrence & Compo give eq. 31 only for the local spectrum; the
    # time-averaged and scale-averaged cross-wavelet distributions are in
    # Torrence & Webster (1999), which is not in examples/reference/. Guessing
    # at them would be worse than the current state, which is at least
    # recorded.
    #
    # Nothing reads either field -- grepped across dims-tabs and both studies'
    # own tabs -- so this is stored, wrong, and unused. It should be corrected
    # against that paper or removed; there is a test pinning the fact.
    dof = N - scales
    global_signif, _ = wavelet.significance(
        1.0, dt, scales, 1, np.mean([alpha1, alpha2]),
        significance_level=SIGNIFICANCE_LEVEL, dof=dof, wavelet=mother_wavelet
    )
    
    return {
        'W1': W1,
        'W2': W2,
        'XWT': XWT,
        'power': power,
        'phase': phase_angle,
        'coherence': WCO,
        'scales': scales,
        'freqs': freqs,
        'period': period,
        'coi': coi,
        'sig95_xwt': sig95_xwt,
        'sig95_wtc': sig95_wtc,
        'signif_xwt': signif_xwt,
        'global_power': global_power,
        'global_signif': global_signif,
        'mother': mother_wavelet,
        'dt': dt,
        'alpha1': alpha1,
        'alpha2': alpha2,
        'dj': dj,
        's0': s0,
        'J': J
    }

def _reduce_time(a, factor):
    """Block-average along the last (time) axis."""
    if factor <= 1:
        return np.asarray(a)
    a = np.asarray(a)
    keep = (a.shape[-1] // factor) * factor
    if keep == 0:
        return a
    t = a[..., :keep]
    return t.reshape(*t.shape[:-1], keep // factor, factor).mean(axis=-1)


def _reduce_null(levels, factor):
    """Reduce the coherence null along the period axis, NaN-aware.

    Rows lying entirely inside the cone of influence carry NaN: no threshold
    could be estimated there. Both directions matter when blocks are averaged.
    A NaN neighbour must not drag a usable row to NaN, or good rows are lost;
    and a block that is *all* NaN must stay NaN rather than becoming a number,
    or a whole period band reads as always-significant.

    Returns None when there is no null to reduce, which is what a study that
    did not ask for the Monte Carlo produces.
    """
    if levels is None:
        return None
    values = np.asarray(levels, dtype=float)
    if factor <= 1:
        return np.real(values)
    keep = (len(values) // factor) * factor
    if keep == 0:
        return np.real(values)
    with np.errstate(invalid='ignore'):
        return np.nanmean(values[:keep].reshape(-1, factor), axis=1)


def _reduce_freq(a, factor):
    """Block-average along the first (period/frequency) axis."""
    if factor <= 1:
        return np.asarray(a)
    a = np.asarray(a)
    keep = (a.shape[0] // factor) * factor
    if keep == 0:
        return a
    t = a[:keep]
    return t.reshape(keep // factor, factor, *t.shape[1:]).mean(axis=1)


def downsample_for_storage(cwt_results, time, scale_avg_power, 
                           max_time_points=MAX_TIME_POINTS_VIZ, 
                           max_freq_points=MAX_FREQ_POINTS_VIZ):
    """
    Downsample the wavelet results for efficient storage and visualization.
    """
    n_time = len(time)
    n_freq = len(cwt_results['freqs'])

    # `reduce.factor_for`, not floor division. This step computed its own
    # factors the old way, so the cap was a suggestion: 1024 samples against a
    # 500-point cap gave factor 2 and drew 512, and 999 gave factor 1 and drew
    # all 999 -- twice the cap, across every array in the file.
    time_factor = _reduce.factor_for(n_time, max_time_points)
    freq_factor = _reduce.factor_for(n_freq, max_freq_points)
    
    # Block-average, not stride. See _reduce_time / _reduce_freq.
    time_ds = _reduce_time(time, time_factor)

    freqs_ds = _reduce_freq(cwt_results['freqs'], freq_factor)
    period_ds = _reduce_freq(cwt_results['period'], freq_factor)
    scales_ds = _reduce_freq(cwt_results['scales'], freq_factor)

    power_ds = np.real(_reduce_time(_reduce_freq(cwt_results['power'], freq_factor), time_factor))
    # Phase is an angle: averaging it directly would turn +179 and -179 into 0.
    # Average the unit vectors and take the angle back.
    _ph = cwt_results['phase']
    phase_ds = np.angle(_reduce_time(_reduce_freq(np.exp(1j * np.asarray(_ph)), freq_factor), time_factor))
    coherence_ds = np.real(_reduce_time(_reduce_freq(cwt_results['coherence'], freq_factor), time_factor))
    sig95_xwt_ds = np.real(_reduce_time(_reduce_freq(cwt_results['sig95_xwt'], freq_factor), time_factor))

    coi_ds = np.real(_reduce_time(cwt_results['coi'], time_factor))
    signif_xwt_ds = np.real(_reduce_freq(cwt_results['signif_xwt'], freq_factor))
    # Per-period coherence null; may be absent if the Monte Carlo was skipped.
    # Averaged with NaN-awareness: COI-only rows are NaN and must not poison
    # their neighbours in a block.
    sig95_wtc_ds = _reduce_null(cwt_results.get('sig95_wtc'), freq_factor)
    global_power_ds = np.real(_reduce_freq(cwt_results['global_power'], freq_factor))
    global_signif_ds = np.real(_reduce_freq(cwt_results['global_signif'], freq_factor))
    scale_avg_power_ds = np.real(_reduce_time(scale_avg_power, time_factor))
    
    if VERBOSE and (time_factor > 1 or freq_factor > 1):
        print(f"  Reduced for the browser: time {n_time}->{len(time_ds)}, "
              f"freq {n_freq}->{len(freqs_ds)} (block-averaged)")

    # NaN has no JSON literal and JSON.parse() rejects it outright, so the
    # unusable (COI-only) scales are emitted as null instead.
    sig95_wtc_json = (None if sig95_wtc_ds is None else
                      [None if not np.isfinite(v) else float(v)
                       for v in sig95_wtc_ds])

    def _json_safe(a):
        """NaN has no JSON literal, and JSON.parse rejects the bare token that
        json.dump would write. Undefined cells travel as null, which the browser
        draws as a gap."""
        a = np.asarray(a, dtype=float)
        return np.where(np.isfinite(a), a, None).tolist()

    return {
        'time': time_ds.tolist(),
        'freqs': freqs_ds.tolist(),
        'period': period_ds.tolist(),
        'scales': scales_ds.tolist(),
        'power': _json_safe(power_ds),
        'phase': _json_safe(phase_ds),
        'coherence': _json_safe(coherence_ds),
        'coi': coi_ds.tolist(),
        'sig95_xwt': _json_safe(sig95_xwt_ds),
        'sig95_wtc': sig95_wtc_json,
        'signif_xwt': signif_xwt_ds.tolist(),
        'global_power': global_power_ds.tolist(),
        'global_signif': global_signif_ds.tolist(),
        'scale_avg_power': scale_avg_power_ds.tolist(),
        'downsampling_factors': {
            'time_factor': time_factor,
            'freq_factor': freq_factor
        }
    }

def calculate_summary_statistics(cwt_results, time, scale_avg_power, scale_avg_signif):
    """
    Calculate summary statistics from cross-wavelet results.
    """
    power = cwt_results['power']
    coherence = cwt_results['coherence']
    phase = cwt_results['phase']
    freqs = cwt_results['freqs']
    period = cwt_results['period']
    coi = cwt_results['coi']
    scales = cwt_results['scales']
    global_power = cwt_results['global_power']
    global_signif = cwt_results['global_signif']
    
    # Create COI mask if requested
    if COI_EXCLUDE:
        coi_mask = np.zeros_like(power, dtype=bool)
        for i, c in enumerate(coi):
            coi_mask[:, i] = scales[:, np.newaxis].flatten() > c
    else:
        coi_mask = np.zeros_like(power, dtype=bool)
    
    # Mask out COI regions
    power_valid = np.ma.masked_array(power, coi_mask)
    # Undefined cells (too little power to define coherence) are masked out of
    # the statistics as well, otherwise one of them turns every summary NaN.
    coherence_valid = np.ma.masked_array(
        coherence, coi_mask | ~np.isfinite(np.asarray(coherence, dtype=float)))
    
    # Dominant frequency at each time point (outside COI)
    dominant_freq_idx = np.ma.argmax(power_valid, axis=0)
    dominant_freqs = freqs[dominant_freq_idx]
    
    # Convert to list, handling masked arrays
    if isinstance(dominant_freqs, np.ma.MaskedArray):
        dominant_freqs_list = dominant_freqs.filled(0).tolist()
    else:
        dominant_freqs_list = dominant_freqs.tolist()
    
    # Phase statistics (circular mean)
    mean_phase_by_freq = np.angle(np.mean(np.exp(1j * phase), axis=1))
    
    # Time-frequency regions of high coherence
    with np.errstate(invalid='ignore'):
        high_coherence_regions = np.asarray(coherence) > HIGH_COHERENCE_THRESHOLD
    high_coherence_regions &= np.isfinite(np.asarray(coherence, dtype=float))
    
    # Calculate percent of time each frequency shows high coherence
    high_coherence_by_freq = np.sum(high_coherence_regions & ~coi_mask, axis=1) / np.maximum(np.sum(~coi_mask, axis=1), 1)

    # Share of usable cells whose coherence beats the AR(1) coherence null.
    # This is the number that says whether a pair is coupled at all, and it is
    # the one to read rather than mean_coherence: under independence it sits at
    # ~0.05 by construction, so anything near that means "no coupling detected",
    # however respectable the mean coherence looks.
    sig95_wtc = cwt_results.get('sig95_wtc')
    wtc_signif_fraction = None
    if sig95_wtc is not None:
        level = np.asarray(sig95_wtc, dtype=float)[:, np.newaxis]
        usable = (~coi_mask & np.isfinite(level)
                  & np.isfinite(np.asarray(coherence, dtype=float)))
        n_usable = int(np.sum(usable))
        if n_usable > 0:
            wtc_signif_fraction = float(np.sum((coherence > level) & usable) / n_usable)

    return {
        'wtc_signif_fraction': wtc_signif_fraction,
        'wtc_signif_level_median': (float(np.nanmedian(sig95_wtc))
                                    if sig95_wtc is not None
                                    and np.any(np.isfinite(sig95_wtc)) else None),
        'global_power': global_power.tolist(),
        'global_signif': global_signif.tolist(),
        'dominant_freqs': dominant_freqs_list,
        'mean_phase_by_freq': mean_phase_by_freq.tolist(),
        'high_coherence_by_freq': high_coherence_by_freq.tolist(),
        'high_coherence_fraction': float(np.sum(high_coherence_regions & ~coi_mask) / np.sum(~coi_mask)) if np.sum(~coi_mask) > 0 else 0,
        'max_coherence': float(np.max(coherence_valid)) if coherence_valid.count() > 0 else 0,
        'mean_coherence': float(np.mean(coherence_valid)) if coherence_valid.count() > 0 else 0,
        'scale_avg_power_mean': float(np.mean(scale_avg_power)),
        'scale_avg_signif': float(scale_avg_signif),
        'coherence_threshold_used': HIGH_COHERENCE_THRESHOLD
    }

def process_cross_wavelet_pair(video_id, data_type1, data_type2, config):
    """
    Process cross-wavelet analysis for a pair of data types following pycwt standard.
    """
    if VERBOSE:
        print(f"\nProcessing cross-wavelet: {data_type1} vs {data_type2}")
    
    # Load both time series
    data1, time1, dt1, std1, var1 = load_and_prepare_timeseries(video_id, data_type1)
    data2, time2, dt2, std2, var2 = load_and_prepare_timeseries(video_id, data_type2)
    
    if data1 is None or data2 is None:
        if VERBOSE:
            print(f"  Failed to load data for {data_type1} or {data_type2}")
        return None
    
    # Ensure both series have the same time base
    # Find common time range
    t_start = max(time1[0], time2[0])
    t_end = min(time1[-1], time2[-1])
    
    # Check minimum overlap
    overlap_fraction = (t_end - t_start) / max(time1[-1] - time1[0], time2[-1] - time2[0])
    if overlap_fraction < MIN_COMMON_TIME_FRACTION:
        if VERBOSE:
            print(f"  Insufficient overlap ({overlap_fraction:.1%} < {MIN_COMMON_TIME_FRACTION:.1%})")
        return None
    
    # Use the smaller dt (higher sampling rate)
    dt = min(dt1, dt2)
    
    # Create common time array
    n_samples = int((t_end - t_start) / dt) + 1
    time_common = np.linspace(t_start, t_end, n_samples)
    
    # Interpolate both series to common time base
    if INTERPOLATION_METHOD == 'linear':
        data1_interp = np.interp(time_common, time1, data1)
        data2_interp = np.interp(time_common, time2, data2)
    elif INTERPOLATION_METHOD == 'cubic':
        from scipy.interpolate import interp1d
        f1 = interp1d(time1, data1, kind='cubic', fill_value='extrapolate')
        f2 = interp1d(time2, data2, kind='cubic', fill_value='extrapolate')
        data1_interp = f1(time_common)
        data2_interp = f2(time_common)
    else:
        data1_interp = np.interp(time_common, time1, data1)
        data2_interp = np.interp(time_common, time2, data2)
    
    if VERBOSE:
        print(f"  Common time base: {len(time_common)} points, dt={dt:.4f}")
    
    # Apply edge taper if requested
    if EDGE_TAPER:
        # scipy>=1.13 moved tukey to scipy.signal.windows; fall back for older versions.
        tukey = getattr(signal, "tukey", None) or signal.windows.tukey
        window = tukey(len(time_common), alpha=TAPER_ALPHA)
        data1_interp = data1_interp * window
        data2_interp = data2_interp * window
        if DEBUG_MODE and VERBOSE:
            print(f"  Applied Tukey window with α={TAPER_ALPHA}")
    
    # Compute cross-wavelet transform using standard approach
    cwt_results = compute_cross_wavelet_standard(
        data1_interp, data2_interp, time_common, dt,
        mother=MOTHER_WAVELET, omega0=OMEGA0, dj=DJ,
        max_period=_tuning(config).get("maxPeriod"),
        mc_count=mc_count_for(config)
    )
    
    # Calculate scale-averaged wavelet power
    period = cwt_results['period']
    power = cwt_results['power']
    
    # Determine scale-averaging band
    band = _tuning(config).get("scaleAvgBand")
    if band and len(band) == 2:
        # Given in seconds, so it means the same thing whatever dt is.
        avg_period_min = float(band[0])
        avg_period_max = min(float(band[1]), period[-1])
    elif SCALE_AVG_BAND_AUTO:
        avg_period_min = S0_FACTOR * dt
        avg_period_max = min(SCALE_AVG_MAX_PERIOD * dt, period[-1] / 2)
    else:
        avg_period_min = SCALE_AVG_MIN_PERIOD * dt
        avg_period_max = min(SCALE_AVG_MAX_PERIOD * dt, period[-1])
    
    sel = find((period >= avg_period_min) & (period <= avg_period_max))
    
    if len(sel) > 0:
        # Scale-averaged power
        Cdelta = cwt_results['mother'].cdelta
        # Create scale matrix properly for broadcasting: (n_scales, n_times)
        scale_avg = cwt_results['scales'][:, np.newaxis] * np.ones((1, len(time_common)))
        scale_avg = power / scale_avg
        scale_avg_power = cwt_results['dj'] * dt / Cdelta * scale_avg[sel, :].sum(axis=0)
        
        # Significance for scale-averaged power.
        # KNOWN WRONG in the same way as global_signif above, and unread.
        scale_avg_signif, _ = wavelet.significance(
            1.0, dt, cwt_results['scales'], 2, 
            np.mean([cwt_results['alpha1'], cwt_results['alpha2']]),
            significance_level=SIGNIFICANCE_LEVEL,
            dof=[cwt_results['scales'][sel[0]], cwt_results['scales'][sel[-1]]],
            wavelet=cwt_results['mother']
        )
        
        if VERBOSE:
            print(f"  Scale-averaging band: {avg_period_min:.2f} - {avg_period_max:.2f}")
    else:
        scale_avg_power = np.zeros(len(time_common))
        scale_avg_signif = 0
        if VERBOSE:
            print("  Warning: No scales in averaging band")
    
    # Calculate summary statistics
    stats = calculate_summary_statistics(cwt_results, time_common, scale_avg_power, scale_avg_signif)
    
    # Downsample for storage
    _tune = _tuning(config)
    downsampled = downsample_for_storage(
        cwt_results, time_common, scale_avg_power,
        max_time_points=int(_tune.get("maxTimePoints", MAX_TIME_POINTS_VIZ)),
        max_freq_points=int(_tune.get("maxFreqPoints", MAX_FREQ_POINTS_VIZ)))
    
    # Prepare output data structure
    result = {
        'data_type1': data_type1,
        'data_type2': data_type2,
        'dt': float(dt),
        'time_range': [float(t_start), float(t_end)],
        'n_samples': int(n_samples),
        'mother_wavelet': MOTHER_WAVELET,
        'omega0': OMEGA0 if MOTHER_WAVELET.lower() == 'morlet' else None,
        'dj': float(cwt_results['dj']),
        's0': float(cwt_results['s0']),
        'J': float(cwt_results['J']),
        'alpha1': float(cwt_results['alpha1']),
        'alpha2': float(cwt_results['alpha2']),
        'statistics': stats,
        'scale_avg_band': [float(avg_period_min), float(avg_period_max)],
        'visualization': downsampled
    }
    
    # Add metadata if requested
    if SAVE_METADATA:
        result['metadata'] = {
            'detrend': DETREND_DATA,
            'detrend_order': DETREND_ORDER if DETREND_DATA else None,
            'edge_taper': EDGE_TAPER,
            'taper_alpha': TAPER_ALPHA if EDGE_TAPER else None,
            'significance_level': SIGNIFICANCE_LEVEL,
            'coherence_threshold': HIGH_COHERENCE_THRESHOLD,
            'interpolation_method': INTERPOLATION_METHOD
        }
    
    # The analysis itself, at the resolution it was computed at. The JSON beside
    # it is a browser payload; this is what a notebook or any downstream
    # analysis should read. Off with
    # analysis.crosswavelet.saveFullResolution = false.
    if _tuning(config).get("saveFullResolution", True):
        try:
            npz = save_full_resolution(_EFFECTIVE_OUTPUT_DIR, video_id,
                                       f"{data_type1}_vs_{data_type2}",
                                       cwt_results, time_common, scale_avg_power)
            if VERBOSE:
                print(f"  Full-resolution analysis -> {npz}")
        except Exception as exc:  # noqa: BLE001 - never lose a run over this
            print(f"  WARNING: could not write full-resolution output ({exc})")

    return result


def save_full_resolution(out_dir, video_id, pair_key, cwt_results, time, scale_avg_power):
    """Write the analysis at the resolution it was computed at.

    The JSON beside this is a *browser payload*: reduced to a few hundred points
    so a page can draw it. It was for a long time the only thing kept, which
    meant anyone continuing the analysis from a study's output was silently
    working at a fraction of the resolution -- and, before block-averaging, from
    an aliased copy.

    This is the artifact to analyse from. Compressed .npz, one file per video,
    with a group of arrays per pair.
    """
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{video_id}_crosswavelet.npz")

    prefix = pair_key.replace('/', '_')
    arrays = {
        f"{prefix}/time": np.asarray(time, dtype=np.float64),
        f"{prefix}/period": np.real(cwt_results['period']).astype(np.float64),
        f"{prefix}/freqs": np.real(cwt_results['freqs']).astype(np.float64),
        f"{prefix}/coherence": np.real(cwt_results['coherence']).astype(np.float32),
        f"{prefix}/power": np.real(cwt_results['power']).astype(np.float32),
        f"{prefix}/phase": np.real(cwt_results['phase']).astype(np.float32),
        f"{prefix}/coi": np.real(cwt_results['coi']).astype(np.float64),
        f"{prefix}/scale_avg_power": np.real(scale_avg_power).astype(np.float64),
    }
    if cwt_results.get('sig95_wtc') is not None:
        arrays[f"{prefix}/sig95_wtc"] = np.asarray(cwt_results['sig95_wtc'], dtype=np.float64)

    # Append rather than rewrite. A .npz is a zip of .npy members, so a new
    # pair can be added without touching the ones already there. The obvious
    # implementation -- load everything, add one pair, recompress -- is
    # quadratic: a study with fifteen pairs recompressed the whole file fifteen
    # times, and on a twenty-minute recording that is gigabytes of needless work
    # per video, with every earlier pair held in memory while it happens.
    if not _append_to_npz(path, arrays):
        # A name collision (the same pair written twice, e.g. a re-run) or a
        # corrupt file: fall back to rebuilding the file from scratch.
        existing = {}
        if os.path.exists(path):
            try:
                with np.load(path, allow_pickle=False) as z:
                    existing = {k: z[k] for k in z.files}
            except Exception:  # noqa: BLE001 - a corrupt file is replaced
                existing = {}
        existing.update(arrays)
        np.savez_compressed(path, **existing)
    return path


def _append_to_npz(path, arrays):
    """Add arrays to a .npz as new zip members. False if that is not possible.

    Returns False when any name is already present (the caller then rebuilds the
    file, so a re-run replaces a pair instead of shadowing it with a duplicate
    zip entry) or when the existing file cannot be read as a zip.
    """
    import zipfile
    from numpy.lib import format as _npformat

    members = {f"{name}.npy": arr for name, arr in arrays.items()}
    if os.path.exists(path):
        try:
            with zipfile.ZipFile(path) as zf:
                if set(zf.namelist()) & set(members):
                    return False
        except (zipfile.BadZipFile, OSError):
            return False
    mode = 'a' if os.path.exists(path) else 'w'
    try:
        with zipfile.ZipFile(path, mode=mode, compression=zipfile.ZIP_DEFLATED,
                             allowZip64=True) as zf:
            for member, arr in members.items():
                with zf.open(member, 'w', force_zip64=True) as fh:
                    _npformat.write_array(fh, np.asarray(arr), allow_pickle=False)
    except (zipfile.BadZipFile, OSError):
        return False
    return True

def main():
    parser = argparse.ArgumentParser(description='Generate Cross-Wavelet data for DIMS Dashboard')
    parser.add_argument('--config', default='config.json', help='Path to config.json')
    parser.add_argument('--output-dir', default=OUTPUT_DIR, help='Output directory for cross-wavelet data')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    
    # Override global settings if command-line args provided
    global VERBOSE, DEBUG_MODE, _EFFECTIVE_OUTPUT_DIR, INPUT_DIR
    # A private study's data lives outside the repository, at the path
    # data.local.json names. Without this, running a step from the case
    # directory finds nothing and blames the input files.
    _note = _assets.describe()
    if _note:
        print(_note)
    INPUT_DIR = _assets.resolve(INPUT_DIR)
    args.output_dir = _assets.resolve(args.output_dir)
    _EFFECTIVE_OUTPUT_DIR = args.output_dir
    if args.verbose:
        VERBOSE = True
    if args.debug:
        DEBUG_MODE = True
        VERBOSE = True
    
    # Load config
    with open(args.config, 'r') as f:
        config = json.load(f)
    
    # Check if cross-wavelet is requested
    if not _config.enabled(config, 'include_crosswavelet'):
        if VERBOSE:
            print("No cross-wavelet analysis requested in config")
        return
    
    # include_crosswavelet may be either:
    #   * a list of explicit [type1, type2] pairs (new, lets the user pick exactly
    #     which pairs to compute), or
    #   * a legacy flat list of data types, expanded to all unique pairs below.
    raw_cwt = _config.as_list(config, 'include_crosswavelet',
                              'pairs of data types')

    # Say which way the coherence null went and why. The decision is a real one
    # -- it is the difference between seconds and hours -- and it used to be a
    # constant nobody could see, let alone change.
    _mc = mc_count_for(config)
    if _mc > 0:
        _why = ("mcCount is set in config.json"
                if _tuning(config).get("mcCount") is not None
                else f"{' or '.join(COHERENCE_NULL_CONSUMERS)} is enabled")
        print(f"coherence null: {_mc} surrogates ({_why})")
    else:
        print("coherence null: skipped -- nothing in this config reads it. "
              "Set analysis.crosswavelet.mcCount to compute it anyway.")
    if all(isinstance(item, (list, tuple)) and len(item) == 2 for item in raw_cwt):
        base_pairs = [(t1, t2) for t1, t2 in raw_cwt]
    else:
        flat_types = [t for t in raw_cwt if isinstance(t, str)]
        if len(flat_types) < 2:
            print("Error: Need at least 2 data types for cross-wavelet analysis")
            return
        base_pairs = []
        for i in range(len(flat_types)):
            for j in range(i + 1, len(flat_types)):
                base_pairs.append((flat_types[i], flat_types[j]))

    if not base_pairs:
        print("Error: No valid cross-wavelet pairs found")
        return
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Print configuration summary if verbose
    if VERBOSE:
        print("\n" + "="*60)
        print("CROSS-WAVELET ANALYSIS CONFIGURATION")
        print("="*60)
        print(f"Mother Wavelet: {MOTHER_WAVELET}")
        if MOTHER_WAVELET.lower() == 'morlet':
            print(f"  Omega0: {OMEGA0}")
        print(f"Frequency Resolution (dj): {DJ}")
        print(f"Smallest Scale Factor: {S0_FACTOR}")
        print(f"Significance Level: {SIGNIFICANCE_LEVEL*100}%")
        print(f"Detrending: {DETREND_DATA} (order {DETREND_ORDER})" if DETREND_DATA else "Detrending: False")
        print(f"Edge Tapering: {EDGE_TAPER} (α={TAPER_ALPHA})" if EDGE_TAPER else "Edge Tapering: False")
        print(f"High Coherence Threshold: {HIGH_COHERENCE_THRESHOLD}")
        print(f"Visualization Resolution: {MAX_TIME_POINTS_VIZ} × {MAX_FREQ_POINTS_VIZ}")
        print(f"Output Format: {OUTPUT_FORMAT}")
        print("="*60)
    
    # Process each video
    for video_id in config['videoIDs']:
        if VERBOSE:
            print(f"\n{'='*50}")
            print(f"Processing video: {video_id}")
            print(f"{'='*50}")
        
        # Process all pairs
        cwt_results = {}
        
        # Pairs to compute (optionally adding the reverse of each for symmetry).
        pairs_to_compute = []
        for data_type1, data_type2 in base_pairs:
            pairs_to_compute.append((data_type1, data_type2))
            if SYMMETRIC_PAIRS:
                pairs_to_compute.append((data_type2, data_type1))
        
        if VERBOSE:
            print(f"Computing {len(pairs_to_compute)} pair(s)")
        
        # Process each pair
        for data_type1, data_type2 in pairs_to_compute:
            pair_key = f"{data_type1}_vs_{data_type2}"
            
            result = process_cross_wavelet_pair(
                video_id, data_type1, data_type2, config
            )
            
            if result:
                cwt_results[pair_key] = result
        
        # Save results
        if cwt_results:
            # Determine output format and save
            if OUTPUT_FORMAT in ['json', 'both']:
                output_path = os.path.join(args.output_dir, f"{video_id}_crosswavelet_data.json")
                
                output_data = {
                    'video_id': video_id,
                    'crosswavelet_pairs': cwt_results,
                    'data_types': sorted({t for pair in base_pairs for t in pair}),
                    'config': {
                        'mother_wavelet': MOTHER_WAVELET,
                        'omega0': OMEGA0 if MOTHER_WAVELET.lower() == 'morlet' else None,
                        'dj': DJ,
                        's0_factor': S0_FACTOR,
                        'significance_level': SIGNIFICANCE_LEVEL,
                        'high_coherence_threshold': HIGH_COHERENCE_THRESHOLD,
                        'detrend': DETREND_DATA,
                        'edge_taper': EDGE_TAPER
                    },
                    'provenance': _payload_provenance(config),
        'processing_info': {
                        'pairs_computed': len(cwt_results),
                        'coi_excluded_from_stats': COI_EXCLUDE,
                        'visualization_resolution': f"{MAX_TIME_POINTS_VIZ}x{MAX_FREQ_POINTS_VIZ}"
                    }
                }
                
                output_data['precision'] = precision_note()
                # Merge rather than clobber: this file is keyed by video, so a
                # second analysis writing pairs into it must survive a re-run.
                # write_payload uses compact separators -- the whitespace of
                # indent=2 is a quarter of the file and nobody reads it by eye.
                kept = _results.write_payload(output_path, round_payload(output_data))

                print(f"\nSaved cross-wavelet data to {output_path}")
            for key, names in kept.get('kept', {}).items():
                print(f"  kept {len(names)} existing {key} entr"
                      f"{'y' if len(names) == 1 else 'ies'} from another "
                      f"analysis: {', '.join(names)}")
            for key, names in kept.get('replaced', {}).items():
                print(f"  replaced {len(names)} existing {key} entr"
                      f"{'y' if len(names) == 1 else 'ies'}: {', '.join(names)}")
            
            if OUTPUT_FORMAT in ['npz', 'both']:
                # Save as compressed NumPy format for easier loading in Python
                output_path_npz = os.path.join(args.output_dir, f"{video_id}_crosswavelet_data.npz")
                np.savez_compressed(output_path_npz, **cwt_results)
                print(f"Saved cross-wavelet data to {output_path_npz}")
            
            # Print summary
            if VERBOSE:
                print("\nSummary of Cross-Wavelet Analysis:")
                for pair_key, result in cwt_results.items():
                    stats = result['statistics']
                    print(f"\n  {pair_key}:")
                    print(f"    - Max coherence: {stats['max_coherence']:.3f}")
                    print(f"    - Mean coherence: {stats['mean_coherence']:.3f}")
                    print(f"    - High coherence fraction: {stats['high_coherence_fraction']*100:.1f}%")
                    print(f"    - Time points: {len(result['visualization']['time'])}")
                    print(f"    - Frequency bins: {len(result['visualization']['freqs'])}")
                    print(f"    - AR1 coefficients: α₁={result['alpha1']:.3f}, α₂={result['alpha2']:.3f}")
    
    print("\nCross-wavelet processing complete!")
    
    if not VERBOSE:
        print("\nNote: Run with --verbose flag for detailed output")
    print("Note: Install required packages with:")
    print("  pip install pycwt numpy pandas scipy")

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
    id = "crosswavelet"
    config_key = "include_crosswavelet"
    output_dir = "assets/crosswavelet"
    output_name = "{video_id}_crosswavelet_data.json"
    description = "Cross-wavelet transform and coherence, with an AR(1) coherence null"

    def run(self, config, ctx):
        import os as _os
        import sys as _sys
        cwd = _os.getcwd()
        argv = _sys.argv[:]
        try:
            _os.chdir(ctx.project_dir)
            _sys.argv = ["crosswavelet", "--config", "config.json",
                         "--output-dir", ctx.output_path(self, "_").rsplit(_os.sep, 1)[0]]
            main()
        finally:
            _sys.argv = argv
            _os.chdir(cwd)
