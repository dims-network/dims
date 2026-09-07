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
