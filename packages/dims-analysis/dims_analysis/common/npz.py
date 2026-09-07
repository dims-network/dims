"""The full-resolution artifact beside the browser payload.

The JSON a study ships is a picture: reduced for a page to draw and rounded to
six significant figures. This is the analysis. `docs/contracts/assets.md` calls
them two artifacts, not one.

What goes in depends on the analysis, and the difference is not stylistic. A
cross-wavelet result is linear in the recording: 99 scales by 6000 samples is a
few megabytes and the whole field is worth keeping. A recurrence matrix is
quadratic: the full Karnatak recording is 58700 points, which is 3.4 billion
cells, and the step already builds that in RAM with no cap. So the recurrence
steps store what is both bounded and actually wanted downstream -- the windowed
metrics at full resolution, the prepared signal, the threshold and the embedding
-- from which the matrix is one line of cdist away, at whatever resolution the
reader can afford.

One file per video, with a group of arrays per data type or pair. Groups are
appended as zip members: the obvious implementation -- load everything, add one
group, recompress -- is quadratic, and a fifteen-pair study paid it fifteen
times.
"""
from __future__ import annotations

import os
import zipfile

import numpy as np
from numpy.lib import format as _npformat


def add_group(path: str, prefix: str, arrays: dict) -> str:
    """Write `arrays` into `path` under `prefix/`, keeping what is already there."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    named = {f"{prefix.replace('/', '_')}/{k}": np.asarray(v) for k, v in arrays.items()}
    if not _append(path, named):
        _rebuild(path, named)
    return path


def _append(path: str, named: dict) -> bool:
    """Add members to the archive. False if a name collides or it is unreadable.

    A collision means the same group is being written twice -- a re-run. Two zip
    members with one name produce an archive that loads and quietly serves the
    stale one, so the caller rebuilds instead.
    """
    members = {f"{name}.npy": arr for name, arr in named.items()}
    if os.path.exists(path):
        try:
            with zipfile.ZipFile(path) as zf:
                if set(zf.namelist()) & set(members):
                    return False
        except (zipfile.BadZipFile, OSError):
            return False
    mode = "a" if os.path.exists(path) else "w"
    try:
        with zipfile.ZipFile(path, mode=mode, compression=zipfile.ZIP_DEFLATED,
                             allowZip64=True) as zf:
            for member, arr in members.items():
                with zf.open(member, "w", force_zip64=True) as fh:
                    _npformat.write_array(fh, arr, allow_pickle=False)
    except (zipfile.BadZipFile, OSError):
        return False
    return True


def _rebuild(path: str, named: dict) -> None:
    existing: dict = {}
    if os.path.exists(path):
        try:
            with np.load(path, allow_pickle=False) as z:
                existing = {k: z[k] for k in z.files}
        except Exception:  # noqa: BLE001 - a corrupt archive is replaced
            existing = {}
    existing.update(named)
    np.savez_compressed(path, **existing)
