"""What the cross-effector network needs from a payload, and how it breaks.

`case-karnatak/tabs/network.js` is the only consumer of the coherence null in
the whole system, and it is the tab most likely to fail quietly: it draws an
edge per pair, decides solid-or-dashed from a significance fraction, and
reduces over a period band and a time window. Every one of those steps reads a
field that the analysis has to have written correctly, and getting it wrong
draws a plausible picture rather than an error.

The three `eff_*` signals here have the coupling structure the tab exists to
find, and deliberately the shape of the real Karnatak result: two effectors
sharing a component are coupled, a third is not. So a correct network is one
solid edge and two dashed.

The tab itself is JavaScript and lives in a private study. These tests cover
the contract it depends on -- what the analysis must produce for it to be able
to work at all.
"""
import json
import os

import numpy as np
import pytest

from conftest import build

COUPLED = "eff_hand_l_vs_eff_hand_r"
UNCOUPLED = ("eff_hand_l_vs_eff_other", "eff_hand_r_vs_eff_other")

#: What independence gives, by construction.
CHANCE = 0.05


@pytest.fixture(scope="session")
def network(coherence_study):
    study, _ = coherence_study
    path = os.path.join(study, "assets", "crosswavelet",
                        "reference_crosswavelet_data.json")
    with open(path) as fh:
        return json.load(fh)["crosswavelet_pairs"]


def vis(pairs, key):
    return pairs[key]["visualization"]


def grid(field):
    return np.array([[np.nan if c is None else c for c in row] for row in field],
                    dtype=float)


# --- the structure the network draws -----------------------------------------

def test_every_pair_the_config_asked_for_is_there(network):
    """A missing pair is a missing edge, and an edge that is simply absent
    looks exactly like an edge that was measured and found to be nothing."""
    for key in (COUPLED,) + UNCOUPLED:
        assert key in network, f"no {key}; found {sorted(network)}"


def test_each_pair_names_its_two_effectors(network):
    """The tab builds its nodes from `data_type1`/`data_type2`, not from the
    key. If they disagreed, edges would connect the wrong nodes -- and the
    picture would still look like a network."""
    for key in (COUPLED,) + UNCOUPLED:
        entry = network[key]
        assert entry["data_type1"] and entry["data_type2"]
        assert entry["data_type1"] in key and entry["data_type2"] in key, (
            f"{key} says it relates {entry['data_type1']} and "
            f"{entry['data_type2']}")


def test_the_coupling_structure_is_recovered(network):
    """One solid edge, two dashed. Measured: 0.753 for the coupled pair, 0.037
    and 0.079 for the uncoupled ones.

    This is the whole output of a cross-effector network, and on real data it
    is unverifiable -- which is why the coupling here was put in on purpose.
    """
    coupled = network[COUPLED]["statistics"]["wtc_signif_fraction"]
    assert coupled > 0.4, (
        f"two effectors sharing 70 % of their variation read {coupled:.4f} "
        f"above chance")
    for key in UNCOUPLED:
        share = network[key]["statistics"]["wtc_signif_fraction"]
        assert share < 0.2, (
            f"{key} shares nothing and reads {share:.4f} above chance; "
            f"independence gives about {CHANCE}")
        assert coupled > share + 0.3, (
            f"the coupled pair ({coupled:.4f}) is not clearly separated from "
            f"{key} ({share:.4f}); the network cannot distinguish them")


# --- the fields it reads, and the ways they break ---------------------------

def test_the_null_has_one_entry_per_period_row(network):
    """A length mismatch makes the step drop `sig95_wtc` entirely, and the tab
    then falls back to `sig95_xwt` -- cross-wavelet *power* significance, which
    answers "was there a lot of energy here?" and is not a test of coupling at
    all. The fallback exists so old files still render; it must not be reached
    by a file written today."""
    for key in (COUPLED,) + UNCOUPLED:
        v = vis(network, key)
        assert "sig95_wtc" in v, f"{key} has no coherence null at all"
        assert len(v["sig95_wtc"]) == len(v["period"]), (
            f"{key}: {len(v['sig95_wtc'])} null values for "
            f"{len(v['period'])} period rows")


def test_an_unusable_null_is_null_and_never_a_number(network):
    """The tab skips rows whose level could not be estimated. A 0 there would
    instead read as "everything in this row beats chance" and draw a solid edge
    out of nothing."""
    for key in (COUPLED,) + UNCOUPLED:
        levels = vis(network, key)["sig95_wtc"]
        assert all(x is None or x > 0 for x in levels), (
            f"{key} has a level of exactly 0, which no cell can fail to beat")


def test_a_period_row_inside_the_cone_reduces_to_null_not_to_zero():
    """Constructed, because the reference study no longer produces one.

    Rows lying entirely inside the cone of influence have no estimable
    threshold, and the frequency reduction averages neighbouring rows -- so a
    NaN row must not drag its neighbour to NaN, and a row that is *all* NaN
    must stay NaN rather than becoming 0. Both directions matter: the first
    would lose good rows, the second would mark a whole period band as
    always-significant.

    This stopped happening in the study itself once the reduction cap was
    fixed, and the test that noticed said so rather than passing vacuously.
    The reduction was inlined in the middle of a 90-line function until this
    test needed to call it, which is its own small finding.
    """
    from dims_analysis.steps import crosswavelet as cw

    levels = np.array([0.6, 0.61, np.nan, np.nan, 0.62, np.nan], dtype=float)
    reduced = cw._reduce_null(levels, 2)
    assert np.isnan(reduced[1]), "a pair of unusable rows must stay unusable"
    assert not np.isnan(reduced[0]), "two usable rows must survive"
    assert np.isclose(reduced[2], 0.62), "a half-usable pair keeps the usable half"


def test_the_coherence_grid_matches_its_axes(network):
    """The tab indexes coherence by [period][time]. Any disagreement here is an
    off-by-one that silently shifts every edge in the network."""
    for key in (COUPLED,) + UNCOUPLED:
        v = vis(network, key)
        coh = grid(v["coherence"])
        assert coh.shape == (len(v["period"]), len(v["time"])), (
            f"{key}: coherence is {coh.shape} for {len(v['period'])} periods "
            f"and {len(v['time'])} times")
        assert len(v["coi"]) == len(v["time"]), (
            f"{key}: the cone has {len(v['coi'])} points for "
            f"{len(v['time'])} times")


def test_the_period_axis_is_ordered_so_a_band_can_be_selected(network):
    """The tab's band control takes a low and a high period and selects the
    rows between them. That is only meaningful on a monotonic axis."""
    period = np.array(vis(network, COUPLED)["period"], dtype=float)
    assert np.all(np.diff(period) > 0), "the period axis is not increasing"
    assert period[0] > 0


def test_restricting_to_a_band_sharpens_the_answer(network):
    """What the band control is for, and a check that it can be done from the
    payload alone: inside the band where the shared component lives, the
    coupled pair separates further from the uncoupled ones."""
    def fraction(key, lo=None, hi=None):
        v = vis(network, key)
        coh = grid(v["coherence"])
        level = np.array([np.nan if x is None else x for x in v["sig95_wtc"]],
                         dtype=float)
        period = np.array(v["period"], dtype=float)
        coi = np.array(v["coi"], dtype=float)
        inside_cone = period[:, None] > coi[None, :]
        rows = np.ones(len(period), dtype=bool)
        if lo is not None:
            rows &= (period >= lo) & (period <= hi)
        usable = (np.isfinite(coh) & np.isfinite(level)[:, None]
                  & ~inside_cone & rows[:, None])
        if not usable.any():
            return None
        return np.sum((coh > level[:, None]) & usable) / np.sum(usable)

    whole = fraction(COUPLED)
    assert whole is not None and whole > 0.4
    for key in UNCOUPLED:
        assert fraction(key) < whole


def test_each_pair_carries_the_statistics_the_tab_reads(network):
    for key in (COUPLED,) + UNCOUPLED:
        stats = network[key]["statistics"]
        for field in ("mean_coherence", "wtc_signif_fraction"):
            assert field in stats, f"{key} has no {field}"
            assert stats[field] is not None


def test_the_tab_and_the_payload_agree_about_the_cone(network):
    """Two implementations of one rule, which is where drift comes from.

    The payload carries `statistics.wtc_signif_fraction`, computed in Python
    over cells outside the cone of influence. The network tab computes its own
    per-edge fraction in JavaScript, over a period band and a time window, with
    its own cone test:

        if (period.length && coi && !(period[i] < coi[j])) continue;

    Over the whole record and the whole band the two must be the same number.
    Measured across the five pairs here they agree to within 0.004 -- the
    remainder is the boundary convention on exact equality.

    The stakes: including the cone instead of excluding it turns 0.048 into
    0.126 on independent signals, so an at-chance edge would be drawn solid.
    """
    for key in (COUPLED,) + UNCOUPLED:
        v = vis(network, key)
        coherence, period, coi = v["coherence"], v["period"], v["coi"]
        levels = v["sig95_wtc"]

        tested = significant = 0
        for i, level in enumerate(levels):
            if level is None:               # no estimable threshold for this row
                continue
            for j, coi_at_t in enumerate(coi):
                value = coherence[i][j]
                if value is None:           # undefined coherence
                    continue
                if not (period[i] < coi_at_t):   # inside the cone: skip
                    continue
                tested += 1
                significant += value > level

        assert tested, f"{key}: every cell was excluded, so nothing was compared"
        theirs = significant / tested
        ours = network[key]["statistics"]["wtc_signif_fraction"]
        assert abs(theirs - ours) < 0.01, (
            f"{key}: the payload reports {ours:.4f}, the tab's own rule gives "
            f"{theirs:.4f}. One of the two changed its mind about the cone.")
