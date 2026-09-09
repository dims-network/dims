"""Is this coherence field measuring coupling, or measuring power?

This is the check that would have caught the defect that shipped to five
repositories for months. It was not a crash: the field looked plausible and was
wrong, so only numbers find it.

The defect smoothed the magnitude of the cross-spectrum instead of the complex
cross-spectrum, destroying the phase cancellation that coherence *is*. The
result tracked signal power. Three fingerprints, all checked below:

  * cells pinned at exactly 1.0, hidden behind a clamp
  * a strong correlation between coherence and log power
  * independent signals scoring as high as coupled ones
"""
from __future__ import annotations

import json
import os

import numpy as np


def load_crosswavelet(path):
    """Load a cross-wavelet result. Prefers the full-resolution file.

    `{video}_crosswavelet_data.json` is the browser payload and is reduced;
    analysing from it means analysing a sixth of the data. `_full.json` beside
    it is the analysis, in the **same schema** with the same field names, so
    the reading code below is the same for both -- only the time axis differs.

    That is the point of the format change this replaced: the full-resolution
    artifact used to be an `.npz`, a second format with its own member naming,
    so a reader had two code paths and the reduced one was easy to reach by
    accident.
    """
    full = (path[:-len("_data.json")] + "_full.json"
            if path.endswith("_data.json") else None)
    if full and os.path.exists(full):
        path, label = full, "full resolution"
    else:
        label = "reduced for the browser"

    with open(path) as fh:
        d = json.load(fh)
    out = {}
    for name, pair in (d.get("crosswavelet_pairs") or {}).items():
        v = pair["visualization"]
        out[name] = {
            "coherence": _array(v["coherence"]),
            "power": _array(v["power"]),
            "period": _array(v["period"]),
            "time": _array(v["time"]),
            "coi": _array(v["coi"]),
            "signif_xwt": _array(v.get("signif_xwt")),
            "sig95_wtc": _array(v.get("sig95_wtc")),
        }
    return out, label


def _array(field):
    """A payload field as a float array, whatever encoding it arrived in.

    Large grids travel base64-encoded, short axes as plain lists with `null`
    for an undefined value -- `json.dump` writes a bare `NaN`, which
    `JSON.parse` rejects outright. Both become NaN here.
    """
    if field is None:
        return None
    if isinstance(field, dict) and "encoding" in field:
        try:
            from dims_analysis.common import arrays
        except ImportError as exc:  # pragma: no cover - stated, not guessed
            raise ImportError(
                "this payload carries base64 arrays; install dims-analysis to "
                "read them (pip install -e dims/packages/dims-analysis)") from exc
        return np.asarray(arrays.unpack(field), dtype=float)
    flat = np.asarray(field, dtype=object)
    return np.asarray(np.where(flat == None, np.nan, flat).tolist(),  # noqa: E711
                      dtype=float)


def coherence_report(pair):
    """Diagnose one pair's coherence field. `pair` as returned by load_crosswavelet."""
    coh = np.asarray(pair["coherence"], dtype=float)
    power = np.asarray(pair["power"], dtype=float)
    finite = np.isfinite(coh)

    saturated = float(np.mean(np.isclose(coh[finite], 1.0, atol=1e-9))) if finite.any() else float("nan")

    with np.errstate(divide="ignore", invalid="ignore"):
        logp = np.log(np.abs(power) + 1e-30)
    both = finite & np.isfinite(logp)
    r_power = float(np.corrcoef(coh[both].ravel(), logp[both].ravel())[0, 1]) if both.sum() > 2 else float("nan")

    report = {
        "mean_coherence": float(np.nanmean(coh)),
        "max_coherence": float(np.nanmax(coh)),
        "saturated_at_1": saturated,
        "corr_with_log_power": r_power,
        "warnings": [],
    }

    null = pair.get("sig95_wtc")
    if null is not None and np.isfinite(np.asarray(null, dtype=float)).any():
        null = np.asarray(null, dtype=float)[:, None]
        usable = finite & np.isfinite(null)
        if usable.any():
            report["significant_fraction"] = float(np.sum((coh > null) & usable) / np.sum(usable))
            report["null_level_median"] = float(np.nanmedian(null))
    else:
        report["warnings"].append(
            "no sig95_wtc: without an AR(1) null an individual coherence value cannot be "
            "read at all — under independence coherence sits near 0.25, not 0")

    if saturated > 0.01:
        report["warnings"].append(
            f"{saturated:.1%} of cells sit at exactly 1.0. A correct coherence does not "
            f"saturate; this is the fingerprint of the pre-2026 defect, and these results "
            f"should be recomputed")
    if np.isfinite(r_power) and r_power > 0.5:
        report["warnings"].append(
            f"coherence correlates {r_power:.2f} with log power. Coherence should be "
            f"largely independent of amplitude; a strong correlation means it is "
            f"measuring how loud the signals are, not whether they are coupled")

    frac = report.get("significant_fraction")
    if frac is not None and frac < 0.08:
        report["warnings"].append(
            f"only {frac:.1%} of usable cells beat the null. Under independence that "
            f"number is 0.05 by construction, so this pair shows no detectable coupling "
            f"— whatever the mean coherence looks like")

    return report


def study_coherence_report(project_dir="."):
    """Run coherence_report over every cross-wavelet result a study has."""
    import glob
    out = []
    for path in sorted(glob.glob(os.path.join(project_dir, "assets/crosswavelet/*_data.json"))):
        try:
            pairs, source = load_crosswavelet(path)
        except Exception as exc:  # noqa: BLE001
            out.append({"file": os.path.basename(path), "error": str(exc)})
            continue
        for name, pair in pairs.items():
            r = coherence_report(pair)
            r["file"] = os.path.basename(path)
            r["pair"] = name
            r["source"] = source
            out.append(r)
    return out
