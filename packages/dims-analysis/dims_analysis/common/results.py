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

**A step may remove its own entries, and only its own.** Preserving everything
was indiscriminate, and it had a cost of its own: a study that dropped a pair
from `include_crosswavelet` — or removed the person a measure was placed on —
kept computing nothing for it while the file kept the old answer, and the
dashboard drew it. Measured on the `test` study: `include_crosswavelet` asked
for four pairs, `processing_info.pairs_computed` said four, and the file held
seven. Two of the three extras mentioned a series no effector declared any
more, which the network tab rendered as a whole extra person.

So each entry records the step that wrote it, in `entry_owners`, and an entry
absent from an incoming run is dropped **when that run's owner is the one that
wrote it**. An entry belonging to another step survives, which is the ORTHO
guarantee above; an entry with no owner recorded survives too, because a file
written before this bookkeeping existed cannot be second-guessed — it is
reported instead, and `dims-analysis prune` is how a study clears those.
"""
from __future__ import annotations

import json
import os


#: The key every payload stamps its encoding with. When it changes, an entry
#: nothing rewrote is an entry no reader can read.
VERSION_KEY = "payload_version"

#: Which step wrote each entry: {payload key: {entry name: owner}}. Bookkeeping
#: rather than data, and additive — `payloadProblem` on the browser side gates
#: on VERSION_KEY alone and never inspects top-level keys, so an older
#: dashboard reads a file carrying this one without noticing it.
#:
#: Kept beside the payload and rebuilt on every write, never merged as part of
#: it: `merge_payload` replaces a nested dict wholesale, so carrying this one
#: through that path would drop another step's stamps -- the bookkeeping would
#: have the very bug it exists to prevent.
OWNERS_KEY = "entry_owners"


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


def owners_of(existing: dict) -> dict:
    """The ownership map already in a file, or {}."""
    owners = existing.get(OWNERS_KEY)
    return owners if isinstance(owners, dict) else {}


def _owned(payload: dict, expected: dict | None) -> dict:
    """The keys of `payload` this write speaks for, and what is asked of each.

    `expected` is {payload key: the entry names the config asks for}. Its keys
    are the scope of everything below, and that scoping is load-bearing rather
    than tidiness: a cross-wavelet payload's top level also carries `config`,
    `provenance`, `processing_info` and `precision`, every field of which the
    output contract documents. Treating "every dict at the top level" as
    entries stamped each of those and then *pruned* them -- `provenance` drops
    its `None` fields, so a run with one optional field unset deleted a key a
    previous run had recorded.
    """
    if not isinstance(expected, dict):
        return {}
    return {key: set(names or ()) for key, names in expected.items()
            if isinstance(payload.get(key), dict)}


def stale_own_entries(existing: dict, payload: dict, owner: str | None,
                      expected: dict | None = None) -> dict:
    """What `owner` wrote before, is not writing now, and is not asked for.

    The whole of the new behaviour is this predicate, and it is deliberately
    narrow. Four things must all hold before an entry goes: the incoming run
    names an owner, it says which keys hold its entries, the file records that
    same owner against the entry, and the config no longer asks for it.

    The last condition is the one that is easy to leave out and expensive to
    get wrong. "Absent from this run's output" is not the same as "no longer
    wanted": a step skips an entry whose source CSV is unreadable and carries
    on with a warning, so pruning on absence alone would delete a good and
    expensive result because somebody renamed a file. Absent *and* undeclared
    is the config having changed its mind, which is the thing being fixed.

    Nothing is computed across a format change, because `merge_payload` keeps
    nothing across one either -- those entries are reported as `stale` and go
    for a different and older reason.
    """
    out: dict = {}
    if not owner or not same_version(existing, payload):
        return out
    owners = owners_of(existing)
    for key, asked in _owned(payload, expected).items():
        prior = existing.get(key)
        stamped = owners.get(key)
        if not isinstance(prior, dict) or not isinstance(stamped, dict):
            continue
        value = payload[key]
        gone = sorted(name for name in prior
                      if name not in value and name not in asked
                      and stamped.get(name) == owner)
        if gone:
            out[key] = gone
    return out


def next_owners(existing: dict, payload: dict, owner: str | None,
                merged: dict, expected: dict | None = None) -> dict:
    """The ownership map for the file about to be written.

    Three rules, in order, and all of them inside the keys `expected` names.
    What this run wrote is owned by this run's owner. What a *nameless* run
    rewrote loses its stamp, because the entry is no longer the work of the
    step recorded against it and claiming otherwise would let one step's prune
    delete another's output. And an entry that is no longer in the file is no
    longer in the map -- stale bookkeeping about a pair nobody holds is how
    this kind of index rots.
    """
    out: dict = {}
    if same_version(existing, payload):
        for key, names in owners_of(existing).items():
            if isinstance(names, dict):
                out[key] = dict(names)

    for key in _owned(payload, expected):
        value = payload[key]
        if owner:
            out.setdefault(key, {}).update({name: owner for name in value})
        elif key in out:
            for name in value:
                out[key].pop(name, None)

    for key in list(out):
        body = merged.get(key)
        if not isinstance(body, dict):
            del out[key]
            continue
        out[key] = {n: o for n, o in out[key].items() if n in body}
        if not out[key]:
            del out[key]
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


def compare_entries(existing: dict, payload: dict, owner: str | None = None,
                    expected: dict | None = None) -> dict:
    """What this write kept, overwrote and removed, per merged key.

    Every half is worth saying out loud. A merge that silently keeps stale
    results is the mirror of the bug it prevents; an entry that is silently
    REPLACED is how ORTHO lost its categorical gaze RQA -- two analyses claimed
    the same data types and the last one to run won without comment; and an
    entry silently *removed* would be the same failure again, so a prune says
    which entries it took and whose they were.

    `kept` means kept and not claimed by this run's owner, which is the honest
    reading: with no owner passed it is every entry this run did not rewrite,
    exactly as before, and with one it excludes the entries being pruned.
    """
    kept: dict = {}
    replaced: dict = {}
    stale: dict = {}
    fresh = same_version(existing, payload)
    pruned = stale_own_entries(existing, payload, owner, expected)
    for key, value in payload.items():
        prior = existing.get(key)
        if not (isinstance(value, dict) and isinstance(prior, dict)):
            continue
        dropping = set(pruned.get(key, ()))
        extra = sorted(k for k in prior if k not in value and k not in dropping)
        over = sorted(k for k in prior if k in value)
        if extra:
            (kept if fresh else stale)[key] = extra
        if over:
            replaced[key] = over
    return {"kept": kept, "replaced": replaced, "stale": stale, "pruned": pruned}


def write_payload(path: str, payload: dict, compact: bool = True,
                  owner: str | None = None,
                  expected: dict | None = None) -> dict:
    """Merge `payload` into whatever is at `path` and write it back.

    `owner` is the id of the step doing the writing and `expected` is
    {payload key: the entry names its config asks for} -- `Step.expected_
    entries`. Both together are what let this write remove the entries that
    step wrote before and nothing asks for any more; with either missing every
    entry is kept, as this function always did.

    One assumption, because the design rests on it: **a step writes all of its
    entries for a file in a single call.** The shipped steps do, writing once
    per video after their loop over data types or pairs. A step that wrote once
    per pair would, on its second call, find its own first entry absent from
    the incoming payload and prune the work it had just done.

    Returns {"kept": ..., "replaced": ..., "pruned": ...} so the caller can
    report all of it.
    """
    existing = read_existing(path)
    check_version(existing, payload, path)
    report = compare_entries(existing, payload, owner, expected)
    for key, names in report.get("stale", {}).items():
        print(f"  dropped {len(names)} {key} entr"
              f"{'y' if len(names) == 1 else 'ies'} written by an older payload "
              f"format, which this run did not rebuild: {', '.join(names)}")
        print(f"       their source data is missing or their analysis did not "
              f"run; rebuild them or they are gone from this study.")
    merged = merge_payload(existing, payload)
    for key, names in report.get("pruned", {}).items():
        for name in names:
            merged.get(key, {}).pop(name, None)
    owners = next_owners(existing, payload, owner, merged, expected)
    if owners:
        merged[OWNERS_KEY] = owners
    else:
        merged.pop(OWNERS_KEY, None)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as fh:
        if compact:
            # The whitespace of indent=2 is a quarter of the file and nobody
            # reads these by eye.
            json.dump(merged, fh, separators=(",", ":"))
        else:
            json.dump(merged, fh, indent=2)
    return report
