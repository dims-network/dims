"""Large arrays inside a JSON payload, so a study ships one file format.

A study used to ship two artifacts per analysis: a JSON payload for the browser
and an `.npz` beside it "for analysis". Measured file by file, the second one
mostly held nothing the first did not:

    RQA     time + signal, byte-identical to the source CSV after the
            documented cleaning, and windowed metrics that are exact
            duplicates of the JSON's                        -> redundant
    cRQA    the prepared signals on the common grid; metrics duplicated
                                                            -> nearly redundant
    cwt     coherence, power and phase at 6x the time resolution
                                                            -> the real thing

And the assets contract told readers "Analyse from the `.npz`" -- pointing them,
for RQA, at the file holding *less*. So there is one format now, and where a
second resolution genuinely exists it is a second JSON with the same schema.

That only works if JSON can carry a megabyte of numbers without becoming
absurd, which is what this module is for. Two encodings, each naming itself:

    {"encoding": "bitmap-b64", "rows": 500, "cols": 500, "data": "..."}
    {"encoding": "f32-b64",    "shape": [128, 504],      "data": "..."}

The `encoding` field is the point of the design. A reader that meets an
encoding it does not know says so; a format that changed silently is how a tab
ends up drawing an empty panel with nothing in the log.

**Why a bitmap rather than the index pairs used before.** A recurrence matrix is
binary, and `[[row, col], ...]` costs about ten bytes per recurrent cell while a
bitmap costs one bit per cell whatever the density. Measured on one ORTHO gaze
matrix: **7,300,452 bytes as pairs against 133,803 as a bitmap, 54.6x**. Sparse
only wins below about 1.2 % density; RQA targets 7 % and ORTHO's gaze channels
run 63-89 %. It is also less code in the browser, because `rqa.js` and
`crqa.js` were each rebuilding a dense matrix from the pairs by hand -- Plotly
wants dense either way.

Everything is little-endian, stated rather than inherited: `numpy` follows the
platform and `DataView` in the browser defaults to big.
"""
from __future__ import annotations

import base64

import numpy as np

#: Bumped when an encoding changes shape in a way an old reader would
#: misinterpret rather than reject. A reader compares this against what it
#: knows and says so plainly if it is newer.
PAYLOAD_VERSION = 2

BITMAP = "bitmap-b64"
FLOAT32 = "f32-b64"


def pack_bitmap(matrix) -> dict:
    """A binary matrix as one bit per cell, row-major.

    Bits are packed most-significant-first within each byte, and each **row**
    starts on a byte boundary. Padding within a row would be cheaper by a few
    bytes and would make the browser's index arithmetic depend on the row
    width; this way a cell is `byte(row * stride + col >> 3)`, which is what
    the decoder does.
    """
    m = np.asarray(matrix)
    if m.ndim != 2:
        raise ValueError(f"a bitmap needs a 2-D matrix, got shape {m.shape}")
    bits = (m != 0).astype(np.uint8)
    packed = np.packbits(bits, axis=1, bitorder="big")
    return {
        "encoding": BITMAP,
        "rows": int(m.shape[0]),
        "cols": int(m.shape[1]),
        "data": base64.b64encode(packed.tobytes()).decode("ascii"),
    }


def unpack_bitmap(obj) -> np.ndarray:
    """The matrix back, as uint8 zeros and ones."""
    _expect(obj, BITMAP)
    rows, cols = int(obj["rows"]), int(obj["cols"])
    raw = np.frombuffer(base64.b64decode(obj["data"]), dtype=np.uint8)
    stride = (cols + 7) // 8
    if raw.size != rows * stride:
        raise ValueError(
            f"a {rows}x{cols} bitmap needs {rows * stride} bytes, got {raw.size}")
    bits = np.unpackbits(raw.reshape(rows, stride), axis=1, bitorder="big")
    return bits[:, :cols].copy()


def pack_f32(array) -> dict:
    """A float array as little-endian float32.

    float32 carries about seven significant figures, which is more than the six
    the JSON payload has ever claimed and far more than a heatmap can show. NaN
    survives the round trip and means the same thing it means in the analysis:
    this cell has no value -- outside the cone of influence, or a band where
    neither signal has power. The browser decoder turns it into `null`, which
    is what Plotly reads as a gap.
    """
    a = np.asarray(array, dtype="<f4")
    return {
        "encoding": FLOAT32,
        "shape": [int(n) for n in a.shape],
        "data": base64.b64encode(a.tobytes()).decode("ascii"),
    }


def unpack_f32(obj) -> np.ndarray:
    _expect(obj, FLOAT32)
    shape = tuple(int(n) for n in obj["shape"])
    raw = np.frombuffer(base64.b64decode(obj["data"]), dtype="<f4")
    expected = int(np.prod(shape)) if shape else 1
    if raw.size != expected:
        raise ValueError(
            f"shape {shape} needs {expected} float32 values, got {raw.size}")
    return raw.reshape(shape).copy()


def is_packed(obj) -> bool:
    return isinstance(obj, dict) and obj.get("encoding") in (BITMAP, FLOAT32)


def unpack(obj):
    """Whichever encoding it is; anything else passes through untouched.

    So a reader can walk a payload without knowing in advance which fields grew
    large enough to be encoded.
    """
    if not isinstance(obj, dict):
        return obj
    encoding = obj.get("encoding")
    if encoding == BITMAP:
        return unpack_bitmap(obj)
    if encoding == FLOAT32:
        return unpack_f32(obj)
    return obj


def _expect(obj, encoding: str) -> None:
    if not isinstance(obj, dict) or "encoding" not in obj:
        raise ValueError(
            f"expected a {encoding} object with an 'encoding' field, got "
            f"{type(obj).__name__}")
    if obj["encoding"] != encoding:
        raise ValueError(
            f"expected encoding {encoding!r}, found {obj['encoding']!r}. If "
            f"this is a newer payload, this reader is older than the file.")


def nan_to_none(values):
    """A plain nested list with NaN as `None`, for the small fields left as JSON.

    `json.dump` writes a bare `NaN` token, which `JSON.parse` rejects outright,
    so one undefined cell makes a whole study's payload unreadable in the
    browser. The large fields go through `pack_f32` and never meet this; the
    short ones -- a period axis, a cone of influence -- stay human-readable and
    come through here.
    """
    a = np.asarray(values, dtype=float)
    if a.ndim == 0:
        return None if not np.isfinite(a) else float(a)
    out = a.tolist()

    def clean(x):
        if isinstance(x, list):
            return [clean(v) for v in x]
        return None if x is None or not np.isfinite(x) else float(x)

    return clean(out)
