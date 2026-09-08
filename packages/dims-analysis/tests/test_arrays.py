"""Round-tripping the two payload encodings, and refusing what it cannot read.

The encodings replace two things at once -- the `[row, col]` index pairs a
recurrence payload used to carry, and the `.npz` beside it -- so if either
direction is wrong the failure is a blank panel, which is the failure mode this
whole contract exists to remove.
"""
from __future__ import annotations

import numpy as np
import pytest

from dims_analysis.common import arrays


@pytest.mark.parametrize("rows,cols", [(1, 1), (1, 9), (9, 1), (7, 8), (8, 7),
                                       (500, 500), (13, 129)])
@pytest.mark.parametrize("density", [0.0, 0.012, 0.07, 0.69, 1.0])
def test_a_bitmap_round_trips_at_every_shape_and_density(rows, cols, density):
    """Widths that are not multiples of eight are where a packing bug lives:
    the last bits of a row are padding and must not become recurrent cells."""
    rng = np.random.default_rng(rows * 1000 + cols)
    m = (rng.random((rows, cols)) < density).astype(np.uint8)
    back = arrays.unpack_bitmap(arrays.pack_bitmap(m))
    assert back.shape == m.shape
    assert np.array_equal(back, m), (
        f"{rows}x{cols} at density {density}: "
        f"{int(np.sum(back != m))} cells differ")


def test_a_bitmap_is_far_smaller_than_the_index_pairs_it_replaces():
    """Measured on an ORTHO gaze matrix: 7,300,452 bytes as pairs against
    133,803 as a bitmap. This pins the reason the format changed."""
    rng = np.random.default_rng(4)
    m = (rng.random((500, 500)) < 0.69).astype(np.uint8)
    packed = len(arrays.pack_bitmap(m)["data"])
    pairs = len(str([[int(r), int(c)] for r, c in zip(*np.where(m))]))
    assert packed * 20 < pairs, (
        f"bitmap {packed} bytes against {pairs} as index pairs; the whole "
        f"reason for the encoding is that this ratio is large")


@pytest.mark.parametrize("shape", [(4,), (128, 504), (1, 1), (3, 5, 2)])
def test_a_float_grid_round_trips(shape):
    rng = np.random.default_rng(11)
    a = rng.standard_normal(shape) * 1e-8
    back = arrays.unpack_f32(arrays.pack_f32(a))
    assert back.shape == a.shape
    # float32, so seven significant figures -- more than the six the payload
    # has always claimed, and more than a heatmap can show.
    assert np.allclose(back, a, rtol=1e-6)


def test_nan_survives_a_float_round_trip():
    """NaN is a value in these grids: outside the cone of influence, or a band
    where neither signal has power. Losing it to a zero would draw a confident
    result where there is none."""
    a = np.array([[1.0, np.nan], [np.nan, -2.5]])
    back = arrays.unpack_f32(arrays.pack_f32(a))
    assert np.isnan(back[0, 1]) and np.isnan(back[1, 0])
    assert back[0, 0] == 1.0 and back[1, 1] == -2.5


def test_the_encoding_field_makes_a_wrong_reader_say_so():
    """The point of naming the encoding: a reader that meets one it does not
    know refuses, instead of interpreting the bytes as something else."""
    packed = arrays.pack_bitmap(np.ones((4, 4), dtype=np.uint8))
    with pytest.raises(ValueError, match="f32-b64"):
        arrays.unpack_f32(packed)

    future = dict(packed, encoding="bitmap-b128")
    assert arrays.unpack(future) is future, "an unknown encoding must pass through"
    with pytest.raises(ValueError, match="older than the file"):
        arrays.unpack_bitmap(future)


def test_truncated_data_is_caught_rather_than_reshaped():
    packed = arrays.pack_bitmap(np.ones((8, 8), dtype=np.uint8))
    packed["rows"] = 9
    with pytest.raises(ValueError, match="bytes"):
        arrays.unpack_bitmap(packed)


def test_unpack_dispatches_and_leaves_everything_else_alone():
    m = np.array([[1, 0], [0, 1]], dtype=np.uint8)
    assert np.array_equal(arrays.unpack(arrays.pack_bitmap(m)), m)
    assert np.allclose(arrays.unpack(arrays.pack_f32([1.5, 2.5])), [1.5, 2.5])
    for passthrough in ({"a": 1}, [1, 2], "text", 7, None):
        assert arrays.unpack(passthrough) is passthrough


def test_nan_never_reaches_the_json_as_a_bare_token():
    """`json.dump` writes `NaN`, which `JSON.parse` rejects outright -- one
    undefined cell would make a whole study's payload unreadable."""
    import json
    cleaned = arrays.nan_to_none([[1.0, float("nan")], [float("inf"), 2.0]])
    assert cleaned == [[1.0, None], [None, 2.0]]
    assert "NaN" not in json.dumps(cleaned)
