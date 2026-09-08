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
    assert report == {"kept": {}, "replaced": {}, "stale": {}}


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
