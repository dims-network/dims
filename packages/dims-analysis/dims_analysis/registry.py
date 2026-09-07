"""Step discovery.

Steps are found through the ``dims.steps`` entry point group. Nothing here
lists them, so adding one — including from a completely separate package —
requires no change to this file.
"""
from __future__ import annotations

from importlib.metadata import entry_points

GROUP = "dims.steps"


def discover() -> dict:
    """Return {id: Step instance} for every registered step.

    A step that fails to import is reported and skipped rather than taking the
    whole run down with it: one broken third-party module should not stop the
    analyses that do work.
    """
    found: dict = {}
    problems: list = []
    for ep in entry_points(group=GROUP):
        try:
            step = ep.load()()
        except Exception as exc:  # noqa: BLE001 - report and continue
            problems.append((ep.name, exc))
            continue
        found[step.id or ep.name] = step
    if problems:
        for name, exc in problems:
            print(f"warning: step '{name}' could not be loaded: {exc}")
    return found
