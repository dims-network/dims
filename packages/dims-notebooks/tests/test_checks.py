"""The checks must fire on the failures they were written for.

A diagnostic that never fires is decoration. Each test here constructs the
failure and asserts the check names it.
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dims_checks.coherence import coherence_report          # noqa: E402
from dims_checks.signals import signal_report               # noqa: E402


def write_csv(tmp_path, t, v, name="vid_a.csv"):
    p = tmp_path / name
    p.write_text("Time,a\n" + "\n".join(f"{a},{b}" for a, b in zip(t, v)) + "\n")
    return str(p)


# --- signals ---------------------------------------------------------------

def test_clean_series_has_nothing_to_say(tmp_path):
    t = np.arange(0, 10, 0.02)
    p = write_csv(tmp_path, t, np.sin(2 * np.pi * t))
    assert signal_report(p)["warnings"] == []


def test_a_gap_is_reported(tmp_path):
    t = np.concatenate([np.arange(0, 5, 0.02), np.arange(9, 14, 0.02)])
    p = write_csv(tmp_path, t, np.sin(t))
    assert any("gap" in w for w in signal_report(p)["warnings"])


def test_a_flatlined_signal_is_reported(tmp_path):
    # What tracking failure looks like in a file: perfectly valid, entirely useless.
    t = np.arange(0, 10, 0.02)
    p = write_csv(tmp_path, t, np.zeros_like(t))
    assert any("never changes" in w for w in signal_report(p)["warnings"])


def test_a_series_shorter_than_its_video_is_reported(tmp_path):
    t = np.arange(0, 10, 0.02)
    p = write_csv(tmp_path, t, np.sin(t))
    assert any("covers only" in w for w in signal_report(p, video_duration=60)["warnings"])


def test_uneven_sampling_is_reported(tmp_path):
    rng = np.random.default_rng(0)
    t = np.cumsum(rng.exponential(0.02, 400))
    p = write_csv(tmp_path, t, np.sin(t))
    assert any("uneven" in w for w in signal_report(p)["warnings"])


# --- coherence -------------------------------------------------------------

def _field(coh, power=None, null=None):
    n_f, n_t = coh.shape
    return {"coherence": coh,
            "power": np.ones_like(coh) if power is None else power,
            "period": np.linspace(0.5, 8, n_f),
            "time": np.arange(n_t) * 0.02,
            "coi": np.full(n_t, 8.0),
            "sig95_wtc": null}


def test_the_old_defect_is_caught():
    """Its exact fingerprint: saturated cells, and coherence tracking power."""
    rng = np.random.default_rng(1)
    power = rng.lognormal(0, 2, size=(32, 400))
    coh = np.clip(power / np.percentile(power, 40), 0, 1)   # what the bug produced
    r = coherence_report(_field(coh, power))
    assert r["saturated_at_1"] > 0.01
    assert r["corr_with_log_power"] > 0.5
    assert any("sit at exactly 1.0" in w for w in r["warnings"])
    assert any("correlates" in w for w in r["warnings"])


def test_a_healthy_field_is_not_flagged():
    rng = np.random.default_rng(2)
    coh = rng.uniform(0.05, 0.8, size=(32, 400))
    null = np.full(32, 0.59)
    r = coherence_report(_field(coh, rng.lognormal(0, 2, size=(32, 400)), null))
    assert not any("sit at exactly 1.0" in w for w in r["warnings"])
    assert "significant_fraction" in r


def test_a_missing_null_is_called_out():
    coh = np.full((16, 100), 0.3)
    r = coherence_report(_field(coh))
    assert any("no sig95_wtc" in w for w in r["warnings"])


def test_chance_level_coupling_is_called_out():
    """The finding that matters scientifically: a respectable-looking mean
    coherence that is nonetheless indistinguishable from red noise."""
    rng = np.random.default_rng(3)
    coh = rng.uniform(0.15, 0.35, size=(32, 400))      # mean ~0.25: independence
    null = np.full(32, 0.59)
    r = coherence_report(_field(coh, None, null))
    assert r["significant_fraction"] < 0.08
    assert any("no detectable coupling" in w for w in r["warnings"])
