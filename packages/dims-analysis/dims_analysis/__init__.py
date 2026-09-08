"""DIMS analyses: the steps that turn time series into what the dashboard draws.

Steps are discovered through the ``dims.steps`` entry point group, so a step in
a separate package joins the pipeline without any change here. See
``docs/contracts/step.md``.
"""
__version__ = "2.0.1"

from dims_analysis.base import Step, StepContext  # noqa: F401
