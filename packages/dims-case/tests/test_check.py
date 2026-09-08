"""What `dims-case check` catches beyond an edited vendor/.

Two failures that v2.0.0 warns about in prose and that nothing enforced. Both
land on the study owner at the worst moment -- after a bump, in a browser, with
no message -- and both are cheap to detect from the study itself.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dims_case.core import (  # noqa: E402
    PAYLOAD_VERSION, shadowed_tabs, stale_assets,
)


def study(tmp_path, payload_version=PAYLOAD_VERSION, analyses=("rqa",)):
    """A study with assets committed, the way a public one is."""
    dest = tmp_path / "study"
    for name in analyses:
        d = dest / "assets" / name
        d.mkdir(parents=True)
        (d / f"v1_{name}_data.json").write_text(json.dumps({
            "video_id": "v1", "payload_version": payload_version,
            f"{name}_data": {"a": {}},
        }))
    return str(dest)


# --- assets that no longer match the core -----------------------------------

def test_assets_from_an_older_core_are_reported_with_the_fix(tmp_path):
    """The failure v2.0.0 exists to prevent, and the one it could not catch.

    A study that bumps `dimsCore` and does not rebuild has payloads no tab can
    read. The dashboard says so now, but only to whoever opens it -- and the
    person who bumped is not always the person who opens it.
    """
    problems = stale_assets(study(tmp_path, payload_version=1))
    assert problems, "an asset from an older core passed unnoticed"
    joined = " ".join(problems)
    assert "build_assets.py" in joined, "the report does not say how to fix it"
    assert "v1_rqa_data.json" in joined, "the report does not say which file"


def test_assets_from_a_newer_core_are_reported_too(tmp_path):
    """The other direction, and the opposite fix: the study is ahead of the
    core it pins, so rebuilding would make it worse."""
    problems = stale_assets(study(tmp_path, payload_version=PAYLOAD_VERSION + 1))
    assert problems
    assert "newer" in " ".join(problems).lower()


def test_current_assets_pass(tmp_path):
    """So the check cannot pass by refusing everything."""
    assert stale_assets(study(tmp_path)) == []


def test_a_study_with_no_committed_assets_is_not_an_error(tmp_path):
    """Every private study is this one: its data lives outside the repository,
    so there is nothing here to compare and that is correct, not missing."""
    dest = tmp_path / "private"
    (dest / "assets" / "rqa").mkdir(parents=True)
    (dest / "assets" / "rqa" / ".gitkeep").write_text("")
    assert stale_assets(str(dest)) == []


def test_a_payload_that_is_not_readable_is_reported_rather_than_skipped(tmp_path):
    dest = study(tmp_path)
    with open(os.path.join(dest, "assets", "rqa", "v1_rqa_data.json"), "w") as fh:
        fh.write("{ not json")
    problems = stale_assets(dest)
    assert problems and "could not be read" in " ".join(problems)


# --- a study tab that shadows a built-in ------------------------------------

def vendored(dest, *ids):
    d = os.path.join(dest, "vendor", "dims-tabs")
    os.makedirs(d, exist_ok=True)
    for tab in ids:
        with open(os.path.join(d, f"{tab}.js"), "w") as fh:
            fh.write("window.DIMS.registerTab({\n    id: '%s',\n    label: 'X',\n});\n" % tab)


def owned(dest, tab_id, filename=None):
    d = os.path.join(dest, "tabs")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, filename or f"{tab_id}.js"), "w") as fh:
        fh.write("window.DIMS.registerTab({ id: '%s', label: 'Mine' });\n" % tab_id)


def test_a_study_tab_that_collides_with_a_built_in_is_named(tmp_path):
    """`case-karnatak` is this case: its own network tab has the id v2.0.0's
    built-in claims. `registerTab` refuses the duplicate with a console.error
    nobody reads, so the study keeps a file that does nothing and the owner has
    no way to know which one they are looking at."""
    dest = str(tmp_path / "study")
    vendored(dest, "rqa", "network")
    owned(dest, "network")
    problems = shadowed_tabs(dest)
    assert problems, "a shadowed tab passed unnoticed"
    joined = " ".join(problems)
    assert "network" in joined
    assert "tabs/network.js" in joined, "the report does not name the file to delete"


def test_a_study_tab_with_its_own_id_is_fine(tmp_path):
    """The whole point of study-owned tabs. A check that flagged these would
    make the mechanism unusable."""
    dest = str(tmp_path / "study")
    vendored(dest, "rqa", "network")
    owned(dest, "trajectory")
    assert shadowed_tabs(dest) == []


def test_the_id_is_read_from_the_file_not_from_its_name(tmp_path):
    """A tab's id is what it registers, not what it is called -- `dims-core`
    keys on the id, so a differently-named file still collides."""
    dest = str(tmp_path / "study")
    vendored(dest, "network")
    owned(dest, "network", filename="cross_effector.js")
    problems = shadowed_tabs(dest)
    assert problems and "cross_effector.js" in " ".join(problems)


def test_a_study_with_no_tabs_of_its_own_is_fine(tmp_path):
    dest = str(tmp_path / "study")
    vendored(dest, "rqa")
    assert shadowed_tabs(dest) == []
