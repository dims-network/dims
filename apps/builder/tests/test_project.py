"""What the wizard produces, against what a study is supposed to be.

The point these test: a study the builder makes and a study `dims-case new`
makes must be the same study. `project.py` has said so in a docstring for some
time and it was not true -- the builder hand-wrote `dims-case.json`, wrote no
`restricted` list, installed no hooks, and hard-coded a visibility it never
asked about.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dims_builder import project  # noqa: E402


def test_the_scaffold_is_the_one_in_this_repository():
    """There is one scaffold and it ships here. The wizard used to ask, and
    every answer but the default was a way to get it wrong: the URL it suggested
    pointed at the pre-monorepo template, which carries a dashboard with no
    vendored core, so a study built from it would have been a fork."""
    assert project.is_template_dir(project.BUNDLED_TEMPLATE)
    assert not hasattr(project, "acquire_template"), (
        "the template-source entry point is still there")
    for gone in ("_resolve_local_template", "_looks_like_url"):
        assert not hasattr(project, gone), f"{gone} still resolves a source"


def test_the_core_comes_from_this_repository_not_whatever_is_installed(tmp_path):
    """An editable install pointing at another checkout used to win, and the
    wizard would then copy this repository's scaffold and another repository's
    vendored core into one folder, stamped with the other one's version."""
    core = project._local_dims_case()
    assert os.path.abspath(core.CORE_ROOT) == os.path.abspath(project._REPO_ROOT)


@pytest.mark.parametrize("visibility", ["private", "public"])
def test_a_new_study_is_a_real_case_repo(tmp_path, visibility):
    out = str(tmp_path / "study")
    report = project.create_project(out, visibility)

    assert report["visibility"] == visibility
    assert project.is_template_dir(out)
    for rel in ("index.html", "serve.py", "vendor/dims-core", "vendor/dims-tabs",
                "dims-case.json", ".github/workflows/ci.yml"):
        assert os.path.exists(os.path.join(out, rel)), f"missing {rel}"

    case = json.load(open(os.path.join(out, "dims-case.json")))
    assert case["visibility"] == visibility
    assert case["dimsCore"] == report["dims_core"]
    assert case["vendorHashes"], "no pin recorded, so nothing can verify the core"
    # One list, read by every guard. An earlier example omitted it and the study
    # written from it declared itself private and blocked nothing.
    assert case["restricted"], "no restricted list"


def test_a_private_study_gets_the_guards_and_is_told_about_the_hooks(tmp_path):
    """The four guards in docs/contracts/data-visibility.md, and the one thing
    no tool can do for the user: hooks are per-clone."""
    out = str(tmp_path / "private")
    report = project.create_project(out, "private")

    assert os.path.isdir(os.path.join(out, ".githooks"))
    assert os.path.exists(os.path.join(out, ".github", "workflows", "privacy.yml"))
    assert os.path.exists(os.path.join(out, "data.local.json.example"))
    assert "restricted" in open(os.path.join(out, ".gitignore")).read() or \
        "assets/videos" in open(os.path.join(out, ".gitignore")).read()
    assert "core.hooksPath" in (report["hooks_command"] or "")


def test_a_public_study_gets_pages_and_no_privacy_workflow(tmp_path):
    out = str(tmp_path / "public")
    report = project.create_project(out, "public")
    wf = os.path.join(out, ".github", "workflows")
    assert os.path.exists(os.path.join(wf, "pages.yml"))
    assert not os.path.exists(os.path.join(wf, "privacy.yml"))
    assert report["hooks_command"] is None


def test_visibility_must_be_declared_not_guessed(tmp_path):
    with pytest.raises(project.ProjectError, match="private"):
        project.create_project(str(tmp_path / "s"), "maybe")


def test_a_folder_that_is_not_a_study_is_refused(tmp_path):
    junk = tmp_path / "junk"
    junk.mkdir()
    (junk / "notes.txt").write_text("hello")
    with pytest.raises(project.ProjectError, match="not empty"):
        project.create_project(str(junk))


# --- reopening --------------------------------------------------------------

def test_a_built_study_reopens_as_what_it_was(tmp_path):
    """Reading a study back is what turns this from a generator into something a
    researcher returns to. Without it the first correction after a build sends
    them into config.json by hand."""
    out = str(tmp_path / "study")
    project.create_project(out, "private")
    ts = os.path.join(out, "assets", "timeseries")
    os.makedirs(ts, exist_ok=True)
    for name in ("s1_alpha.csv", "s1_beta.csv"):
        with open(os.path.join(ts, name), "w") as fh:
            fh.write("Time,value\n0,1\n0.05,2\n")
    project.write_config(out, {
        "title": "Reopened", "videoIDs": ["s1"], "dataTypes": {"s1": ["alpha", "beta"]},
        "include_RQA": ["alpha"], "include_network": True,
        "analysis": {"rqa": {"window": 6}},
    })

    found = project.read_project(out)
    assert found["visibility"] == "private"
    assert found["config"]["title"] == "Reopened"
    assert found["config"]["include_network"] is True
    assert found["config"]["analysis"] == {"rqa": {"window": 6}}
    names = sorted(a["name"] for a in found["assets"])
    assert names == ["s1_alpha.csv", "s1_beta.csv"]
    # The session and measure come back from the filename, which is the
    # interface docs/contracts/assets.md defines.
    alpha = next(a for a in found["assets"] if a["name"] == "s1_alpha.csv")
    assert (alpha["videoID"], alpha["dataType"]) == ("s1", "alpha")


def test_reopening_something_that_is_not_a_study_says_so(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(project.ProjectError, match="not a DIMS study"):
        project.read_project(str(plain))


# --- the config -------------------------------------------------------------

def test_the_written_config_matches_the_contract(tmp_path):
    """The builder validates against the same schema CI validates every study
    against, so it cannot write a config the core would reject -- a failure that
    otherwise surfaces much later as an empty tab."""
    out = str(tmp_path / "study")
    project.create_project(out, "private")
    project.write_config(out, {
        "title": "T", "videoIDs": ["s1"], "dataTypes": {"s1": ["a", "b"]},
        "include_RQA": ["a"], "include_crosswavelet": [["a", "b"]],
        "include_network": {"groups": [{"match": "^a", "label": "A"}], "band": [0.5, 8]},
        "perspectives": ["wide", "close"],
        "videoSrcTemplate": "assets/videos/{videoID}_{persp}.mp4",
        "analysis": {"crosswavelet": {"mcCount": 100}, "rqa": {"targetRecurrence": 0.07}},
    })
    written = json.load(open(os.path.join(out, "config.json")))
    assert project.schema_problems(written) == []
    assert written["include_network"]["groups"][0]["match"] == "^a"
    assert written["perspectives"] == ["wide", "close"]


def test_a_config_the_core_would_reject_is_refused(tmp_path):
    out = str(tmp_path / "study")
    project.create_project(out, "private")
    with pytest.raises(project.ProjectError, match="videoIDs"):
        project.write_config(out, {"videoIDs": "s1", "dataTypes": {}})


def test_untouched_optional_keys_are_left_out(tmp_path):
    """`perspectives: []` beside `videoSrcTemplate: ""` reads as a study that
    considered multi-camera and declined. It did not; nobody was asked."""
    out = str(tmp_path / "study")
    project.create_project(out, "private")
    project.write_config(out, {"title": "T", "videoIDs": ["s1"],
                               "dataTypes": {"s1": ["a"]}})
    written = json.load(open(os.path.join(out, "config.json")))
    for absent in ("perspectives", "videoSrcTemplate", "include_network", "analysis"):
        assert absent not in written, f"{absent} was written without being set"
    # A switch with two meanings keeps both: off is a decision.
    assert written["include_elan"] is False
