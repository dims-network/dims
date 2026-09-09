"""The study's dev server: range requests, and the private-data redirection.

141 lines that nothing imported and nothing launched, in the script every study
runs to look at its dashboard. Two things in it are load-bearing and neither was
asserted anywhere.

Range requests are why this file exists at all: without a 206 response a browser
cannot seek in a video, and the whole dashboard is a video beside a timeline.

The redirection is a privacy mechanism. A private study keeps its recordings out
of the repository and names their real location in an untracked data.local.json;
`translate_path` is what makes `assets/...` resolve there. It is also the only
thing standing between a crafted URL and the rest of the disk, so the traversal
refusal is tested here rather than trusted.
"""
import importlib.util
import os
import sys

import pytest

SCAFFOLD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_serve():
    """Import serve.py by path: it is a template script, not a package module."""
    spec = importlib.util.spec_from_file_location(
        "scaffold_serve", os.path.join(SCAFFOLD, "serve.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def serve():
    module = load_serve()
    yield module
    module.ASSETS_ROOT = None


def _bind(module, project_dir):
    """A real RangeRequestHandler, minus the socket.

    `translate_path` calls `super().translate_path`, so a stand-in object will
    not do -- it has to be an instance of the class. `__init__` would try to
    handle a request, so it is skipped; `directory` is the only attribute the
    inherited implementation reads.
    """
    handler = module.RangeRequestHandler.__new__(module.RangeRequestHandler)
    handler.directory = str(project_dir)

    def translate(path, _handler=handler, _dir=str(project_dir)):
        cwd = os.getcwd()
        os.chdir(_dir)
        try:
            return _handler.translate_path(path)
        finally:
            os.chdir(cwd)

    handler.translate = translate
    return handler


# --- where a private study's assets come from --------------------------------

def test_without_a_data_root_everything_comes_from_the_project(serve, tmp_path):
    serve.ASSETS_ROOT = None
    handler = _bind(serve, tmp_path)
    resolved = handler.translate("/assets/videos/s1.mp4")
    assert str(tmp_path) in resolved


def test_assets_are_served_from_the_external_root_when_one_is_set(serve, tmp_path):
    """The point of the mechanism: the file is outside the repository."""
    external = tmp_path / "elsewhere"
    (external / "videos").mkdir(parents=True)
    (external / "videos" / "s1.mp4").write_bytes(b"video")
    serve.ASSETS_ROOT = str(external)

    handler = _bind(serve, tmp_path)
    assert handler.translate("/assets/videos/s1.mp4") == str(external / "videos" / "s1.mp4")


def test_only_assets_are_redirected(serve, tmp_path):
    """index.html and the vendored core still come from the project."""
    external = tmp_path / "elsewhere"
    external.mkdir()
    serve.ASSETS_ROOT = str(external)
    handler = _bind(serve, tmp_path)
    assert str(external) not in handler.translate("/index.html")


def test_a_request_cannot_climb_out_of_the_data_root(serve, tmp_path):
    """The data root holds the identifiable recordings a private study exists to
    keep out of the repository, so a URL must not be able to walk out of it.

    What the redirection guarantees is one direction: nothing outside the data
    root is ever served *as* an asset. The fallback is the ordinary static
    handler rooted at the project, which does its own sanitising -- so a
    traversal ends up inside the project, which is what a dev server serves,
    and never inside somebody's home directory.
    """
    external = tmp_path / "elsewhere"
    external.mkdir()
    outside = tmp_path.parent / "outside-the-project.txt"
    outside.write_text("not for the browser")
    serve.ASSETS_ROOT = str(external)
    handler = _bind(serve, tmp_path)

    for attempt in ("/assets/../../outside-the-project.txt",
                    "/assets/videos/../../../outside-the-project.txt",
                    "/assets/../secret.txt"):
        resolved = handler.translate(attempt)
        assert not resolved.startswith(str(external) + os.sep), (
            f"{attempt} resolved inside the data root: {resolved}")
        assert str(outside) != resolved, f"{attempt} escaped the project"


def test_a_query_string_does_not_become_part_of_the_filename(serve, tmp_path):
    """Cache-busting `?v=2` is normal, and a path carrying it matches nothing."""
    external = tmp_path / "elsewhere"
    (external / "videos").mkdir(parents=True)
    (external / "videos" / "s1.mp4").write_bytes(b"video")
    serve.ASSETS_ROOT = str(external)
    handler = _bind(serve, tmp_path)
    assert handler.translate("/assets/videos/s1.mp4?v=2") == str(
        external / "videos" / "s1.mp4")


def test_a_missing_external_file_falls_back_to_the_project(serve, tmp_path):
    """So a partly-populated data root does not 404 files the repo does have."""
    external = tmp_path / "elsewhere"
    external.mkdir()
    serve.ASSETS_ROOT = str(external)
    handler = _bind(serve, tmp_path)
    assert str(external) not in handler.translate("/assets/videos/absent.mp4")


# --- reading data.local.json ---------------------------------------------------

def test_no_data_local_json_means_the_usual_place(serve, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert serve._assets_root() is None


def test_a_malformed_data_local_json_is_not_a_crash(serve, tmp_path, monkeypatch):
    """It is hand-edited and untracked, so it is the file most likely to be
    broken -- and a traceback on startup tells a researcher nothing."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data.local.json").write_text("{ not json")
    assert serve._assets_root() is None


def test_a_root_that_does_not_exist_is_ignored(serve, tmp_path, monkeypatch):
    """Naming a drive that is not mounted must not silently serve nothing."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data.local.json").write_text('{"assetsRoot": "/no/such/place"}')
    assert serve._assets_root() is None


def test_a_real_root_is_returned_absolute(serve, tmp_path, monkeypatch):
    external = tmp_path / "data"
    external.mkdir()
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data.local.json").write_text(f'{{"assetsRoot": "{external}"}}')
    assert serve._assets_root() == str(external)
