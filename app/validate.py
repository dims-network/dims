"""Validators that mirror what the template's js/app.js actually requires.

Each file validator returns a list of issue dicts: {"level": "error"|"warning",
"message": str}. An empty list means the file is valid. Errors block the build;
warnings are surfaced but non-blocking.
"""
import csv
import json
import os
import xml.etree.ElementTree as ET


def _err(msg):
    return {"level": "error", "message": msg}


def _warn(msg):
    return {"level": "warning", "message": msg}


def validate_csv(path: str) -> list:
    """Time-series CSV: must have a `Time` column + at least one measurement column.

    Mirrors js/app.js (~1339-1405): PapaParse with headers, requires `Time` plus
    one or more numeric measurement columns.
    """
    issues = []
    try:
        with open(path, newline="") as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration:
                return [_err("CSV is empty (no header row).")]
            cols = [c.strip() for c in header]
            if "Time" not in cols:
                issues.append(_err("CSV must contain a 'Time' column (case-sensitive)."))
            measurement_cols = [c for c in cols if c and c != "Time"]
            if not measurement_cols:
                issues.append(_err("CSV must contain at least one measurement column besides 'Time'."))
            # at least one data row?
            if next(reader, None) is None:
                issues.append(_err("CSV has a header but no data rows."))
    except Exception as e:  # noqa: BLE001
        issues.append(_err(f"Could not read CSV: {e}"))
    return issues


def validate_transcript(path: str) -> list:
    """Transcript JSON: { "segments": [ {start, end, speaker, text}, ... ] }.

    Mirrors js/app.js (~1407-1424).
    """
    issues = []
    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [_err(f"Transcript is not valid JSON: {e}")]
    except Exception as e:  # noqa: BLE001
        return [_err(f"Could not read transcript: {e}")]

    segments = data.get("segments") if isinstance(data, dict) else None
    if not isinstance(segments, list):
        return [_err("Transcript must be an object with a 'segments' array.")]
    if not segments:
        return [_warn("Transcript 'segments' array is empty.")]

    required = ("start", "end", "speaker", "text")
    missing_keys = set()
    for i, seg in enumerate(segments[:200]):  # sample to keep it fast
        if not isinstance(seg, dict):
            issues.append(_err(f"Segment {i} is not an object."))
            break
        for k in required:
            if k not in seg:
                missing_keys.add(k)
    if missing_keys:
        issues.append(_err(
            "Each segment needs start, end, speaker, text. Missing: "
            + ", ".join(sorted(missing_keys))
        ))
    return issues


def validate_eaf(path: str) -> list:
    """ELAN .eaf: XML with TIME_SLOT (TIME_VALUE) + TIER>ALIGNABLE_ANNOTATION.

    Mirrors js/app.js (~1753-1794).
    """
    issues = []
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as e:
        return [_err(f".eaf is not valid XML: {e}")]
    except Exception as e:  # noqa: BLE001
        return [_err(f"Could not read .eaf: {e}")]

    time_slots = list(root.iter("TIME_SLOT"))
    if not time_slots:
        issues.append(_err(".eaf has no TIME_SLOT elements."))
    if not any(ts.get("TIME_VALUE") is not None for ts in time_slots):
        issues.append(_err(".eaf TIME_SLOT elements are missing TIME_VALUE."))
    if not list(root.iter("ALIGNABLE_ANNOTATION")):
        issues.append(_err(".eaf has no TIER > ALIGNABLE_ANNOTATION annotations."))
    return issues


# Map asset role -> validator (config/video have no per-file validator here).
FILE_VALIDATORS = {
    "timeseries": validate_csv,
    "transcript": validate_transcript,
    "elan": validate_eaf,
}


def validate_file(role: str, path: str) -> list:
    fn = FILE_VALIDATORS.get(role)
    if fn is None:
        return []
    if not os.path.exists(path):
        return [_err(f"File not found: {path}")]
    return fn(path)


def validate_config(cfg: dict, staged: list) -> list:
    """Validate the assembled config against the template's invariants.

    `staged` is a list of dicts like {role, videoID, dataType}. Used to confirm
    that gated analyses point at data types that actually have CSVs.

    Extension point: ORTHO-only keys (trajectory/perspective/dtw) are intentionally
    NOT validated here. Add their checks in this function when v2 supports them.
    """
    issues = []
    video_ids = cfg.get("videoIDs") or []
    data_types = cfg.get("dataTypes") or {}

    if not video_ids:
        issues.append(_err("No sessions defined — add at least one video/session ID."))

    # CSV data types available per video, from staged files.
    csv_types_by_video = {}
    videos_with_mp4 = set()
    for item in staged:
        vid = item.get("videoID")
        if item.get("role") == "timeseries" and vid and item.get("dataType"):
            csv_types_by_video.setdefault(vid, set()).add(item["dataType"])
        if item.get("role") == "video" and vid:
            videos_with_mp4.add(vid)

    for vid in video_ids:
        dts = data_types.get(vid)
        if not dts:
            issues.append(_err(f"Session '{vid}' has no data types — add at least one time-series CSV."))
        if vid not in videos_with_mp4:
            issues.append(_warn(f"Session '{vid}' has no video (.mp4); the dashboard works best with one."))

    # Helper: does (some video) have a CSV for this data type?
    all_csv_types = set().union(*csv_types_by_video.values()) if csv_types_by_video else set()

    for dt in cfg.get("include_RQA") or []:
        if dt not in all_csv_types:
            issues.append(_err(f"RQA is enabled for '{dt}' but no time-series CSV provides it."))

    cw = cfg.get("include_crosswavelet") or []
    for dt in cw:
        if dt not in all_csv_types:
            issues.append(_err(f"Cross-wavelet is enabled for '{dt}' but no time-series CSV provides it."))
    if cw and len(set(cw)) < 2:
        issues.append(_err("Cross-wavelet needs at least 2 data types (it compares pairs)."))

    return issues
