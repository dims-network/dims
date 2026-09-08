"""The tracked record of assets a private study cannot otherwise describe."""
import json
import os

from dims_analysis.common import manifest as mf


def study(tmp_path, files=(("timeseries/a.csv", "t,x\n0,1\n"),
                           ("videos/v1.mp4", "pretend video"))):
    root = tmp_path / "case"
    for rel, content in files:
        path = root / "assets" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return str(root)


def test_a_manifest_records_names_sizes_and_checksums(tmp_path):
    m = mf.write(study(tmp_path))
    assert set(m["files"]) == {"timeseries/a.csv", "videos/v1.mp4"}
    entry = m["files"]["videos/v1.mp4"]
    assert entry["bytes"] == len("pretend video")
    assert len(entry["sha256"]) == 64


def test_a_manifest_holds_no_content(tmp_path):
    """The reason the hook and the CI guard exempt this file by name."""
    secret = "the participant's name is in this file"
    dest = study(tmp_path, files=(("transcripts/t1.txt", secret),))
    mf.write(dest)
    assert secret not in open(mf.path_for(dest)).read()


def test_the_manifest_is_tracked_in_the_repo_not_beside_the_data(tmp_path):
    """Assets are external on a private study; the record of them is not."""
    dest = tmp_path / "case"
    (dest / "assets").mkdir(parents=True)
    external = tmp_path / "elsewhere"
    (external / "timeseries").mkdir(parents=True)
    (external / "timeseries" / "a.csv").write_text("t,x\n")
    (dest / "data.local.json").write_text(json.dumps({"assetsRoot": str(external)}))

    m = mf.write(str(dest))
    assert m["assetsExternal"] is True
    assert list(m["files"]) == ["timeseries/a.csv"]
    assert os.path.exists(dest / "assets" / "MANIFEST.json")
    assert not os.path.exists(external / "MANIFEST.json")
    # And it does not record where that is: on a private study the path names
    # somebody's home directory.
    assert str(external) not in open(mf.path_for(str(dest))).read()


def test_a_missing_file_is_reported(tmp_path):
    dest = study(tmp_path)
    mf.write(dest)
    os.remove(os.path.join(dest, "assets", "videos", "v1.mp4"))
    missing, changed, extra = mf.compare(dest)
    assert missing == ["videos/v1.mp4"]
    assert changed == [] and extra == []


def test_a_truncated_file_is_caught_without_reading_it(tmp_path):
    """The cheap check exists so that it actually gets run on video."""
    dest = study(tmp_path)
    mf.write(dest)
    open(os.path.join(dest, "assets", "timeseries", "a.csv"), "w").write("t\n")
    missing, changed, extra = mf.compare(dest, deep=False)
    assert changed == ["timeseries/a.csv"]


def test_a_same_size_edit_needs_the_deep_check(tmp_path):
    dest = study(tmp_path)
    mf.write(dest)
    path = os.path.join(dest, "assets", "timeseries", "a.csv")
    open(path, "w").write("t,x\n0,9\n")     # same length, different content
    assert mf.compare(dest, deep=False)[1] == []
    assert mf.compare(dest, deep=True)[1] == ["timeseries/a.csv"]


def test_a_manifest_without_checksums_does_not_claim_changes_it_cannot_see(tmp_path):
    """`--deep` against a size-only manifest must not report every file."""
    dest = study(tmp_path)
    mf.write(dest, deep=False)
    open(os.path.join(dest, "assets", "timeseries", "a.csv"), "w").write("t,x\n0,9\n")
    assert mf.compare(dest, deep=True)[1] == []


def test_an_extra_file_is_listed_but_is_not_a_failure(tmp_path):
    dest = study(tmp_path)
    mf.write(dest)
    open(os.path.join(dest, "assets", "scratch.txt"), "w").write("working file")
    missing, changed, extra = mf.compare(dest)
    assert extra == ["scratch.txt"] and not missing and not changed


def test_placeholders_are_not_assets(tmp_path):
    dest = study(tmp_path, files=(("videos/.gitkeep", ""),
                                  ("videos/v1.mp4", "x")))
    assert list(mf.write(dest)["files"]) == ["videos/v1.mp4"]


def test_no_manifest_is_distinguishable_from_an_empty_one(tmp_path):
    dest = study(tmp_path)
    assert mf.compare(dest) is None
