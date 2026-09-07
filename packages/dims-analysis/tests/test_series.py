"""Reading a study's time series. One rule, where there were four.

Only one of the four sorted by time; the length floor was 10 in two steps and
50 in a third; one raised on a missing Time column and the others returned a
sentinel. Two analyses of the same CSV could therefore disagree about what the
data was.
"""
import numpy as np
import pytest

from dims_analysis.common import series


def _csv(tmp_path, text, name="v1_alpha.csv"):
    p = tmp_path / name
    p.write_text(text)
    return str(p)


def test_rows_are_returned_in_time_order(tmp_path):
    """The divergence that mattered: only cross-RQA sorted, so given a file
    like this it and RQA analysed different signals."""
    path = _csv(tmp_path, "Time,value\n2.0,20\n0.0,0\n1.0,10\n")
    t, v = series.load(path)
    assert list(t) == [0.0, 1.0, 2.0]
    assert list(v) == [0, 10, 20]


def test_the_time_column_is_found_under_any_casing(tmp_path):
    for header in ("time", " TIME ", "Time"):
        path = _csv(tmp_path, f"value,{header}\n1,0.0\n2,1.0\n", name=f"{header.strip()}.csv")
        t, v = series.load(path)
        assert list(t) == [0.0, 1.0] and list(v) == [1, 2]


def test_nan_rows_are_dropped(tmp_path):
    path = _csv(tmp_path, "Time,value\n0,1\n1,\n2,3\n")
    t, v = series.load(path)
    assert list(t) == [0.0, 2.0]
    assert list(v) == [1.0, 3.0]


def test_a_missing_time_column_is_an_error_that_names_the_columns(tmp_path):
    path = _csv(tmp_path, "a,b\n1,2\n")
    with pytest.raises(series.SeriesError) as exc:
        series.load(path)
    assert "'Time'" in str(exc.value) and "['a', 'b']" in str(exc.value)


def test_a_missing_file_is_an_error_not_a_crash(tmp_path):
    with pytest.raises(series.SeriesError):
        series.load(str(tmp_path / "nope.csv"))


def test_the_length_floor_is_the_callers_to_state(tmp_path):
    path = _csv(tmp_path, "Time,value\n0,1\n1,2\n")
    assert len(series.load(path, min_points=2)[0]) == 2
    with pytest.raises(series.SeriesError) as exc:
        series.load(path, min_points=50)
    assert "fewer than the 50" in str(exc.value)


def test_load_or_none_reports_and_returns_a_pair(tmp_path, capsys):
    t, v = series.load_or_none(str(tmp_path / "missing.csv"))
    assert (t, v) == (None, None)
    assert "Warning:" in capsys.readouterr().out


def test_the_value_column_can_be_named(tmp_path):
    path = _csv(tmp_path, "Time,a,b\n0,1,9\n1,2,8\n")
    assert list(series.load(path, value_column="b")[1]) == [9, 8]
    assert list(series.load(path)[1]) == [1, 2], "default is the first non-Time column"


def test_the_steps_share_this_reader():
    from dims_analysis.steps import rqa, crqa
    assert rqa._series is crqa._series is series
