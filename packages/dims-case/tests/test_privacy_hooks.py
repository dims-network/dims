"""The guards a private study relies on, exercised against real git.

A study like case-karnatak holds identifiable video. The contract promises
three layers -- a commit hook, a push hook and a CI check -- and the first two
are the ones that act before anything leaves the machine. Both had already
failed silently once: `pre-push` was a byte-for-byte copy of `pre-commit`, so
it inspected the staging area, which is empty at push time, and passed every
push. Nothing noticed, because nothing ran them.

These tests run them.
"""
import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dims_case.core import _install_private_bits  # noqa: E402


def git(repo, *args, **kw):
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, **kw)


@pytest.fixture
def study(tmp_path):
    """A private study with a remote, its hooks installed, one commit pushed."""
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)

    repo = tmp_path / "case-secret"
    (repo / "assets" / "videos").mkdir(parents=True)
    (repo / "assets" / "videos" / ".gitkeep").write_text("")
    (repo / "dims-case.json").write_text(json.dumps({
        "case": "secret", "visibility": "private", "dimsCore": "9.9.9",
        "publishable": [],
        "restricted": ["assets/videos", "assets/timeseries"],
    }))
    (repo / "index.html").write_text("<p>a dashboard</p>")
    _install_private_bits(str(repo))

    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    for k, v in (("core.hooksPath", ".githooks"), ("user.email", "t@example"),
                 ("user.name", "T"), ("commit.gpgsign", "false")):
        git(repo, "config", k, v)
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "add", "-A")
    assert git(repo, "commit", "-m", "the study").returncode == 0
    assert git(repo, "push", "-q", "origin", "HEAD:main").returncode == 0
    return repo


def stage_a_video(repo, name="subject01.mp4"):
    path = repo / "assets" / "videos" / name
    path.write_text("pretend this is 4 GB of identifiable footage")
    git(repo, "add", "-f", str(path.relative_to(repo)))


def test_the_commit_hook_refuses_a_force_added_video(study):
    """`.gitignore` is not the guard: `git add -f` walks through one."""
    stage_a_video(study)
    r = git(study, "commit", "-m", "add a video")
    assert r.returncode == 1
    # git routes hook output to stderr, so read both rather than guessing.
    assert "assets/videos/subject01.mp4" in r.stderr + r.stdout


def test_the_push_hook_refuses_what_no_verify_let_through(study):
    """The layer that exists because the first one can be bypassed."""
    stage_a_video(study)
    git(study, "commit", "--no-verify", "-m", "sneak it in")

    r = git(study, "push", "origin", "HEAD:main")
    assert r.returncode != 0
    assert "assets/videos/subject01.mp4" in r.stderr + r.stdout


def test_the_push_hook_sees_data_a_later_commit_deleted(study):
    """Deleting the file does not remove it from the history being pushed.

    The tree at the tip is clean here, so a hook that checked only the tip --
    or only `git ls-files`, as the server-side guard does -- would pass this.
    """
    stage_a_video(study)
    git(study, "commit", "--no-verify", "-m", "sneak it in")
    git(study, "rm", "-q", "assets/videos/subject01.mp4")
    git(study, "commit", "--no-verify", "-m", "take it out again")

    r = git(study, "push", "origin", "HEAD:main")
    assert r.returncode != 0
    assert "history has to be rewritten" in r.stderr + r.stdout


def test_a_new_branch_is_checked_too(study):
    """A first push of a branch has no remote sha to diff against."""
    git(study, "checkout", "-q", "-b", "side")
    stage_a_video(study)
    git(study, "commit", "--no-verify", "-m", "sneak it in")

    r = git(study, "push", "origin", "side")
    assert r.returncode != 0
    assert "assets/videos/subject01.mp4" in r.stderr + r.stdout


def test_a_missing_restricted_key_does_not_disable_the_guard(study):
    """The failure a privacy guard may never have.

    The contract's own example omitted this key, so a hand-written
    dims-case.json turned both hooks into no-ops while still declaring the
    study private. The core's list is the fallback, as it already was on the
    server side.
    """
    path = study / "dims-case.json"
    case = json.loads(path.read_text())
    del case["restricted"]
    path.write_text(json.dumps(case))
    git(study, "add", "dims-case.json")
    git(study, "commit", "--no-verify", "-m", "drop the key")

    stage_a_video(study)
    assert git(study, "commit", "-m", "add a video").returncode == 1
    git(study, "commit", "--no-verify", "-m", "anyway")
    assert git(study, "push", "origin", "HEAD:main").returncode != 0


def test_a_publishable_directory_is_allowed_through(study):
    """The guard has to be openable, or it gets turned off wholesale."""
    path = study / "dims-case.json"
    case = json.loads(path.read_text())
    case["publishable"] = ["assets/videos/consented"]
    path.write_text(json.dumps(case))
    (study / "assets" / "videos" / "consented").mkdir()
    (study / "assets" / "videos" / "consented" / "ok.mp4").write_text("released")
    git(study, "add", "-f", "-A")

    assert git(study, "commit", "-m", "a video we may publish").returncode == 0
    assert git(study, "push", "origin", "HEAD:main").returncode == 0


def test_a_public_study_is_not_policed(tmp_path, study):
    """A public study's assets are the point of it."""
    path = study / "dims-case.json"
    case = json.loads(path.read_text())
    case["visibility"] = "public"
    path.write_text(json.dumps(case))
    git(study, "add", "dims-case.json")
    git(study, "commit", "--no-verify", "-m", "go public")

    stage_a_video(study)
    assert git(study, "commit", "-m", "an asset").returncode == 0
    assert git(study, "push", "origin", "HEAD:main").returncode == 0


def test_installing_twice_does_not_repeat_the_gitignore_block(tmp_path):
    """`adopt` then `sync` used to write the same rules into one file twice."""
    dest = tmp_path / "case-secret"
    dest.mkdir()
    (dest / ".gitignore").write_text("node_modules/\n")

    _install_private_bits(str(dest))
    once = (dest / ".gitignore").read_text()
    _install_private_bits(str(dest))
    twice = (dest / ".gitignore").read_text()

    assert once == twice
    assert twice.count("data.local.json\n") == 1
    assert twice.startswith("node_modules/\n")


def test_the_two_hooks_are_not_the_same_file(tmp_path):
    """They were, byte for byte, which is how the push guard did nothing."""
    dest = tmp_path / "case-secret"
    dest.mkdir()
    _install_private_bits(str(dest))
    hooks = dest / ".githooks"
    assert hooks.joinpath("pre-commit").read_text() != hooks.joinpath("pre-push").read_text()
    assert os.access(hooks / "pre-push", os.X_OK)


def test_check_says_when_a_clone_has_not_enabled_its_guards(study, capsys):
    """Tracked hooks do nothing until the clone opts in, and forgetting is silent.

    `git config core.hooksPath .githooks` is documented, and a person who
    clones a private study and misses it has no guards at all until CI catches
    something after a push. So the command that answers "is this study healthy"
    says so.
    """
    import subprocess
    import sys

    dims_case = os.path.join(os.path.dirname(__file__),
                             "..", "..", "..", "tools", "dims-case")
    git(study, "config", "--unset", "core.hooksPath")
    r = subprocess.run([sys.executable, dims_case, "check", str(study)],
                       capture_output=True, text=True)
    assert "guards are not enabled" in r.stdout
    assert "core.hooksPath .githooks" in r.stdout
    # A warning, not a failure: it is about this clone, not about the study.
    assert r.returncode == 0

    git(study, "config", "core.hooksPath", ".githooks")
    r = subprocess.run([sys.executable, dims_case, "check", str(study)],
                       capture_output=True, text=True)
    assert "guards are not enabled" not in r.stdout
