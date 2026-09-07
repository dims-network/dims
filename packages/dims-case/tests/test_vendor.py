"""The vendored-core check, which is the whole reason a study may pin a version.

A study carries a copy of the core rather than a dependency on it, so the copy
is only meaningful if something proves it is unmodified. There are two ways to
prove it and they are not equally strong; these tests pin down the difference,
because CI relies on it.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dims_case.core import VENDOR, _write_vendor, verify_vendor  # noqa: E402


def make_study(tmp_path, version="1.3.0"):
    """The vendored part of a study, as `dims-case new` would write it."""
    dest = str(tmp_path / "case-x")
    os.makedirs(dest)
    hashes = _write_vendor(dest)
    with open(os.path.join(dest, "dims-case.json"), "w") as fh:
        json.dump({"case": "x", "visibility": "public", "dimsCore": version,
                   "vendorHashes": hashes}, fh)
    return dest


def rehash(dest):
    """Re-record the hashes, the way a careless `sync` against a fork would."""
    from dims_case.core import _dir_hash
    path = os.path.join(dest, "dims-case.json")
    case = json.load(open(path))
    case["vendorHashes"] = {rel: _dir_hash(os.path.join(dest, rel))
                            for rel in VENDOR.values()}
    json.dump(case, open(path, "w"))


def test_a_freshly_vendored_study_passes_both_checks(tmp_path):
    dest = make_study(tmp_path)
    assert verify_vendor(dest) == []
    assert verify_vendor(dest, strict=True) == []


def test_an_edited_file_is_caught(tmp_path):
    dest = make_study(tmp_path)
    with open(os.path.join(dest, "vendor", "dims-core", "dims-core.js"), "a") as fh:
        fh.write("\n// local tweak\n")
    assert verify_vendor(dest), "an edit to vendored code must be reported"
    assert verify_vendor(dest, strict=True)


def test_an_edit_that_covers_its_tracks_needs_the_release(tmp_path):
    """The reason CI does not simply run the offline check.

    Editing vendored code and then re-recording the hashes leaves a study that
    agrees with itself: both sides of the offline comparison live in the repo.
    Only rebuilding vendor/ from the core can tell the difference, so this is
    the case that decides which check CI has to run.
    """
    dest = make_study(tmp_path)
    with open(os.path.join(dest, "vendor", "dims-tabs", "rqa.js"), "a") as fh:
        fh.write("\n// local tweak\n")
    rehash(dest)

    assert verify_vendor(dest) == [], "offline check cannot see this, by design"
    problems = verify_vendor(dest, strict=True)
    assert problems and "vendor/dims-tabs" in problems[0]


def test_a_stale_recorded_hash_is_reported_even_when_the_bytes_are_right(tmp_path):
    """Otherwise the offline check would pass or fail for the wrong reason."""
    dest = make_study(tmp_path)
    path = os.path.join(dest, "dims-case.json")
    case = json.load(open(path))
    case["vendorHashes"]["vendor/dims-core"] = "0" * 64
    json.dump(case, open(path, "w"))

    problems = verify_vendor(dest, strict=True)
    assert len(problems) == 1
    assert "records a different hash" in problems[0]


def test_a_missing_vendor_directory_is_reported(tmp_path):
    import shutil
    dest = make_study(tmp_path)
    shutil.rmtree(os.path.join(dest, "vendor", "dims-tabs"))
    assert any("missing" in p for p in verify_vendor(dest, strict=True))


def test_vendor_carries_only_what_a_dashboard_loads(tmp_path):
    """CI compares vendor/ against a rebuild, so what is left out is contract.

    A `diff -r` in the workflow would have to repeat this exclusion list and
    would drift from it. It does not: the rule lives in `_write_vendor`, and
    this is the test that keeps it honest. Test harnesses, their dependencies
    and documentation are development material -- shipping them into every
    study would put a jsdom tree in each of them.
    """
    dest = make_study(tmp_path)
    for rel in VENDOR.values():
        for root, dirs, files in os.walk(os.path.join(dest, rel)):
            assert "test" not in dirs
            assert "node_modules" not in dirs
            assert [f for f in files if f.endswith(".md")] == []
