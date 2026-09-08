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


#: The key every payload stamps its encoding with. When it changes, an entry
#: nothing rewrote is an entry no reader can read.
VERSION_KEY = "payload_version"


class UnversionedPayload(Exception):
    """A step wrote a payload with no `payload_version` into a file that has one."""


def check_version(existing: dict, payload: dict, path: str = "") -> None:
    """Refuse to merge an unstamped payload into a stamped file.

    The sharp edge this removes: a study-owned step written before versioning
    existed writes `{"video_id": ..., "rqa_data": {...}}` into the same file as
    the shared step. Its payload declares no version, the file on disk declares
    2, and the rule below would then treat every entry already there as stale
    and drop it -- turning one forgotten field into the silent loss of another
    analysis, which is the exact failure merging was introduced to prevent.

    So it raises instead, naming the field and the file. Loud and one line to
    fix beats quiet and unrecoverable.
    """
    if VERSION_KEY in payload or VERSION_KEY not in existing:
        return
    where = f" at {path}" if path else ""
    raise UnversionedPayload(
        f"this payload carries no {VERSION_KEY!r}, and the file it is being "
        f"merged into{where} is version {existing[VERSION_KEY]}. Refusing to "
        f"write, because merging them would drop every entry already there -- "
        f"including analyses this step did not produce. Add "
        f'"{VERSION_KEY}": arrays.PAYLOAD_VERSION to the payload; see '
        f"docs/contracts/analysis-output.md, A3.")


def same_version(existing: dict, payload: dict) -> bool:
    """Whether the two files are in the same format.

    A file with no version at all predates versioning, so it is only "the same"
    as another file with no version.
    """
    return existing.get(VERSION_KEY) == payload.get(VERSION_KEY)


def merge_payload(existing: dict, payload: dict) -> dict:
    """New values win, except that dicts are merged one level deep.

    **Nothing is merged across a format change.** Preserving entries no
    incoming run rewrote is the whole point of this function -- it is why
    ORTHO's study-owned categorical gaze RQA survives a run of the shared RQA
    step -- but when `payload_version` moves, those entries are in an encoding
    the new reader does not speak, and keeping them produces a file whose
    stated version describes only half of itself.

    Found by rebuilding ORTHO at 2.0.0: four of twelve recordings kept v1
    `sparse_matrix` entries, for gaze channels whose source CSV had gone
    missing, inside files stamped v2 beside v2 bitmaps. A tab reading those
    entries finds nothing and draws an empty panel, which is precisely the
    failure this release exists to make impossible.
    """
    if not same_version(existing, payload):
        return dict(payload)
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
    stale: dict = {}
    fresh = same_version(existing, payload)
    for key, value in payload.items():
        prior = existing.get(key)
        if not (isinstance(value, dict) and isinstance(prior, dict)):
            continue
        extra = sorted(k for k in prior if k not in value)
        over = sorted(k for k in prior if k in value)
        if extra:
            (kept if fresh else stale)[key] = extra
        if over:
            replaced[key] = over
    return {"kept": kept, "replaced": replaced, "stale": stale}


def write_payload(path: str, payload: dict, compact: bool = True) -> dict:
    """Merge `payload` into whatever is at `path` and write it back.

    Returns {"kept": ..., "replaced": ...} so the caller can report both.
    """
    existing = read_existing(path)
    check_version(existing, payload, path)
    report = compare_entries(existing, payload)
    for key, names in report.get("stale", {}).items():
        print(f"  dropped {len(names)} {key} entr"
              f"{'y' if len(names) == 1 else 'ies'} written by an older payload "
              f"format, which this run did not rebuild: {', '.join(names)}")
        print(f"       their source data is missing or their analysis did not "
              f"run; rebuild them or they are gone from this study.")
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
