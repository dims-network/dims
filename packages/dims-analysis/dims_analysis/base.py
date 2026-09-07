"""The step contract.

A step reads time series and writes something the dashboard can draw. It
declares which config key gates it and where its output goes; the runner does
the rest. Full contract, with the acceptance checks: ``docs/contracts/step.md``.
"""
from __future__ import annotations

import json
import os


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

    def output_path(self, step: "Step", video_id: str) -> str:
        d = self._output_dir or self.path(step.output_dir)
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, step.output_name.format(video_id=video_id))

    # -- results -------------------------------------------------------------
    def write_result(self, step: "Step", video_id: str, payload: dict) -> str:
        """Write the browser payload, merging with anything already there.

        Merging rather than clobbering is deliberate: one fork had to maintain
        its own copy of a whole step purely because the shared version
        overwrote the output that a second, complementary analysis had written.
        """
        p = self.output_path(step, video_id)
        merged = {"video_id": video_id}
        if os.path.exists(p):
            try:
                with open(p) as fh:
                    existing = json.load(fh)
                if isinstance(existing, dict):
                    merged.update(existing)
            except (OSError, ValueError):
                pass  # unreadable output is replaced, not preserved
        merged.update(payload)
        with open(p, "w") as fh:
            json.dump(merged, fh, indent=2)
        return p

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

    def gate(self, config: dict) -> bool:
        """Whether to run at all. Default: the config key is present and truthy."""
        return bool(config.get(self.config_key))

    def run(self, config: dict, ctx: StepContext) -> None:
        raise NotImplementedError

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Step {self.id}>"
