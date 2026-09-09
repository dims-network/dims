"""What the wizard refuses to accept, and what it merely warns about.

192 lines of validation that no test imported. It was reached only when a
`server.py` request happened to route through it, so which message a bad file
produces -- the whole point of the module -- was asserted nowhere.

The distinction these tests care about is error versus warning. The wizard's
failures are all of one kind: something is quietly not there and the person
using it is least able to work out why. A file the dashboard cannot read must
be an error, and a file it can read but probably should not is a warning.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dims_builder import validate  # noqa: E402


def levels(issues):
    return [i["level"] for i in issues]


def messages(issues):
    return " ".join(i["message"] for i in issues)


# --- time-series CSV ---------------------------------------------------------

def test_a_usable_csv_raises_nothing(tmp_path):
    p = tmp_path / "ok.csv"
    p.write_text("Time,bodysync\n0.0,1.0\n0.1,1.4\n")
    assert validate.validate_csv(str(p)) == []


def test_the_time_column_is_matched_under_any_casing(tmp_path):
    """The host matches it case-insensitively, so the wizard must agree.

    Disagreeing here rejects a file the dashboard would have read.
    """
    for header in ("time", "TIME", " Time "):
        p = tmp_path / "c.csv"
        p.write_text(f"{header},v\n0.0,1.0\n")
        assert validate.validate_csv(str(p)) == [], header


def test_a_csv_with_no_time_column_is_an_error(tmp_path):
    p = tmp_path / "notime.csv"
    p.write_text("frame,value\n1,2\n")
    issues = validate.validate_csv(str(p))
    assert "error" in levels(issues)
    assert "Time" in messages(issues)


def test_a_csv_with_only_a_time_column_is_an_error(tmp_path):
    """A time axis and nothing on it is not a time series."""
    p = tmp_path / "bare.csv"
    p.write_text("Time\n0.0\n0.1\n")
    issues = validate.validate_csv(str(p))
    assert "error" in levels(issues)
    assert "measurement column" in messages(issues)


def test_a_header_with_no_rows_is_an_error(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text("Time,v\n")
    issues = validate.validate_csv(str(p))
    assert "error" in levels(issues)
    assert "no data rows" in messages(issues)


def test_an_empty_file_is_an_error_and_not_a_crash(tmp_path):
    p = tmp_path / "nothing.csv"
    p.write_text("")
    issues = validate.validate_csv(str(p))
    assert levels(issues) == ["error"]


def test_a_missing_file_is_reported_rather_than_raised(tmp_path):
    """The caller is an HTTP handler; an exception here is a 500 page."""
    issues = validate.validate_csv(str(tmp_path / "absent.csv"))
    assert levels(issues) == ["error"]
    assert "Could not read" in messages(issues)


# --- ELAN ---------------------------------------------------------------------

def test_a_file_that_is_not_xml_is_an_error(tmp_path):
    p = tmp_path / "bad.eaf"
    p.write_text("this is not xml at all")
    assert "error" in levels(validate.validate_eaf(str(p)))


# --- dispatch ------------------------------------------------------------------

def test_an_unknown_role_validates_nothing_rather_than_raising(tmp_path):
    p = tmp_path / "x.bin"
    p.write_text("anything")
    assert validate.validate_file("something-else", str(p)) == []


def test_each_known_role_reaches_its_own_validator(tmp_path):
    """The dispatch table, which is the only thing server.py calls."""
    p = tmp_path / "notime.csv"
    p.write_text("frame,value\n1,2\n")
    assert "error" in levels(validate.validate_file("timeseries", str(p)))
