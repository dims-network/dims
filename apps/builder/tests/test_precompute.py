"""What the wizard's precompute step does, against the project it really makes.

This suite used to fabricate an `opt/` directory full of fake step scripts, and
every test that would have reached environment setup monkeypatched it away. Both
were necessary for the tests to pass, and both hid the same thing: the bundled
scaffold has no `opt/` at all, the shared analyses moved into the dims-analysis
package, and precompute opened `opt/requirements.txt` before checking whether
there was anything to do. Step 6 of the wizard failed for every project it
generated, with a FileNotFoundError, for the audience least able to read one.

So the fixture here is the real scaffold.
"""
import json
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dims_builder import precompute  # noqa: E402
from dims_builder.precompute import (  # noqa: E402
    _enabled, discover_steps, run_precompute,
)
from dims_builder.project import BUNDLED_TEMPLATE  # noqa: E402


def scaffold_project(tmp_path, config=None):
    """A copy of the scaffold the wizard actually generates from."""
    proj = tmp_path / "study"
    shutil.copytree(BUNDLED_TEMPLATE, proj)
    if config is not None:
        (proj / "config.json").write_text(json.dumps(config, indent=2))
    return str(proj)


def with_own_step(project, name="step_categorical_rqa.py"):
    """A study that ships an analysis of its own, the way ORTHO does."""
    opt = os.path.join(project, "opt")
    os.makedirs(opt, exist_ok=True)
    with open(os.path.join(opt, name), "w") as fh:
        fh.write("import sys; sys.exit(0)\n")
    return project


# --- discovery --------------------------------------------------------------

def test_the_scaffold_ships_no_analyses_of_its_own(tmp_path):
    """The shared ones come from the package now. Finding none here is correct
    -- it was reading it as 'nothing to run' that was wrong."""
    assert discover_steps(scaffold_project(tmp_path)) == []


def test_a_study_owned_step_is_found(tmp_path):
    proj = with_own_step(scaffold_project(tmp_path), "step_network.py")
    step_id, script, out_dir, key = discover_steps(proj)[0]
    assert (step_id, script, out_dir, key) == (
        "network", os.path.join("opt", "step_network.py"),
        os.path.join("assets", "network"), "include_network")


def test_a_stale_copy_of_a_shared_analysis_is_ignored(tmp_path):
    """A project carrying opt/step_RQA.py is a leftover from before the
    migration. Running it would produce a second, older answer beside the
    package's."""
    proj = with_own_step(scaffold_project(tmp_path), "step_RQA.py")
    assert discover_steps(proj) == []


def test_a_project_with_no_opt_directory_is_not_an_error(tmp_path):
    assert discover_steps(str(tmp_path)) == []


# --- the failure this file exists to prevent --------------------------------

def test_a_project_with_nothing_enabled_never_builds_an_environment(tmp_path):
    """The check must come first. Building a venv and reading a requirements
    file the project does not have is what broke every generated project."""
    proj = scaffold_project(tmp_path, {"videoIDs": ["v1"], "dataTypes": {"v1": ["a"]}})
    out = "".join(run_precompute(proj, config={}))
    assert "nothing to precompute" in out
    assert "Setting up Python environment" not in out
    assert not os.path.exists(os.path.join(proj, ".venv"))
    assert "Traceback" not in out and "FileNotFoundError" not in out


def test_an_enabled_config_reaches_the_shared_runner(tmp_path, monkeypatch):
    """Without a real venv build -- that is a network install, not a unit test."""
    import dims_builder.precompute as pc
    monkeypatch.setattr(pc, "create_venv", lambda project: iter(["(venv)\n"]))
    commands = []

    def fake_stream(cmd, cwd):
        commands.append(cmd)
        yield "__EXIT__:0\n"

    monkeypatch.setattr(pc, "_stream", fake_stream)
    proj = scaffold_project(tmp_path)
    out = "".join(pc.run_precompute(proj, config={"include_RQA": ["a"]}))

    assert any("dims_analysis.cli" in " ".join(c) for c in commands), commands
    assert "Precompute complete" in out


def test_a_failing_analysis_is_reported_and_stops_the_run(tmp_path, monkeypatch):
    import dims_builder.precompute as pc
    monkeypatch.setattr(pc, "create_venv", lambda project: iter([]))
    monkeypatch.setattr(pc, "_stream", lambda cmd, cwd: iter(["__EXIT__:1\n"]))
    proj = scaffold_project(tmp_path)
    out = "".join(pc.run_precompute(proj, config={"include_crosswavelet": [["a", "b"]]}))
    assert "__FAILED__:dims-analysis" in out
    assert "Precompute FAILED" in out


def test_a_study_owned_step_runs_after_the_shared_ones(tmp_path, monkeypatch):
    import dims_builder.precompute as pc
    monkeypatch.setattr(pc, "create_venv", lambda project: iter([]))
    order = []

    def fake_stream(cmd, cwd):
        order.append("shared" if "dims_analysis.cli" in " ".join(cmd) else "own")
        yield "__EXIT__:0\n"

    monkeypatch.setattr(pc, "_stream", fake_stream)
    proj = with_own_step(scaffold_project(tmp_path), "step_categorical_rqa.py")
    "".join(pc.run_precompute(proj, config={
        "include_RQA": ["a"], "include_categorical_rqa": True}))
    assert order == ["shared", "own"], order


# --- the config gate --------------------------------------------------------

@pytest.mark.parametrize("key,config,expected", [
    ("include_RQA", {"include_RQA": ["a"]}, True),
    ("include_rqa", {"include_RQA": ["a"]}, True),      # historical casing
    ("include_cRQA", {"include_crqa": [["a", "b"]]}, True),
    ("include_RQA", {"include_RQA": []}, False),
    ("include_RQA", {}, False),
])
def test_the_config_key_is_matched_case_insensitively(key, config, expected):
    assert _enabled(config, key) is expected


def test_a_study_keeps_the_versions_it_pinned(tmp_path):
    """The cleaner drops what cannot be installed, and nothing else.

    It used to carry a repair for a template that no longer exists: the
    template's `scipy==1.26.4` is not a real release -- 1.26.4 is a numpy
    version -- so the rule replaced any scipy requirement with a bare `scipy`.
    Applied to a study that had deliberately pinned scipy==1.11.4, that
    silently removed the pin. Repairing a file nobody writes any more, by
    un-pinning one somebody did, is the wrong trade.
    """
    opt = tmp_path / "opt"
    opt.mkdir()
    (opt / "requirements.txt").write_text(
        "# a study's own analysis dependencies\n"
        "scipy==1.11.4\n"
        "pandas>=2.0\n"
        "json\n"          # stdlib: cannot be installed, and is dropped
        "\n")

    cleaned = precompute._filtered_requirements(str(tmp_path))
    written = open(cleaned).read().split()

    assert "scipy==1.11.4" in written, "the study's pin was removed"
    assert "pandas>=2.0" in written
    assert "json" not in written, "stdlib is not pip-installable"
    assert "numpy" in written, "added explicitly, not relied on transitively"


def test_the_old_template_s_impossible_pin_is_repaired(tmp_path):
    """`scipy==1.26.4` is not a release -- 1.26.4 is a numpy version.

    Every study made from the template that shipped it carries it, and pip stops
    dead at a pin that cannot resolve, so the study's own analyses never install.
    This has been got wrong in both directions: first by rewriting *any* scipy
    requirement, which un-pinned studies that meant theirs, and then by dropping
    the repair on the reasoning that nobody would still carry the broken one.
    The next study built from a sample carried it. Both cases are asserted here
    so the next change has to keep both true.
    """
    opt = tmp_path / "opt"
    opt.mkdir()
    (opt / "requirements.txt").write_text(
        "json\nscipy==1.26.4\nmatplotlib\npandas\npycwt\n")

    written = open(precompute._filtered_requirements(str(tmp_path))).read().split()

    assert "scipy" in written, "the impossible pin should become a usable one"
    assert "scipy==1.26.4" not in written
    assert "json" not in written
    assert written.count("scipy") == 1, "repaired, not duplicated"


def test_a_failed_environment_setup_is_reported_as_a_failure(tmp_path, monkeypatch):
    """The log used to end on "Precompute complete" after a failed install.

    create_venv streamed pip's exit codes to the browser and nothing here read
    them, so a study whose own requirements would not install still finished
    green -- while the page, which does scan the stream, said it finished with
    errors. Two answers to one question, in one log, and the reassuring one was
    the server's.
    """
    project = tmp_path / "study"
    (project / "opt").mkdir(parents=True)
    (project / "config.json").write_text(json.dumps({"videoIDs": [], "dataTypes": {}}))

    def failing_setup(_project):
        yield "$ pip install -r opt/requirements.txt\n"
        yield "ERROR: No matching distribution found for scipy==1.26.4\n"
        yield "__EXIT__:1\n"

    monkeypatch.setattr(precompute, "create_venv", failing_setup)
    # The shared analyses come from the core install, not from this file, so
    # they still run; their own failure is a separate report.
    monkeypatch.setattr(precompute, "_stream",
                        lambda *a, **k: iter(["ran\n", "__EXIT__:0\n"]))
    out = "".join(precompute.run_precompute(
        str(project), config={"include_RQA": ["a"]}))

    assert "__FAILED__:environment" in out
    assert "Precompute FAILED" in out, out[-300:]
    assert "Precompute complete" not in out


def test_a_clean_setup_still_finishes_complete(tmp_path, monkeypatch):
    project = tmp_path / "study"
    project.mkdir()
    (project / "config.json").write_text(json.dumps({"videoIDs": [], "dataTypes": {}}))

    monkeypatch.setattr(precompute, "create_venv",
                        lambda _p: iter(["$ pip install\n", "__EXIT__:0\n"]))
    monkeypatch.setattr(precompute, "_stream",
                        lambda *a, **k: iter(["ran\n", "__EXIT__:0\n"]))
    out = "".join(precompute.run_precompute(
        str(project), config={"include_RQA": ["a"]}))

    assert "Precompute complete" in out
    assert "__FAILED__" not in out
