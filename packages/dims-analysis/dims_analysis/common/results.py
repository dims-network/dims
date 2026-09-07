"""Writing a step's browser payload without destroying a neighbour's.

A study's output file is keyed by video, not by analysis: `{video}_rqa_data.json`
holds *every* RQA result for that video, whatever produced it. ORTHO runs the
shared RQA over its kinematic channels and a study-owned categorical RQA over
its gaze channels, and both land in the same file under the same `rqa_data` key.

The shared step used to `json.dump` the whole file, so re-running it deleted the
categorical results. That is not hypothetical: it is why a fork once maintained
its own copy of an entire step. `StepContext.write_result` was written to merge
and fixes exactly this — but no shipped step called it, so the behaviour existed
only in a docstring and a test.

The merge is one level deep, because that is where the payload is keyed by data
type or pair. A top-level merge alone would preserve `rqa_data` as a key and
still replace everything in it.

The trade-off, stated plainly: entries are preserved, never removed. Dropping a
data type from `include_RQA` leaves its old result in the file. Delete the file
to start clean — that is the recovery, and it is cheaper than the alternative,
which is silently losing an analysis somebody else produced.
"""
from __future__ import annotations

import json
import os


def merge_payload(existing: dict, payload: dict) -> dict:
    """New values win, except that dicts are merged one level deep."""
    out = dict(existing)
    for key, value in payload.items():
        prior = out.get(key)
        if isinstance(value, dict) and isinstance(prior, dict):
            merged = dict(prior)
            merged.update(value)
            out[key] = merged
        else:
            out[key] = value
    return out


def read_existing(path: str) -> dict:
    """Whatever is already at `path`, or {} — an unreadable file is replaced."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as fh:
            existing = json.load(fh)
    except (OSError, ValueError):
        return {}
    return existing if isinstance(existing, dict) else {}


def compare_entries(existing: dict, payload: dict) -> dict:
    """What this write kept and what it overwrote, per merged key.

    Both halves are worth saying out loud. A merge that silently keeps stale
    results is the mirror of the bug it prevents; and an entry that is silently
    REPLACED is how ORTHO lost its categorical gaze RQA -- two analyses claimed
    the same data types and the last one to run won without comment.
    """
    kept: dict = {}
    replaced: dict = {}
    for key, value in payload.items():
        prior = existing.get(key)
        if not (isinstance(value, dict) and isinstance(prior, dict)):
            continue
        extra = sorted(k for k in prior if k not in value)
        over = sorted(k for k in prior if k in value)
        if extra:
            kept[key] = extra
        if over:
            replaced[key] = over
    return {"kept": kept, "replaced": replaced}


def write_payload(path: str, payload: dict, compact: bool = True) -> dict:
    """Merge `payload` into whatever is at `path` and write it back.

    Returns {"kept": ..., "replaced": ...} so the caller can report both.
    """
    existing = read_existing(path)
    report = compare_entries(existing, payload)
    merged = merge_payload(existing, payload)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as fh:
        if compact:
            # The whitespace of indent=2 is a quarter of the file and nobody
            # reads these by eye.
            json.dump(merged, fh, separators=(",", ":"))
        else:
            json.dump(merged, fh, indent=2)
    return report
