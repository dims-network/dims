"""The step contract must hold for steps this package does not know about."""
from dims_analysis.base import Step, StepContext
from dims_analysis.registry import discover


def test_builtin_steps_are_discovered():
    steps = discover()
    for expected in ("rqa", "crqa", "crosswavelet"):
        assert expected in steps, f"{expected} not registered"


def test_gate_defaults_to_the_config_key():
    class S(Step):
        id = "x"
        config_key = "include_X"

    assert S().gate({"include_X": ["a"]}) is True
    assert S().gate({"include_X": []}) is False
    assert S().gate({}) is False


def test_write_result_merges_rather_than_clobbers(tmp_path):
    """One fork had to maintain its own copy of a whole step because the shared
    version overwrote what a complementary analysis had already written."""
    class S(Step):
        id = "s"
        output_dir = "out"
        output_name = "{video_id}_data.json"

    ctx = StepContext(str(tmp_path), {}, output_dir=str(tmp_path / "out"))
    step = S()
    ctx.write_result(step, "v1", {"first": 1})
    ctx.write_result(step, "v1", {"second": 2})

    import json
    with open(ctx.output_path(step, "v1")) as fh:
        data = json.load(fh)
    assert data["first"] == 1 and data["second"] == 2
    assert data["video_id"] == "v1"


def test_params_let_config_override_step_defaults():
    class S(Step):
        id = "rqa"

    ctx = StepContext(".", {"analysis": {"rqa": {"window": 5.0}}})
    p = ctx.params(S(), {"window": 20.0, "step": 1.0})
    assert p["window"] == 5.0 and p["step"] == 1.0


def test_crosswavelet_tuning_comes_from_config(tmp_path):
    """A study must be able to change these without forking the script.

    Karnatak previously maintained its own copy of the entire cross-wavelet
    step in order to change two numbers -- a period cap and a scale-averaging
    band. That copy is why the coherence fix could not travel back upstream for
    months.
    """
    import importlib.util, os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(here, "dims_analysis", "steps", "crosswavelet.py")
    spec = importlib.util.spec_from_file_location("cw_under_test", path)
    cw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cw)

    assert cw._tuning({}) == {}, "no tuning means module defaults"
    cfg = {"analysis": {"crosswavelet": {"maxPeriod": 12.0, "scaleAvgBand": [0.0, 12.0]}}}
    assert cw._tuning(cfg)["maxPeriod"] == 12.0
    assert cw._tuning(cfg)["scaleAvgBand"] == [0.0, 12.0]

    # and the cap actually reaches the transform
    import inspect
    assert "max_period" in inspect.signature(cw.compute_cross_wavelet_standard).parameters
    src = inspect.getsource(cw.process_cross_wavelet_pair)
    assert 'max_period=_tuning(config).get("maxPeriod")' in src, \
        "the caller must pass the study's period cap through"


def test_no_output_suffix_remains():
    """The _wtcfix suffix was scaffolding for comparing two branches. Once the
    correction is the only version, a variant-output mechanism is just a way to
    end up with two answers again."""
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = open(os.path.join(here, "dims_analysis", "steps", "crosswavelet.py")).read()
    assert "OUTPUT_SUFFIX" not in src
    assert "_wtcfix" not in src
