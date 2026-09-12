"""The step contract.

A step reads time series and writes something the dashboard can draw. It
declares which config key gates it and where its output goes; the runner does
the rest. Full contract, with the acceptance checks: ``docs/contracts/step.md``.
"""
from __future__ import annotations

import json
import os

from dims_analysis.common import assets, results


class StepContext:
    """Everything a step is allowed to touch outside its own module.

    Steps must go through this rather than reading and writing paths directly.
    Two of the scripts this package absorbed hardcoded ``./config.json`` and
    their own input directories, which is why they could only ever run from one
    working directory.
    """

    def __init__(self, project_dir: str, config: dict, output_dir: str | None = None):
        self.project_dir = os.path.abspath(project_dir)
        self.config = config
        self._output_dir = output_dir

    # -- paths ---------------------------------------------------------------
    def path(self, *parts: str) -> str:
        return os.path.join(self.project_dir, *parts)

    def output_dir_for(self, step: "Step") -> str:
        """Where this step's output belongs. No side effects.

        Resolved through data.local.json, so a private study -- whose assets
        live outside the repository -- gets the same answer here as the step
        itself computes. An explicit --output-dir is the caller being specific
        and is never rewritten.
        """
        if self._output_dir:
            return self._output_dir
        d = assets.resolve(step.output_dir, self.project_dir)
        return d if os.path.isabs(d) else self.path(d)

    def input_dir(self, relative: str) -> str:
        """Where a step reads from, absolute. The counterpart of output_dir_for.

        Same two rules: `data.local.json` may send `assets/...` outside the
        repository, and anything still relative is relative to the *project*,
        not to the working directory. Steps used to get the second rule by
        chdir-ing into the project before running, which is process-global and
        made them unusable from a threaded caller -- and it is what let one
        project's resolved input path leak into the next.
        """
        d = assets.resolve(relative, self.project_dir)
        return d if os.path.isabs(d) else self.path(d)

    def output_path(self, step: "Step", video_id: str) -> str:
        d = self.output_dir_for(step)
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, step.output_name.format(video_id=video_id))

    def output_snapshot(self, step: "Step") -> dict:
        """{path: mtime} for the step's output directory, for before/after use.

        Comparing snapshots rather than timestamps against a clock start avoids
        depending on filesystem timestamp granularity, and catches a rewritten
        file as well as a new one.
        """
        d = self.output_dir_for(step)
        snap: dict = {}
        try:
            names = os.listdir(d)
        except OSError:
            return snap
        for name in names:
            full = os.path.join(d, name)
            try:
                if os.path.isfile(full):
                    snap[full] = os.stat(full).st_mtime_ns
            except OSError:
                continue
        return snap

    # -- results -------------------------------------------------------------
    def write_result(self, step: "Step", video_id: str, payload: dict) -> dict:
        """Write the browser payload, merging with anything already there.

        Merging rather than clobbering is deliberate: one fork had to maintain
        its own copy of a whole step purely because the shared version
        overwrote the output that a second, complementary analysis had written.

        The step's id goes down as the owner of every entry it writes, which is
        what lets the next run of this same step remove the entries it no
        longer produces without touching that second analysis's.

        Returns the {"kept": ..., "replaced": ..., "pruned": ...} report, so the
        caller can say what happened -- a silent keep leaves stale results in a
        file that looks freshly written. Use `step_io.report_merge` to print it.

        It writes compactly, as the steps' own `main()` does. It did not, and
        that mattered the moment anything called it: two entry points into one
        analysis must not produce two different files, and indent=2 is a quarter
        of a payload nobody reads by eye.
        """
        p = self.output_path(step, video_id)
        body = {"video_id": video_id}
        body.update(payload)
        return results.write_payload(p, body, owner=step.id or None,
                                     expected=step.expected_entries(self.config))

    def params(self, step: "Step", defaults: dict) -> dict:
        """Per-step tuning from config.json, falling back to the step's defaults.

        Tuning that lives only as a module constant cannot vary per study
        without editing the source — which is exactly how a fork ends up
        maintaining its own copy of an analysis.
        """
        given = (self.config.get("analysis") or {}).get(step.id) or {}
        out = dict(defaults)
        out.update(given)
        return out


class Step:
    """Base class for an analysis. Subclass, set the attributes, implement run()."""

    #: short identifier, also the CLI selector
    id: str = ""
    #: key in config.json that switches this step on
    config_key: str = ""
    #: default output directory, relative to the project
    output_dir: str = ""
    #: output filename template
    output_name: str = "{video_id}_data.json"
    #: one line, shown by `dims-analysis list`
    description: str = ""
    #: further files this step writes, same `{video_id}` shape as output_name.
    #: `dims-analysis prune` walks these too -- cross-wavelet's second,
    #: full-resolution file is keyed by the same pairs as the first, and a
    #: prune that cleaned one and not the other would leave the two disagreeing
    #: about which pairs the study has.
    extra_output_names: tuple = ()

    def expected_entries(self, config: dict) -> dict:
        """{payload key: the entry names this config asks for}, or {}.

        Two things read this. `write_result` passes it to the writer, which is
        what lets a re-run remove the entries this step wrote for a question
        the config no longer asks -- the cross-wavelet pairs of a person who
        was removed in the wizard, say. And `dims-analysis prune` uses it to
        clear the same entries out of a study built before any of this existed.

        The default is {}, which means "cannot say": such a step's entries are
        stamped with nobody and removed by nothing, which is the safe end of
        the trade -- a study-owned analysis sharing a file with a shipped step
        must not lose its results to a guess. Answer it to opt in.
        """
        return {}

    def gate(self, config: dict) -> bool:
        """Whether to run at all. Default: the config key is present and truthy.

        Matched case-insensitively, because the three gate keys use three
        different conventions -- `include_RQA`, `include_cRQA`,
        `include_crosswavelet` -- and `build_assets.py` already matched loosely.
        A study writing `include_crqa` was reported as enabled by one and
        skipped in silence by the other.
        """
        from dims_analysis.common import config as _config
        return _config.enabled(config, self.config_key)

    def run(self, config: dict, ctx: StepContext) -> None:
        raise NotImplementedError

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Step {self.id}>"
