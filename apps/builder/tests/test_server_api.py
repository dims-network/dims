"""The wizard's API, exercised the way the browser exercises it.

These tests exist because the wizard's failures are all of one kind: something
is quietly not there, and the person using it is the one least able to work out
why. So each of them asks "would a user get what the screen promised?" rather
than "did the call return 200".
"""
import io
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The wizard is an optional extra, and this is the only suite that needs it.
# Without the guard, `pytest` at the repository root is a collection error
# rather than a skip for anyone who installed `.[dev]` -- which does not carry
# flask -- and the one CI job that installs it is the only place anybody would
# find out. Same idiom as tests/test_contracts.py for jsonschema.
pytest.importorskip("flask", reason="the builder's extra: pip install '.[builder]'")

from dims_builder import server  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _example_study_cache(tmp_path_factory):
    """Generate the example study once per run, and never into the user's cache.

    The wizard generates it on demand rather than shipping it, so a test that
    presses the button pays for the videos. Once per session is the whole cost;
    every later call is a cache hit.
    """
    os.environ["DIMS_BUILDER_CACHE"] = str(tmp_path_factory.mktemp("cache"))
    yield
    os.environ.pop("DIMS_BUILDER_CACHE", None)


@pytest.fixture
def client():
    app = server.create_app()
    with app.test_client() as c:
        c.state = app.state
        yield c


def start(client, tmp_path, visibility="private"):
    out = str(tmp_path / "study")
    r = client.post("/api/project", json={"output_dir": out, "visibility": visibility,
                                          "config": {"title": "T"}})
    assert r.status_code == 200, r.get_json()
    return out, r.get_json()


# --- the example study ------------------------------------------------------

EXPECTED_MEASURES = [
    "personLeftLeftHandSpeed", "personLeftRightHandSpeed",
    "personRightLeftHandSpeed", "personRightRightHandSpeed", "rtpjSync",
]


def test_the_example_study_loads_in_one_click(client, tmp_path):
    """Someone who has not got their own data yet has to be able to reach a
    working dashboard, and the only way in used to be finding a folder and
    dragging its contents in."""
    start(client, tmp_path)
    r = client.post("/api/samples")
    assert r.status_code == 200, r.get_json()
    files = r.get_json()["files"]

    sessions = {f["videoID"] for f in files}
    assert sessions == {"dyad01", "dyad02"}, sessions
    # Each dyad is its own folder, so the button only works if the endpoint
    # walks the generated tree rather than listing its top level. And both
    # dyads carry the same measures: a study where one session is shaped
    # differently from the next teaches the wrong thing.
    for dyad in sorted(sessions):
        got = sorted(f["dataType"] for f in files
                     if f["videoID"] == dyad and f["role"] == "timeseries")
        assert got == EXPECTED_MEASURES, (dyad, got)
    assert {f["role"] for f in files} == {"video", "timeseries", "transcript", "elan"}
    assert not any(i["level"] == "error" for f in files for i in f["issues"]), (
        "the example study does not validate cleanly, so it teaches the wrong thing")


def test_a_multi_column_csv_is_split_on_upload(client, tmp_path):
    """Motion tracking hands you one wide file; every analysis reads one measure
    per file. The example study no longer carries such a file -- it would make
    one dyad shaped unlike the other -- so the behaviour is asserted directly."""
    start(client, tmp_path)
    wide = b"Time,alpha,beta,gamma\n0.0,1,2,3\n0.5,4,5,6\n1.0,7,8,9\n"
    r = client.post("/api/upload", data={
        "file": (io.BytesIO(wide), "session9.csv")}, content_type="multipart/form-data")
    assert r.status_code == 200, r.get_json()
    rows = r.get_json()["files"]

    assert sorted(f["dataType"] for f in rows) == ["alpha", "beta", "gamma"]
    assert {f["videoID"] for f in rows} == {"session9"}
    assert all(f["columns"][0] == "Time" and len(f["columns"]) == 2 for f in rows)


def test_the_example_study_builds_and_its_config_is_valid(client, tmp_path):
    out, _ = start(client, tmp_path)
    client.post("/api/samples")
    client.post("/api/config", json={
        "include_RQA": ["rtpjSync"],
        "include_crosswavelet": [["personLeftRightHandSpeed",
                                  "personRightRightHandSpeed"]],
        "include_cRQA": [["personLeftRightHandSpeed",
                          "personRightRightHandSpeed"]],
        "include_elan": True,
    })
    r = client.post("/api/build")
    assert r.status_code == 200, r.get_json()
    assert len(r.get_json()["placed"]) == 16

    cfg = json.load(open(os.path.join(out, "config.json")))
    from dims_builder import project
    assert project.schema_problems(cfg) == []
    assert sorted(cfg["videoIDs"]) == ["dyad01", "dyad02"]


# --- the network, and what switching it on implies --------------------------

def test_switching_the_network_on_switches_the_chance_level_on(client, tmp_path):
    """Without a chance level no edge can be told from coincidence: an unrelated
    pair scores about 0.25, not 0. The wizard states this and the config carries
    it, so the study says what it will do before it does it."""
    out, _ = start(client, tmp_path)
    client.post("/api/samples")
    client.post("/api/config", json={
        "include_crosswavelet": [["personLeftRightHandSpeed", "personRightRightHandSpeed"]],
        "include_network": True,
    })
    assert client.post("/api/build").status_code == 200
    cfg = json.load(open(os.path.join(out, "config.json")))
    assert cfg["include_network"] is True
    assert cfg["analysis"]["crosswavelet"]["mcCount"] == 100


def test_an_explicit_surrogate_count_wins(client, tmp_path):
    out, _ = start(client, tmp_path)
    client.post("/api/samples")
    client.post("/api/config", json={
        "include_crosswavelet": [["personLeftRightHandSpeed", "personRightRightHandSpeed"]],
        "include_network": True,
        "analysis": {"crosswavelet": {"mcCount": 20}},
    })
    client.post("/api/build")
    cfg = json.load(open(os.path.join(out, "config.json")))
    assert cfg["analysis"]["crosswavelet"]["mcCount"] == 20


# --- reopening --------------------------------------------------------------

def test_reopening_brings_back_the_files_and_the_settings(client, tmp_path):
    out, _ = start(client, tmp_path)
    client.post("/api/samples")
    client.post("/api/config", json={
        "include_RQA": ["rtpjSync"], "include_elan": True,
        "analysis": {"rqa": {"window": 6, "targetRecurrence": 0.1}},
    })
    client.post("/api/build")

    fresh = server.create_app().test_client()
    r = fresh.post("/api/open", json={"output_dir": out})
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["visibility"] == "private"
    assert len(d["files"]) == 16
    assert d["config"]["include_RQA"] == ["rtpjSync"]
    assert d["config"]["analysis"]["rqa"]["window"] == 6
    assert sorted(d["config"]["videoIDs"]) == ["dyad01", "dyad02"]


def test_removing_a_reopened_row_does_not_delete_the_studys_data(client, tmp_path):
    """A row is a list entry. Taking one off must not reach into the study and
    delete a recording -- for a private study that data may be the only copy."""
    out, _ = start(client, tmp_path)
    client.post("/api/samples")
    client.post("/api/config", json={"include_elan": True})
    client.post("/api/build")

    fresh_app = server.create_app()
    fresh = fresh_app.test_client()
    files = fresh.post("/api/open", json={"output_dir": out}).get_json()["files"]
    victim = next(f for f in files if f["role"] == "video")
    on_disk = fresh_app.state["staged"][victim["id"]]["path"]
    assert os.path.exists(on_disk)

    fresh.delete(f"/api/upload/{victim['id']}")
    assert os.path.exists(on_disk), "removing a row deleted the study's own video"


def test_reopening_a_folder_that_is_not_a_study_explains_itself(client, tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    r = client.post("/api/open", json={"output_dir": str(plain)})
    assert r.status_code == 400
    assert "not a DIMS study" in r.get_json()["error"]


# --- what the wizard no longer asks -----------------------------------------

def test_a_template_source_is_neither_asked_for_nor_accepted(client, tmp_path):
    """There is one scaffold and it is in this repository."""
    out = str(tmp_path / "study")
    r = client.post("/api/project", json={
        "output_dir": out, "visibility": "private",
        "template_source": "https://example.invalid/not-a-template.git"})
    assert r.status_code == 200, "a template source should be ignored, not honoured"
    case = json.load(open(os.path.join(out, "dims-case.json")))
    assert case["vendorHashes"], "the core came from somewhere other than here"

    page = client.get("/").get_data(as_text=True)
    assert "Template source" not in page
    assert "scaffold folder on this machine" not in page


def test_a_private_study_is_never_told_to_commit_everything(client, tmp_path):
    """The wizard must not walk its own user into the failure step 1 warns about.

    `git add -A` is the one command the privacy guards exist to intercept, and
    they only run once the user has pointed git at them -- a thing a person does,
    in every clone, and may not have done yet. The deploy instructions therefore
    differ by visibility, and the private one puts `core.hooksPath` before the
    first commit.
    """
    page = client.get("/static/builder.js").get_data(as_text=True)
    assert "core.hooksPath .githooks" in page
    assert "do this BEFORE the first commit" in page
    # And it does not offer to publish a private study without saying what that
    # means.
    assert "Publishing it means publishing the recordings" in page


def test_the_deploy_instructions_name_the_folder(client, tmp_path):
    """`cd <your-output-folder>` is a placeholder the builder could have filled
    in: it knows the folder, and the reader is copy-pasting."""
    page = client.get("/static/builder.js").get_data(as_text=True)
    assert "<your-output-folder>" not in page
    assert "state.outputDir" in page
