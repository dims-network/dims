"""Reading one of a study's time series. One rule, one implementation.

Four rules shipped at once. Only one sorted by time; the minimum length was 10
in two steps and 50 in a third; one raised on a missing Time column and the
others printed and returned None. So two analyses of the same CSV could disagree
about what the data was, and on out-of-order timestamps only cross-RQA would
have been right.

None of the 93 time series in the studies is currently out of order, so
consolidating changes no number today. It is a guard against the file that is,
which would otherwise produce a plausible-looking wrong answer in three of the
four readers.
"""
from __future__ import annotations

import pandas as pd

TIME = "Time"


class SeriesError(Exception):
    """The CSV is not a usable time series. The message says why."""


def time_column(df) -> str | None:
    """The time column under any casing or surrounding whitespace."""
    for c in df.columns:
        if str(c).strip().lower() == "time":
            return c
    return None


def load(path: str, min_points: int = 0, value_column: str | None = None):
    """Return (time, values) as float arrays: NaNs dropped, sorted by time.

    Raises SeriesError rather than returning a sentinel, so a caller cannot
    forget to check. Callers that want the old behaviour use load_or_none.
    """
    try:
        df = pd.read_csv(path)
    except FileNotFoundError:
        raise SeriesError(f"file not found: {path}") from None
    except Exception as exc:  # noqa: BLE001 - a malformed CSV is a data problem
        raise SeriesError(f"could not read {path}: {exc}") from None

    tcol = time_column(df)
    if tcol is None:
        raise SeriesError(f"{path} has no 'Time' column (found: {list(df.columns)})")
    df = df.rename(columns={tcol: TIME})

    if value_column is None:
        others = [c for c in df.columns if c != TIME]
        if not others:
            raise SeriesError(f"{path} has a Time column and nothing else")
        value_column = others[0]
    elif value_column not in df.columns:
        raise SeriesError(f"{path} has no column {value_column!r}")

    sub = df[[TIME, value_column]].dropna().sort_values(TIME)
    if len(sub) < min_points:
        raise SeriesError(
            f"{path} has {len(sub)} usable points, fewer than the {min_points} "
            f"this analysis needs")
    return sub[TIME].values.astype(float), sub[value_column].values.astype(float)


def load_or_none(path: str, min_points: int = 0, prefix: str = "  "):
    """load(), reporting the problem and returning None instead.

    For the steps, which continue to the next data type rather than stopping.
    The runner notices a step that produced nothing, so this no longer hides a
    failed run.

    It returns None, not (None, None). The pair was worse than it looks: the
    obvious guard, `if load_or_none(...) is None`, was then always false, and a
    caller who wrote it got an AttributeError several lines later instead of a
    skip. A function whose name says None has to return None.
    """
    try:
        return load(path, min_points)
    except SeriesError as exc:
        print(f"{prefix}Warning: {exc}")
        return None
