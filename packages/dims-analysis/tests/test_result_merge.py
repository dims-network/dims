"""A step must not delete an analysis it did not produce.

A study's output file is keyed by video, not by analysis: {video}_rqa_data.json
holds every RQA result for that video, whatever produced it. ORTHO runs the
shared RQA over its kinematic channels and a study-owned categorical RQA over
its gaze channels, into the same file.

StepContext.write_result was written to merge and does. No shipped step called
it — they all json.dump'd the whole file — so the behaviour lived in a docstring
and in a test that constructed a Step subclass no production code resembles.
That is the shape these tests avoid: they exercise the writer the steps use.
"""
import json

import pytest

from dims_analysis.common import results


def test_a_second_writer_does_not_remove_the_first(tmp_path):
    out = tmp_path / "v1_rqa_data.json"
    results.write_payload(str(out), {
        "video_id": "v1",
        "rqa_data": {"gaze_parent": {"categorical": True, "rr": 0.1}},
    })
    results.write_payload(str(out), {
        "video_id": "v1",
        "rqa_data": {"vx": {"rr": 0.07}},
        "precision": {"significant_figures": 6},
    })
    data = json.loads(out.read_text())["rqa_data"]
    assert sorted(data) == ["gaze_parent", "vx"]
    assert data["gaze_parent"]["categorical"] is True, \
        "the second writer replaced an analysis it did not produce"


def test_the_writer_says_what_it_kept_and_what_it_overwrote(tmp_path):
    """Both halves matter. A silent keep leaves stale results; a silent replace
    is how ORTHO lost its categorical gaze RQA."""
    out = tmp_path / "v1_rqa_data.json"
    results.write_payload(str(out), {
        "rqa_data": {"gaze_parent": {"n": 1}, "vx": {"n": 1}},
    })
    report = results.write_payload(str(out), {"rqa_data": {"vx": {"n": 2}}})
    assert report["kept"] == {"rqa_data": ["gaze_parent"]}
    assert report["replaced"] == {"rqa_data": ["vx"]}
    assert json.loads(out.read_text())["rqa_data"]["vx"] == {"n": 2}


def test_a_first_write_reports_nothing(tmp_path):
    out = tmp_path / "fresh.json"
    report = results.write_payload(str(out), {"rqa_data": {"vx": {}}})
    assert report == {"kept": {}, "replaced": {}, "stale": {}, "pruned": {}}


def test_scalars_and_new_keys_are_replaced_wholesale(tmp_path):
    """Only dicts merge. A changed precision block or video_id must not be a
    union of the old and the new."""
    out = tmp_path / "v1.json"
    results.write_payload(str(out), {"video_id": "v1", "note": "old", "list": [1, 2]})
    results.write_payload(str(out), {"video_id": "v1", "note": "new", "list": [3]})
    data = json.loads(out.read_text())
    assert data["note"] == "new"
    assert data["list"] == [3]


def test_an_unreadable_existing_file_is_replaced_not_fatal(tmp_path):
    out = tmp_path / "broken.json"
    out.write_text("{ not json")
    results.write_payload(str(out), {"rqa_data": {"vx": {}}})
    assert json.loads(out.read_text())["rqa_data"] == {"vx": {}}


@pytest.mark.parametrize("compact", [True, False])
def test_both_formats_round_trip(tmp_path, compact):
    out = tmp_path / f"f{int(compact)}.json"
    results.write_payload(str(out), {"a": {"b": 1}}, compact=compact)
    assert json.loads(out.read_text()) == {"a": {"b": 1}}
    assert ("\n" in out.read_text()) is not compact


# --- a merge across a format change ------------------------------------------

def test_entries_from_an_older_payload_version_are_not_kept():
    """Found by rebuilding ORTHO at 2.0.0, and it would have shipped.

    The merge preserves entries no incoming run rewrote -- that is the whole
    point of it, and it is why ORTHO's categorical gaze RQA survives a run of
    the shared RQA step. But when the *format* changes, an entry nothing
    rewrote is an entry no reader can read, and the file then carries a
    `payload_version` that describes only half of itself.

    Measured on four of ORTHO's twelve recordings: the gaze channels whose
    source CSV had gone missing kept their v1 `sparse_matrix` entries inside a
    file stamped v2, beside v2 bitmap entries. A tab reading `visualization.
    matrix` on those finds nothing and draws an empty panel.
    """
    from dims_analysis.common import results

    old = {"video_id": "v1", "payload_version": 1,
           "rqa_data": {"gaze": {"visualization": {"sparse_matrix": [[0, 1]]}},
                        "vx": {"visualization": {"sparse_matrix": [[1, 2]]}}}}
    new = {"video_id": "v1", "payload_version": 2,
           "rqa_data": {"vx": {"visualization": {"matrix": {"encoding": "bitmap-b64"}}}}}

    merged = results.merge_payload(old, new)
    assert set(merged["rqa_data"]) == {"vx"}, (
        "an entry in the old format survived into a file stamped with the new "
        f"one: {sorted(merged['rqa_data'])}")
    assert merged["payload_version"] == 2


def test_the_dropped_entries_are_reported_by_name():
    """Silently dropping someone else's analysis is the mirror of silently
    keeping an unreadable one. Both have happened here."""
    from dims_analysis.common import results

    old = {"payload_version": 1, "rqa_data": {"gaze": {}, "vx": {}}}
    new = {"payload_version": 2, "rqa_data": {"vx": {}}}
    report = results.compare_entries(old, new)
    assert report.get("stale", {}).get("rqa_data") == ["gaze"], report
    assert not report["kept"], "nothing can be kept across a format change"


def test_a_merge_at_the_same_version_still_keeps_everything():
    """The behaviour this must not break: ORTHO's study-owned categorical RQA
    writes into the same file as the shared step, and whichever runs second
    must not erase the other."""
    from dims_analysis.common import results

    old = {"payload_version": 2, "rqa_data": {"gaze": {"a": 1}}}
    new = {"payload_version": 2, "rqa_data": {"vx": {"b": 2}}}
    merged = results.merge_payload(old, new)
    assert set(merged["rqa_data"]) == {"gaze", "vx"}
    assert results.compare_entries(old, new)["kept"]["rqa_data"] == ["gaze"]


# --- a step removing its own entries, and only its own -----------------------
#
# `expected` is {payload key: the entry names the config asks for}. It is what
# scopes the removal: without it nothing is stamped and nothing is pruned, and
# an entry goes only when it is this owner's, absent from the run, AND absent
# from what the config still asks for.

RQA = "rqa_data"


def test_a_step_removes_the_entries_it_no_longer_produces(tmp_path):
    """The other half of the trade-off this module used to state.

    Preserving everything meant a study that stopped asking for a result kept
    the old answer in the file for ever, and every reader drew it.
    """
    out = tmp_path / "v1_rqa_data.json"
    results.write_payload(str(out), {
        "payload_version": 2, RQA: {"vx": {"n": 1}, "vy": {"n": 1}},
    }, owner="rqa", expected={RQA: {"vx", "vy"}})
    report = results.write_payload(str(out), {
        "payload_version": 2, RQA: {"vx": {"n": 2}},
    }, owner="rqa", expected={RQA: {"vx"}})

    assert sorted(json.loads(out.read_text())[RQA]) == ["vx"]
    assert report["pruned"] == {RQA: ["vy"]}
    assert not report["kept"], "a pruned entry must not also be reported as kept"


def test_an_entry_the_config_still_asks_for_is_kept_when_a_run_fails(tmp_path):
    """"Absent from this run" is not "no longer wanted".

    A step skips a data type whose source CSV is unreadable, warns, and carries
    on. Pruning on absence alone would delete a good and expensive result
    because somebody renamed a file -- so the config has to agree that the
    entry is gone before it goes.
    """
    out = tmp_path / "v1_rqa_data.json"
    results.write_payload(str(out), {
        "payload_version": 2, RQA: {"vx": {"n": 1}, "vy": {"n": 1}},
    }, owner="rqa", expected={RQA: {"vx", "vy"}})

    # vy is still asked for; its CSV went missing, so this run did not produce it.
    report = results.write_payload(str(out), {
        "payload_version": 2, RQA: {"vx": {"n": 2}},
    }, owner="rqa", expected={RQA: {"vx", "vy"}})

    assert sorted(json.loads(out.read_text())[RQA]) == ["vx", "vy"]
    assert not report["pruned"]
    assert report["kept"] == {RQA: ["vy"]}


def test_only_the_keys_a_step_owns_are_stamped_or_pruned(tmp_path):
    """A payload's top level is not all entries.

    A cross-wavelet payload also carries `config`, `provenance`,
    `processing_info` and `precision`, every field of which the output contract
    documents. Treating every top-level dict as entries stamped each of those
    and then pruned them: `provenance` drops its `None` fields, so a run with
    one optional field unset deleted a key a previous run had recorded.
    Measured before this was scoped -- `config.omega0` disappeared.
    """
    out = tmp_path / "dyad01_crosswavelet_data.json"
    results.write_payload(str(out), {
        "payload_version": 2,
        "crosswavelet_pairs": {"a_vs_b": {"m": 1}},
        "config": {"omega0": 6, "dj": 0.08},
        "processing_info": {"pairs_computed": 1},
    }, owner="crosswavelet", expected={"crosswavelet_pairs": {"a_vs_b"}})

    results.write_payload(str(out), {
        "payload_version": 2,
        "crosswavelet_pairs": {"a_vs_b": {"m": 2}},
        "config": {"dj": 0.08},                    # omega0 not applicable now
        "processing_info": {"pairs_computed": 1},
    }, owner="crosswavelet", expected={"crosswavelet_pairs": {"a_vs_b"}})

    data = json.loads(out.read_text())
    assert data["config"]["omega0"] == 6, \
        "a documented config field was pruned as if it were an analysis entry"
    assert list(data[results.OWNERS_KEY]) == ["crosswavelet_pairs"], \
        f"metadata blocks were stamped: {sorted(data[results.OWNERS_KEY])}"


def test_one_step_does_not_prune_anothers_entries(tmp_path):
    """The ORTHO guarantee, under ownership. ORTHO's study-owned categorical
    gaze RQA writes into the same file as the shared step, and a prune by
    either must be invisible to the other."""
    out = tmp_path / "v1_rqa_data.json"
    results.write_payload(str(out), {
        "payload_version": 2, RQA: {"gaze_parent": {"categorical": True}},
    }, owner="ortho-gaze-rqa", expected={RQA: {"gaze_parent"}})
    results.write_payload(str(out), {
        "payload_version": 2, RQA: {"vx": {"n": 1}, "vy": {"n": 1}},
    }, owner="rqa", expected={RQA: {"vx", "vy"}})

    report = results.write_payload(str(out), {
        "payload_version": 2, RQA: {"vx": {"n": 2}},
    }, owner="rqa", expected={RQA: {"vx"}})

    data = json.loads(out.read_text())[RQA]
    assert sorted(data) == ["gaze_parent", "vx"], \
        "the shared step pruned an analysis it did not produce"
    assert data["gaze_parent"]["categorical"] is True
    assert report["pruned"] == {RQA: ["vy"]}
    assert report["kept"] == {RQA: ["gaze_parent"]}


def test_an_entry_with_no_recorded_owner_is_kept_and_named(tmp_path):
    """A file written before this bookkeeping existed cannot be spoken for.

    Dropping such an entry on a guess is how the shared step would delete a
    fork's results, which is the failure merging was introduced to prevent. It
    is reported instead, and `dims-analysis prune` is the deliberate removal.
    """
    out = tmp_path / "v1_rqa_data.json"
    results.write_payload(str(out), {
        "payload_version": 2, RQA: {"legacy": {"n": 1}},
    })                                              # no owner: an older core
    report = results.write_payload(str(out), {
        "payload_version": 2, RQA: {"vx": {"n": 1}},
    }, owner="rqa", expected={RQA: {"vx"}})

    assert sorted(json.loads(out.read_text())[RQA]) == ["legacy", "vx"]
    assert report["kept"] == {RQA: ["legacy"]}
    assert not report["pruned"]


def test_the_phantom_third_person(tmp_path):
    """The bug this was found by, reduced to the write that caused it.

    A study had three people; `rtpjSync` was placed on the third. The person
    was removed in the wizard and the study rebuilt. `include_crosswavelet`
    then asked for four pairs and `processing_info.pairs_computed` said four --
    while the file on disk held seven, because nothing ever removed the three
    the earlier build had written. The network tab reads the file, found a
    measure no effector declared, and drew it as an extra grey person.
    """
    out = tmp_path / "dyad01_crosswavelet_data.json"
    before = ["a_vs_b", "a_vs_c", "b_vs_c", "a_vs_rtpjSync", "b_vs_rtpjSync"]
    results.write_payload(str(out), {
        "payload_version": 2,
        "crosswavelet_pairs": {k: {"mean": 0.5} for k in before},
        "processing_info": {"pairs_computed": len(before)},
    }, owner="crosswavelet", expected={"crosswavelet_pairs": set(before)})

    after = ["a_vs_b", "a_vs_c", "b_vs_c"]
    results.write_payload(str(out), {
        "payload_version": 2,
        "crosswavelet_pairs": {k: {"mean": 0.5} for k in after},
        "processing_info": {"pairs_computed": len(after)},
    }, owner="crosswavelet", expected={"crosswavelet_pairs": set(after)})

    data = json.loads(out.read_text())
    assert sorted(data["crosswavelet_pairs"]) == sorted(after)
    assert data["processing_info"]["pairs_computed"] == \
        len(data["crosswavelet_pairs"]), \
        "the file disagrees with its own count of what was computed"
    assert "rtpjSync" not in out.read_text()


def test_the_owner_index_does_not_outlive_its_entries(tmp_path):
    """Bookkeeping about a pair nobody holds is how an index rots."""
    out = tmp_path / "v1.json"
    results.write_payload(str(out), {
        "payload_version": 2, RQA: {"vx": {}, "vy": {}},
    }, owner="rqa", expected={RQA: {"vx", "vy"}})
    results.write_payload(str(out), {
        "payload_version": 2, RQA: {"vx": {}},
    }, owner="rqa", expected={RQA: {"vx"}})

    data = json.loads(out.read_text())
    assert data[results.OWNERS_KEY] == {RQA: {"vx": "rqa"}}


def test_nothing_is_stamped_when_nobody_claims_it(tmp_path):
    """An owner-less write behaves exactly as it always did, and adds no key."""
    out = tmp_path / "v1.json"
    results.write_payload(str(out), {"payload_version": 2, RQA: {"vx": {}}})
    assert results.OWNERS_KEY not in json.loads(out.read_text())


def test_an_owner_that_names_no_keys_prunes_nothing(tmp_path):
    """`Step.expected_entries` answers {} for a step that cannot say what its
    config asks for. Such a step's entries are stamped with nobody and removed
    by nothing, which is the safe end of the trade."""
    out = tmp_path / "v1.json"
    results.write_payload(str(out), {
        "payload_version": 2, RQA: {"vx": {}, "vy": {}},
    }, owner="mystery")
    report = results.write_payload(str(out), {
        "payload_version": 2, RQA: {"vx": {}},
    }, owner="mystery")

    assert sorted(json.loads(out.read_text())[RQA]) == ["vx", "vy"]
    assert not report["pruned"]
    assert results.OWNERS_KEY not in json.loads(out.read_text())


def test_a_nameless_rewrite_releases_the_entry(tmp_path):
    """An entry a nameless run rewrote is no longer the work of the step
    recorded against it. Keeping the stamp would let that step's next prune
    delete a result it did not produce -- the ORTHO failure by a longer road."""
    out = tmp_path / "v1.json"
    results.write_payload(str(out), {
        "payload_version": 2, RQA: {"vx": {"n": 1}},
    }, owner="rqa", expected={RQA: {"vx"}})
    results.write_payload(str(out), {
        "payload_version": 2, RQA: {"vx": {"n": 2}},
    }, expected={RQA: {"vx"}})                       # no owner
    report = results.write_payload(str(out), {
        "payload_version": 2, RQA: {"vy": {"n": 1}},
    }, owner="rqa", expected={RQA: {"vy"}})

    assert sorted(json.loads(out.read_text())[RQA]) == ["vx", "vy"]
    assert not report["pruned"]


def test_a_format_change_still_keeps_nothing(tmp_path):
    """Ownership must not resurrect entries in an encoding no reader speaks."""
    out = tmp_path / "v1.json"
    results.write_payload(str(out), {
        "payload_version": 1, RQA: {"vx": {}, "gaze": {}},
    }, owner="rqa", expected={RQA: {"vx", "gaze"}})
    report = results.write_payload(str(out), {
        "payload_version": 2, RQA: {"vx": {}},
    }, owner="rqa", expected={RQA: {"vx"}})

    data = json.loads(out.read_text())
    assert set(data[RQA]) == {"vx"}
    assert data[results.OWNERS_KEY] == {RQA: {"vx": "rqa"}}
    assert report["stale"] == {RQA: ["gaze"]}, \
        "a dropped old-format entry is stale, not pruned"
    assert not report["pruned"]


def test_an_unstamped_payload_is_refused_rather_than_dropping_what_is_there(tmp_path):
    """The sharp edge of "nothing merges across a version change".

    A study-owned step written before versioning existed declares no
    `payload_version`. The file it writes into declares one. Treating that as a
    version change would drop every entry already there -- including analyses
    this step did not produce -- turning one forgotten field into the silent
    loss merging was introduced to prevent.
    """
    from dims_analysis.common import results

    out = tmp_path / "shared.json"
    results.write_payload(str(out), {"payload_version": 2, "rqa_data": {"vx": {"a": 1}}})

    with pytest.raises(results.UnversionedPayload, match="payload_version"):
        results.write_payload(str(out), {"rqa_data": {"gaze": {"b": 2}}})

    # And nothing was written: the file still holds what it held.
    import json
    assert sorted(json.load(open(out))["rqa_data"]) == ["vx"]
