"""Sanity checks for a DIMS study.

The logic lives here rather than inside the notebooks, so it can be tested and
so a notebook stays short enough to read. The notebooks are thin: they load a
study and print these.

Why this exists at all: the wavelet coherence defect that shipped to five
repositories was found by a notebook. Had a check like `coherence_report` been
part of the core and run routinely, it would not have shipped.
"""
from dims_checks.signals import signal_report, load_series
from dims_checks.coherence import coherence_report, load_crosswavelet

__all__ = ["signal_report", "load_series", "coherence_report", "load_crosswavelet"]
__version__ = "1.0.2"
