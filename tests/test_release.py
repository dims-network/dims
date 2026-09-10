"""The whole core moves together, or a pinned version means nothing.

A study pins one version and vendors the code that matches it. That only holds
if every package in this repository declares the same version and if the
release is described somewhere a reader can find. Both have already failed
here once: v1.2.0's tree contained no `pyproject.toml` at all, so nothing was
installable from the release three studies were pinned to.
"""
import os
import re
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def declared_versions():
    found = {}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in ("node_modules", ".git", ".venv", "__pycache__")]
        if "pyproject.toml" in filenames:
            path = os.path.join(dirpath, "pyproject.toml")
            with open(path, "rb") as fh:
                data = tomllib.load(fh)
            version = (data.get("project") or {}).get("version")
            if version:
                found[os.path.relpath(path, ROOT)] = version
    return found


def literal_versions():
    """`__version__` as written in the source.

    Not `importlib.metadata`: an editable install keeps the version it was
    installed with, so the metadata for this checkout currently reports a
    version two releases old. Anything that compares versions at runtime has to
    read the literal, which makes keeping the literal right this test's job.
    """
    found = {}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in ("node_modules", ".git", ".venv", "__pycache__")]
        if "__init__.py" not in filenames:
            continue
        path = os.path.join(dirpath, "__init__.py")
        m = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', open(path).read(), re.M)
        if m:
            found[os.path.relpath(path, ROOT)] = m.group(1)
    return found


def test_every_package_declares_the_same_version():
    versions = declared_versions()
    assert versions, "no packaged version found -- a release would install nothing"
    assert len(set(versions.values())) == 1, (
        "packages disagree about the core version, so a study pinning one of "
        f"them pins the others by accident: {versions}")


def test_the_source_agrees_with_the_packaging():
    """`__version__` had drifted to 0.1.0 while the package shipped 1.4.0."""
    packaged = set(declared_versions().values())
    for path, version in literal_versions().items():
        assert version in packaged, (
            f"{path} says {version}, but this release is "
            f"{', '.join(sorted(packaged))}")


def test_the_changelog_describes_the_version_being_shipped():
    """And describes it FIRST, which is what makes it the version being shipped.

    This asked only whether the declared version had *a* heading somewhere in
    the file. Every past release leaves one behind, so once v1.0.0 was written
    the check could never fail again -- and it did not: v1.4.0 was tagged while
    pyproject.toml and both __version__ strings still said 1.3.0, and this test
    passed on the v1.3.0 heading four releases down the page.

    The changelog is strictly newest-first, so the first `## v...` heading is
    the release being shipped. Comparing against that one is the difference
    between checking that a version was described once and checking that it is
    the version this tree is.
    """
    version = next(iter(declared_versions().values()))
    changelog = open(os.path.join(ROOT, "CHANGELOG.md")).read()
    headings = re.findall(r"^## v(\S+)$", changelog, re.M)

    assert headings, (
        "CHANGELOG.md has no `## vX.Y.Z` headings at all, so nothing here "
        "describes any release.")
    assert headings[0] == version, (
        f"this tree declares {version}, but the newest entry in CHANGELOG.md "
        f"is v{headings[0]}. Either the release was not written up, or the "
        f"version literals were not bumped -- the second is how v1.4.0 shipped "
        f"declaring 1.3.0.")
