"""Step discovery.

Steps are found through the ``dims.steps`` entry point group. Nothing here
lists them, so adding one — including from a completely separate package —
requires no change to this file.
"""
from __future__ import annotations

from importlib.metadata import entry_points

GROUP = "dims.steps"


def discover(problems: list | None = None) -> dict:
    """Return {id: Step instance} for every registered step.

    A step that fails to import is reported and skipped rather than taking the
    whole run down with it: one broken third-party module should not stop the
    analyses that do work. But "skipped" must not read as "fine" — a missing
    pycwt used to mean the only analysis a config asked for never ran, with a
    warning in the log and an exit code of 0. Pass a list to collect the
    failures so the caller can decide; the caller that matters is the CLI, which
    fails if a step the config *asked for* is among them.
    """
    found: dict = {}
    failures: list = []
    seen_ids: dict = {}
    for ep in entry_points(group=GROUP):
        try:
            step = ep.load()()
        except Exception as exc:  # noqa: BLE001 - report and continue
            failures.append((ep.name, exc))
            continue
        sid = step.id or ep.name
        # Two installed distributions can register the same id -- e.g. a stale
        # dims-network alongside an editable dims-analysis. Silently keeping the
        # last one makes which code runs depend on iteration order.
        prior = seen_ids.get(sid)
        if prior is not None and prior != _origin(ep):
            print(f"warning: step '{sid}' is registered by more than one "
                  f"distribution ({prior}, {_origin(ep)}); using the first")
            continue
        seen_ids[sid] = _origin(ep)
        found[sid] = step
    for name, exc in failures:
        print(f"warning: step '{name}' could not be loaded: {exc}")
    if problems is not None:
        problems.extend(failures)
    return found


def _origin(ep) -> str:
    """Which distribution an entry point came from, for the duplicate warning."""
    dist = getattr(ep, "dist", None)
    return getattr(dist, "name", None) or "unknown"
