"""Cross-recurrence against a lag we chose ourselves.

`sine_lagged` is `sine` delayed by exactly 0.4 s, so the cross-recurrence line
sits 20 samples off the diagonal. That is the one structure a striding
reduction destroys, and no real study can test it because nobody knows its
true lag.

Shared fixtures and helpers: conftest.py.
"""
import numpy as np

from conftest import LAG_S, LAG_SAMPLES, dense, diagonal_offsets, entry


# --- K3: a known lag lands where it should -----------------------------------

def test_K3_cross_recurrence_finds_the_lag_it_was_given(recurrence):
    """The line sits LAG off the diagonal, and that is the whole point.

    Catches: **striding**. Sampling every nth row and column keeps a line on
    the main diagonal and deletes one beside it -- and a lagged coupling is
    precisely a line beside it. This is the test the real studies could never
    have provided, because nobody knows their true lag.
    """
    study, _ = recurrence
    vis = entry(study, "crqa", "crqa_data", "sine_vs_sine_lagged")["visualization"]
    factor = vis["reduction"]["factor"]
    expected = LAG_SAMPLES / factor

    offsets = diagonal_offsets(dense(vis))
    assert offsets, "two identical signals, one delayed, produced no line at all"
    nearest = min(offsets, key=lambda k: abs(abs(k) - expected))
    assert abs(abs(nearest) - expected) <= max(2, 0.2 * expected), (
        f"the dominant line is at offset {nearest} (factor {factor}); a {LAG_S} s "
        f"lag should put it near {expected:.0f}. Offsets found: {offsets[:12]}")


