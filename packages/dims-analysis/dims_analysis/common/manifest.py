"""What a study's assets are, recorded where the assets themselves cannot go.

A private study keeps its data outside git, so a clone contains an empty
`assets/` and nothing in the repository says what belongs there. That is fine
until someone rebuilds from raw data and wants to know whether the rebuild
produced everything -- at which point the only available answer is "the files
that are on this machine", which is not an answer.

`assets/MANIFEST.json` is the tracked record: names, sizes and checksums, never
content. It is what the commit hook and the CI guard already exempt by name,
and it is the reason they can: a manifest carries no identifiable material.
It is equally useful in a public study, where it catches a half-finished run
that a green exit code hid.

Checking is two-speed on purpose. Names and sizes catch a missing or truncated
file and cost one `stat` each; checksums catch a corrupted or stale one and
cost a full read, which on a study with video is minutes. The cheap check is
the default so that it actually gets run.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

from dims_analysis.common import assets

NAME = 'MANIFEST.json'
_SKIP_NAMES = {NAME, '.gitkeep', '.DS_Store'}
_CHUNK = 1 << 20


def _digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        while True:
            block = fh.read(_CHUNK)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _root(project_dir='.'):
    """Where the asset files actually are, external root included."""
    return assets.assets_root(project_dir) or os.path.join(project_dir, 'assets')


def scan(project_dir='.', deep=True):
    """Every asset file, keyed by its path relative to the assets root."""
    root = _root(project_dir)
    found = {}
    if not os.path.isdir(root):
        return found
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith('.'))
        for name in sorted(filenames):
            if name in _SKIP_NAMES or name.startswith('.'):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, '/')
            entry = {'bytes': os.path.getsize(full)}
            if deep:
                entry['sha256'] = _digest(full)
            found[rel] = entry
    return found


def path_for(project_dir='.'):
    """The manifest is tracked, so it lives in the repository, not the root."""
    return os.path.join(project_dir, 'assets', NAME)


def load(project_dir='.'):
    try:
        with open(path_for(project_dir)) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def write(project_dir='.', deep=True):
    """Record the assets as they are now. Returns the manifest."""
    manifest = {
        'generated': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        # Not the path: that is a local detail, and on a private study it
        # tends to name a person's home directory.
        'assetsExternal': assets.assets_root(project_dir) is not None,
        'checksums': deep,
        'files': scan(project_dir, deep=deep),
    }
    target = path_for(project_dir)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, 'w') as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write('\n')
    return manifest


def compare(project_dir='.', deep=False):
    """Differences between the recorded manifest and what is on disk.

    Returns ``(missing, changed, extra)``. `deep` compares checksums, and only
    for entries that have one -- a manifest written without them cannot grow
    them retroactively, and saying "changed" for every file would be a lie.
    """
    manifest = load(project_dir)
    if manifest is None:
        return None
    recorded = manifest.get('files') or {}
    actual = scan(project_dir, deep=deep and manifest.get('checksums', False))

    missing = sorted(set(recorded) - set(actual))
    extra = sorted(set(actual) - set(recorded))
    changed = []
    for rel in sorted(set(recorded) & set(actual)):
        want, have = recorded[rel], actual[rel]
        if want.get('bytes') != have.get('bytes'):
            changed.append(rel)
        elif deep and want.get('sha256') and have.get('sha256') \
                and want['sha256'] != have['sha256']:
            changed.append(rel)
    return missing, changed, extra
