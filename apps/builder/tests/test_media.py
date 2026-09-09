"""The wizard's file handling, below the parts that need ffmpeg.

274 lines that no test imported. `trim_video` and `pad_timeseries` need an
ffmpeg binary and are left to the integration path, but everything that decides
*what* to do -- which column is time, where a series starts and stops, what a
column is called once it becomes a filename -- is pure and was untested.

`split_timeseries_csv` matters most: it is what turns one uploaded multi-column
CSV into the one-column files the dashboard actually reads, and getting a name
or a time column wrong there produces a study whose tabs are simply empty.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dims_builder import media  # noqa: E402


# --- the time column ----------------------------------------------------------

def test_the_time_column_is_found_under_any_casing_or_padding():
    """The dashboard's canonical name is `Time`; a user's export rarely is."""
    for columns, expected in (
        (["Time", "a"], "Time"),
        (["time", "a"], "time"),
        (["TIME", "a"], "TIME"),
        ([" Time ", "a"], " Time "),
    ):
        assert media.time_key(columns) == expected, columns


def test_no_time_column_is_none_rather_than_a_guess():
    assert media.time_key(["frame", "value"]) is None
    assert media.time_key([]) is None
    assert media.time_key(None) is None
    assert media.time_key([None, "value"]) is None


# --- the extent of a series ---------------------------------------------------

def test_series_bounds_reports_the_span_and_the_sample_interval(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("Time,v\n0.0,1\n0.1,2\n0.2,3\n0.3,4\n")
    b = media.series_bounds(str(p))
    assert b["min"] == pytest.approx(0.0)
    assert b["max"] == pytest.approx(0.3)
    assert b["step"] == pytest.approx(0.1)
    assert b["rows"] == 4


def test_the_step_is_a_median_so_one_gap_does_not_define_it(tmp_path):
    """A dropped frame is common; it must not become the sample interval."""
    p = tmp_path / "gap.csv"
    p.write_text("Time,v\n0.0,1\n0.1,2\n0.2,3\n5.0,4\n0.3,5\n")
    assert media.series_bounds(str(p))["step"] == pytest.approx(0.1)


def test_rows_out_of_order_do_not_move_the_bounds(tmp_path):
    p = tmp_path / "unsorted.csv"
    p.write_text("Time,v\n0.2,3\n0.0,1\n0.1,2\n")
    b = media.series_bounds(str(p))
    assert (b["min"], b["max"]) == (pytest.approx(0.0), pytest.approx(0.2))


def test_a_series_with_no_rows_is_none_rather_than_a_zero_span(tmp_path):
    """None says "there is nothing here"; {min: 0, max: 0} says "it is empty
    and starts at zero", which the caller cannot tell from a real recording."""
    p = tmp_path / "none.csv"
    p.write_text("Time,v\n")
    assert media.series_bounds(str(p)) is None


def test_a_single_row_has_no_interval_to_measure(tmp_path):
    p = tmp_path / "one.csv"
    p.write_text("Time,v\n1.5,9\n")
    b = media.series_bounds(str(p))
    assert b["rows"] == 1 and b["step"] == 0.0
    assert b["min"] == b["max"] == pytest.approx(1.5)


# --- names that become filenames ----------------------------------------------

def test_a_column_name_becomes_a_safe_filename_token():
    assert media.slug("Body Sync") == "Body_Sync"
    assert media.slug("  spaced  ") == "spaced"
    assert media.slug("a/b\\c:d") == "a_b_c_d"


def test_a_name_that_slugs_to_nothing_still_gets_one():
    """The token ends up in a path; an empty one collides with every other."""
    assert media.slug("") == "col"
    assert media.slug("///") == "col"
    assert media.slug("   ") == "col"


# --- one upload becomes the files the dashboard reads --------------------------

def test_a_multi_column_upload_becomes_one_file_per_measurement(tmp_path):
    staging = tmp_path / "staging"
    staging.mkdir()
    src = tmp_path / "upload.csv"
    src.write_text("Time,Body Sync,neural\n0.0,1,10\n0.1,2,20\n")

    produced = media.split_timeseries_csv(str(src), str(staging), "fid", "rec1")

    assert len(produced) == 2, produced
    assert [item["dataType"] for item in produced] == ["Body_Sync", "neural"]
    for item in produced:
        assert os.path.exists(item["path"])
        header = open(item["path"]).readline().strip().split(",")
        # Time plus exactly one measurement: what the dashboard's reader wants.
        assert len(header) == 2 and header[0].lower() == "time"
        assert header[1] == item["column"]


def test_a_csv_with_no_time_column_splits_into_nothing(tmp_path):
    """Rather than writing files the dashboard would silently fail to read."""
    staging = tmp_path / "staging"
    staging.mkdir()
    src = tmp_path / "notime.csv"
    src.write_text("frame,value\n1,2\n")
    assert media.split_timeseries_csv(str(src), str(staging), "fid", "rec1") == []


def test_two_columns_that_slug_alike_get_distinct_data_types(tmp_path):
    """The dataType becomes a filename token and a config key.

    "Body Sync" and "Body/Sync" both slug to Body_Sync; letting them collide
    would silently leave the study one signal short, with the second having
    overwritten the first.
    """
    staging = tmp_path / "staging"
    staging.mkdir()
    src = tmp_path / "collide.csv"
    src.write_text("Time,Body Sync,Body/Sync\n0.0,1,2\n")
    produced = media.split_timeseries_csv(str(src), str(staging), "fid", "rec")
    types = [item["dataType"] for item in produced]
    assert types == ["Body_Sync", "Body_Sync_2"]
    assert len({item["path"] for item in produced}) == 2


def test_a_single_measurement_column_is_left_alone(tmp_path):
    """There is nothing to split, and the caller handles it as a normal upload.

    Splitting it anyway would rename the file for no reason.
    """
    staging = tmp_path / "staging"
    staging.mkdir()
    src = tmp_path / "one.csv"
    src.write_text("Time,only\n0.0,1\n")
    assert media.split_timeseries_csv(str(src), str(staging), "fid", "rec") == []
