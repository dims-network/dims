"""`dims-analysis prune` -- removing entries a config no longer asks for.

`write_payload` stamps each entry with the step that wrote it and can remove
its own on the next run. A file written before that bookkeeping existed records
no owner, and an unstamped entry is never removed on a guess: it could be the
output of a study-owned analysis sharing the file. So a study built before that
release keeps its orphans through any number of rebuilds, and this command is
how they go -- deliberately, with a person reading the list first.

The study this was written for: `include_crosswavelet` asked for four pairs and
the payload held seven, two of them naming a series whose person had been
removed in the wizard. The network tab drew that series as an extra grey body.
"""
import json

import pytest

from dims_analysis import cli
from dims_analysis.base import Step
from dims_analysis.common import results


CW = "crosswavelet_pairs"


class _PairStep(Step):
    """A step whose entries are pairs, like the real cross-wavelet one."""
    id = "pairs"
    config_key = "include_crosswavelet"
    output_dir = "assets/pairs"
    output_name = "{video_id}_pairs_data.json"
    extra_output_names = ("{video_id}_pairs_full.json",)

    def expected_entries(self, config):
        return {CW: {f"{a}_vs_{b}" for a, b in config["include_crosswavelet"]}}

    def run(self, config, ctx):        # pragma: no cover - prune never runs it
        raise NotImplementedError


@pytest.fixture
def study(tmp_path, monkeypatch):
    """A project holding two files with one orphan pair each."""
    monkeypatch.setattr(cli, "discover", lambda problems=None: {"pairs": _PairStep()})
    p = tmp_path / "study"
    out = p / "assets" / "pairs"
    out.mkdir(parents=True)
    (p / "config.json").write_text(json.dumps({
        "videoIDs": ["v1"],
        "dataTypes": {"v1": ["a", "b", "c"]},
        "include_crosswavelet": [["a", "b"]],
    }))
    for name in ("v1_pairs_data.json", "v1_pairs_full.json"):
        (out / name).write_text(json.dumps({
            "video_id": "v1", "payload_version": 2,
            CW: {"a_vs_b": {"m": 1}, "a_vs_rtpjSync": {"m": 2}},
            "processing_info": {"pairs_computed": 1},
        }))
    return p


def _prune(study, *extra):
    return cli.main(["prune", "--config", str(study / "config.json"), *extra])


def _pairs(study, name="v1_pairs_data.json"):
    path = study / "assets" / "pairs" / name
    return json.loads(path.read_text())[CW]


def test_a_report_alone_writes_nothing(study, capsys):
    assert _prune(study) == 0
    out = capsys.readouterr().out
    assert "would remove" in out
    assert "a_vs_rtpjSync" in out
    assert "--apply" in out, "the report must say how to act on itself"
    assert sorted(_pairs(study)) == ["a_vs_b", "a_vs_rtpjSync"], \
        "a dry run changed the file"


def test_apply_removes_the_orphan_and_keeps_the_rest(study, capsys):
    assert _prune(study, "--apply") == 0
    assert sorted(_pairs(study)) == ["a_vs_b"]
    # Both of the step's files, not just the one it names first: a prune that
    # cleaned one would leave the two disagreeing about which pairs exist.
    assert sorted(_pairs(study, "v1_pairs_full.json")) == ["a_vs_b"]
    assert "removed 6 entries" not in capsys.readouterr().out


def test_nothing_else_in_the_payload_is_touched(study):
    _prune(study, "--apply")
    data = json.loads((study / "assets" / "pairs" / "v1_pairs_data.json").read_text())
    assert data["processing_info"] == {"pairs_computed": 1}
    assert data["payload_version"] == 2
    assert data["video_id"] == "v1"


def test_an_entry_another_step_owns_is_never_offered(study, capsys):
    """The one thing here that could destroy data.

    In one real study `gaze_child` and `gaze_parent` sit in `*_rqa_data.json`,
    are absent from `include_RQA`, and are not orphans -- they are a
    study-owned categorical RQA's results. An entry stamped by a step other
    than the one claiming the key is reported as kept and left alone.
    """
    path = study / "assets" / "pairs" / "v1_pairs_data.json"
    data = json.loads(path.read_text())
    data[CW]["gaze_vs_gaze"] = {"categorical": True}
    data[results.OWNERS_KEY] = {CW: {"gaze_vs_gaze": "study-owned-gaze"}}
    path.write_text(json.dumps(data))

    assert _prune(study, "--apply") == 0
    out = capsys.readouterr().out
    assert "keeping" in out and "study-owned-gaze" in out
    assert sorted(_pairs(study)) == ["a_vs_b", "gaze_vs_gaze"]


def test_an_unstamped_removal_is_called_out(study, capsys):
    """Unstamped means nobody knows whose it is, and the report says so rather
    than presenting the list as certainly safe."""
    _prune(study)
    out = capsys.readouterr().out
    assert "owner: unknown" in out
    assert "study-owned analysis" in out


def test_a_clean_study_says_so(study, capsys):
    _prune(study, "--apply")
    capsys.readouterr()
    assert _prune(study) == 0
    assert "nothing to remove" in capsys.readouterr().out


def test_the_owner_index_loses_what_the_prune_took(study):
    path = study / "assets" / "pairs" / "v1_pairs_data.json"
    data = json.loads(path.read_text())
    data[results.OWNERS_KEY] = {CW: {"a_vs_b": "pairs", "a_vs_rtpjSync": "pairs"}}
    path.write_text(json.dumps(data))

    _prune(study, "--apply")
    assert json.loads(path.read_text())[results.OWNERS_KEY] == {CW: {"a_vs_b": "pairs"}}


def test_a_step_that_cannot_say_is_skipped(study, capsys, monkeypatch):
    """`expected_entries` answering {} means "cannot say", and a prune that
    treated that as "asks for nothing" would empty the file."""
    monkeypatch.setattr(_PairStep, "expected_entries", lambda self, config: {})
    assert _prune(study, "--apply") == 0
    assert sorted(_pairs(study)) == ["a_vs_b", "a_vs_rtpjSync"]
    assert "nothing to remove" in capsys.readouterr().out


def test_an_unknown_step_is_an_error(study):
    assert _prune(study, "--steps", "nope") == 2


def test_a_missing_config_is_an_error(tmp_path):
    assert cli.main(["prune", "--config", str(tmp_path / "nope.json")]) == 2
