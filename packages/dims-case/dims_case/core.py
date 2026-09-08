"""Creating a study, and keeping its vendored core honest.

This is library code, used by two callers that must not disagree:

  * the `dims-case` command, which a person runs
  * the no-code builder, which writes the same thing for someone who will never
    open a terminal

A generated study is a generated study either way.
"""

import argparse


import hashlib


import json


import os
import re


import shutil
import tempfile


import subprocess


import sys


# packages/dims-case/dims_case/core.py -> repo root
CORE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))


VENDOR = {
    "packages/dims-core": "vendor/dims-core",
    "packages/dims-tabs": "vendor/dims-tabs",
}


SCAFFOLD = "packages/dims-case-scaffold"


RESTRICTED = ["assets/videos", "assets/timeseries", "assets/transcripts",
              "assets/elan", "assets/motion_tracking"]


#: The payload encoding this core reads. Kept in step with
#: `dims_analysis.common.arrays.PAYLOAD_VERSION` -- read from there when the
#: analyses are installed, and declared here so `dims-case` works without them,
#: which is the normal state of a study repository's CI.
PAYLOAD_VERSION = 2
try:                                             # pragma: no cover - optional
    from dims_analysis.common.arrays import PAYLOAD_VERSION as _ANALYSIS_VERSION
    PAYLOAD_VERSION = _ANALYSIS_VERSION
except ImportError:
    pass


def stale_assets(dest, expected=None):
    """Committed analysis outputs the pinned core cannot read.

    v2.0.0 changed the payload format, so a study that bumps `dimsCore` and does
    not rebuild has assets no tab can draw. The dashboard says so when someone
    opens it -- but the person who bumped and the person who opens it are not
    always the same person, and CI is where the first one finds out.

    A study with nothing committed under `assets/` is every private study, and
    is not an error: its data lives outside the repository and there is nothing
    here to compare.
    """
    expected = PAYLOAD_VERSION if expected is None else expected
    assets = os.path.join(dest, "assets")
    problems = []
    for root, dirs, files in os.walk(assets):
        dirs.sort()
        for name in sorted(files):
            if not name.endswith("_data.json"):
                continue
            rel = os.path.relpath(os.path.join(root, name), dest)
            try:
                with open(os.path.join(root, name)) as fh:
                    found = json.load(fh).get("payload_version")
            except (OSError, ValueError) as exc:
                problems.append(f"{rel} could not be read as a payload ({exc}).")
                continue
            if found == expected:
                continue
            if found is not None and found > expected:
                problems.append(
                    f"{rel} is payload version {found} and this core reads "
                    f"{expected}: the assets are newer than the pinned core. "
                    f"Bump dimsCore rather than rebuilding, or the study loses "
                    f"work.")
            else:
                shown = "an older core" if found is None else f"payload version {found}"
                problems.append(
                    f"{rel} was written by {shown} and this core reads "
                    f"{expected}; every analysis tab will refuse it. Rebuild: "
                    f"python build_assets.py")
    return problems


#: A tab declares its id to `DIMS.registerTab`, and the host keys on that rather
#: than on the filename.
_TAB_ID = re.compile(r"""\bid\s*:\s*['"]([\w-]+)['"]""")


def _tab_ids(path):
    try:
        with open(path) as fh:
            return set(_TAB_ID.findall(fh.read()))
    except OSError:                              # pragma: no cover - unreadable
        return set()


def shadowed_tabs(dest):
    """Study-owned tabs whose id a vendored built-in already claims.

    `registerTab` refuses a duplicate id with a `console.error` and carries on,
    so the study keeps a file that does nothing and nobody is told which of the
    two is on screen. It became reachable in v2.0.0, when the cross-effector
    network -- which had lived in one study -- became a built-in.

    Reported, never deleted: whether to keep a customised copy under a new id or
    drop it for the built-in is the study owner's call.
    """
    tabs_dir = os.path.join(dest, "tabs")
    vendor_dir = os.path.join(dest, "vendor", "dims-tabs")
    if not os.path.isdir(tabs_dir) or not os.path.isdir(vendor_dir):
        return []

    built_in = {}
    for name in sorted(os.listdir(vendor_dir)):
        if name.endswith(".js"):
            for tab_id in _tab_ids(os.path.join(vendor_dir, name)):
                built_in[tab_id] = name

    problems = []
    for name in sorted(os.listdir(tabs_dir)):
        if not name.endswith(".js"):
            continue
        for tab_id in sorted(_tab_ids(os.path.join(tabs_dir, name))):
            if tab_id in built_in:
                problems.append(
                    f"tabs/{name} registers the tab id '{tab_id}', which the "
                    f"built-in vendor/dims-tabs/{built_in[tab_id]} also claims. "
                    f"The built-in loads first and wins; this study's copy is "
                    f"ignored. Delete tabs/{name}, or give it an id of its own.")
    return problems


# The names are historical on purpose: these are the files a study carried in
# its own `opt/` before the shared analyses became the dims-analysis package, and
# recognising them is how `adopt` clears the leftovers. They are data about the
# past, not a stale reference to fix.
SHARED_STEPS = {"step_RQA.py", "step_cRQA.py", "step_crosswavelet.py",
                "requirements.txt"}


# Both hooks ask the same question of a different set of paths, so the question
# is written once. A study that answered it two slightly different ways would be
# worse than a study with one hook.
_HOOK = '''#!/bin/sh
# __TITLE__
#
# A .gitignore is not this guard -- `git add -f` walks straight through one.
__PROLOGUE__python3 - "$@" <<'PY' || exit 1
import json, os, subprocess, sys

# The core's own list is the fallback. Without it, a dims-case.json that has
# lost its "restricted" key -- or was written by hand from the example in the
# contract, which omitted it -- disables the guard silently, which is the one
# failure a privacy guard may never have. The server-side check already has
# this fallback; the hook did not.
DEFAULT_RESTRICTED = ['assets/videos', 'assets/timeseries', 'assets/transcripts', 'assets/elan', 'assets/motion_tracking']

def run(*args):
    out = subprocess.run(["git", *args], capture_output=True, text=True)
    return out.stdout.split() if out.returncode == 0 else []

try:
    case = json.load(open("dims-case.json"))
except (OSError, ValueError):
    sys.exit(0)
if case.get("visibility") != "private":
    sys.exit(0)

allow = case.get("publishable") or []
restricted = case.get("restricted") or DEFAULT_RESTRICTED

__COLLECT__

bad = sorted({f for f in candidates
              if any(f.startswith(r) for r in restricted)
              and not any(f.startswith(a) for a in allow)
              # A manifest carries names and checksums, never content.
              and not f.endswith(("MANIFEST.json", ".gitkeep"))})
if bad:
    print("BLOCKED: this study is declared private and these are data files:")
    for f in bad:
        print("  " + f)
    print("")
    print("__ADVICE__")
    print("")
    print("If one of these is genuinely publishable, add its directory to")
    print("\\"publishable\\" in dims-case.json. Do not use --no-verify: CI")
    print("checks the same thing and will fail the branch.")
    sys.exit(1)
PY
'''


PRE_COMMIT = (_HOOK
    .replace("__PROLOGUE__", "")
    .replace("__TITLE__", "Refuses to stage data in a private case.")
    .replace("__COLLECT__", "candidates = run(\"diff\", \"--cached\", \"--name-only\")")
    .replace("__ADVICE__",
             "Nothing has been committed. Unstage them and try again."))


# The index is empty at push time, so the pre-commit body -- which is what this
# hook used to be, byte for byte -- inspected nothing and passed every push.
# What a push actually offers is a range of commits per ref, on stdin.
PRE_PUSH = (_HOOK
    .replace("__PROLOGUE__",
             "# git writes the refs being pushed on stdin, and the heredoc\n"
             "# below is itself stdin -- so they are captured first and passed\n"
             "# as an argument. Reading stdin inside the script would read the\n"
             "# script.\n"
             "DIMS_PUSH_REFS=$(cat)\n"
             "export DIMS_PUSH_REFS\n")
    .replace("__TITLE__", "Refuses to push data in a private case.")
    .replace("__COLLECT__", '''candidates = []
for line in os.environ.get("DIMS_PUSH_REFS", "").splitlines():
    parts = line.split()
    if len(parts) != 4:
        continue
    _local_ref, local_sha, _remote_ref, remote_sha = parts
    if local_sha.strip("0") == "":
        continue                      # deleting a branch pushes no content
    if remote_sha.strip("0") == "":
        # A new branch: everything on it that the remote does not already have.
        commits = run("rev-list", local_sha, "--not", "--remotes")
    else:
        commits = run("rev-list", remote_sha + ".." + local_sha)
    # Every path the range touches, not just the paths still present at the
    # tip. Data added and then deleted a commit later is still in the history
    # this push would publish, and removing it afterwards means a rewrite.
    for commit in commits:
        candidates += run("diff-tree", "-r", "--no-commit-id",
                          "--name-only", commit)
    # And the tree being pushed, which is what the server-side guard reads.
    candidates += run("ls-tree", "-r", "--name-only", local_sha)''')
    .replace("__ADVICE__",
             "Nothing has been pushed. These are in commits you already made, "
             "so removing the file is not enough -- the history has to be "
             "rewritten before this push can succeed."))


CI_YML = """name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  # The study's own code -- not the vendored core, which is verified byte for
  # byte against the release below and so needs no syntax check here. Every
  # study passed python_paths: "" and a js_glob covering only vendored files,
  # so build_assets.py, every opt/ and tools/ script, and a 1245-line
  # study-owned tab were never even parsed.
  check:
    uses: dims-network/.github/.github/workflows/reusable-dashboard-ci.yml@main
    with:
      python_paths: "build_assets.py opt tools"
      js_glob: "tabs/*.js"
      config_path: "config.json"
      check_assets: %(check_assets)s

  # A study must not carry hand-edited core code -- that is what makes a
  # pinned copy a pin rather than a fork. The check lives in the org's
  # workflow repo because it needs the released core to compare against, and
  # because one copy of it cannot drift from another.
  vendor:
    uses: dims-network/.github/.github/workflows/reusable-vendor-check.yml@main
"""


PAGES_YML = """name: Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

jobs:
  deploy:
    uses: dims-network/.github/.github/workflows/reusable-pages-deploy.yml@main
"""


PRIVACY_YML = """name: Privacy guard

on:
  push:
    branches: [main]
  pull_request:

jobs:
  guard:
    uses: dims-network/.github/.github/workflows/reusable-privacy-guard.yml@main
"""


SYNC_YML = """name: Core update

# Each study checks for itself whether a newer core has been released, and opens
# a pull request in its own repository. Pull rather than push: the core would
# otherwise need write access to every study, which means a personal access
# token that somebody has to create, own and rotate. The built-in token is
# enough to open a pull request in the repository it belongs to.
on:
  schedule:
    - cron: "0 6 * * 1"      # Monday morning
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write

jobs:
  bump:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Find the newest core release
        id: latest
        run: |
          latest=$(git ls-remote --tags --refs https://github.com/dims-network/dims.git \
                   | sed 's|.*refs/tags/||' | grep '^v' | sort -V | tail -1)
          echo "tag=${latest}" >> "$GITHUB_OUTPUT"
          echo "version=${latest#v}" >> "$GITHUB_OUTPUT"
          echo "pinned=$(python -c "import json;print(json.load(open('dims-case.json'))['dimsCore'])")" >> "$GITHUB_OUTPUT"

      - name: Up to date?
        id: check
        run: |
          if [ -z "${{ steps.latest.outputs.version }}" ] || \
             [ "${{ steps.latest.outputs.version }}" = "${{ steps.latest.outputs.pinned }}" ]; then
            echo "nothing to do: pinned ${{ steps.latest.outputs.pinned }}"
            echo "changed=false" >> "$GITHUB_OUTPUT"
          else
            echo "changed=true" >> "$GITHUB_OUTPUT"
          fi

      - name: Refresh the vendored core
        if: steps.check.outputs.changed == 'true'
        run: |
          git clone -q --depth 1 --branch "${{ steps.latest.outputs.tag }}" \
            https://github.com/dims-network/dims.git /tmp/core
          python /tmp/core/tools/dims-case sync . --version "${{ steps.latest.outputs.version }}"

      # A pull request opened with the built-in token does not start other
      # workflows, so the check that matters runs here, before the PR exists.
      - name: Verify what we are about to propose
        if: steps.check.outputs.changed == 'true'
        run: python /tmp/core/tools/dims-case check .

      # The analyses are not vendored -- a study installs them from the core it
      # pins -- so the numbers in this study's assets are produced by the code
      # in /tmp/core, and this is the last point before that code becomes this
      # study's. `examples/reference/` is a synthetic study whose answers are
      # known in advance (a 2 s sine recurs at 2 s, a 0.4 s lag sits 0.4 s off
      # the diagonal, two independent noises beat a 95 % level 5 % of the time),
      # and its tests check those against pyrqa and against Torrence & Compo's
      # published constants.
      #
      # Running it here rather than trusting the core's own CI is deliberate:
      # the same release meets a different Python, a different numpy and a
      # different OpenCL here, and it is this study that carries the result.
      - name: The pinned core still answers the reference study correctly
        if: steps.check.outputs.changed == 'true'
        run: |
          sudo apt-get update -qq && sudo apt-get install -y -qq pocl-opencl-icd
          python -m pip install -q -e /tmp/core/packages/dims-analysis
          python -m pip install -q pytest pyrqa
          python -c "import pyrqa.computation" || {
            echo "::error::pyrqa is the independent oracle for DET, LAM and RR;"\
                 "without it those tests skip silently and this gate proves nothing"
            exit 1
          }
          python -m pytest /tmp/core/tests/reference -q

      # Needs "Allow GitHub Actions to create and approve pull requests" in the
      # organisation's Actions settings. Until that is on, this step fails and
      # the job below explains why rather than leaving a bare red X every week.
      - name: Open the pull request
        id: pr
        if: steps.check.outputs.changed == 'true'
        continue-on-error: true
        uses: peter-evans/create-pull-request@v7
        with:
          branch: core/${{ steps.latest.outputs.tag }}
          title: "Update DIMS core to ${{ steps.latest.outputs.tag }}"
          commit-message: "Update DIMS core to ${{ steps.latest.outputs.tag }}"
          body: |
            Pinned core moves from `${{ steps.latest.outputs.pinned }}` to
            `${{ steps.latest.outputs.version }}`.

            `vendor/` was refreshed by `dims-case sync` and verified against the
            release before this pull request was opened. Nothing here was edited
            by hand — if something in the core is wrong, fix it there and let the
            next release come through.

            Release notes: https://github.com/dims-network/dims/releases/tag/${{ steps.latest.outputs.tag }}

      - name: Explain a permissions failure
        if: steps.check.outputs.changed == 'true' && steps.pr.outcome == 'failure'
        run: |
          {
            echo "### Core ${{ steps.latest.outputs.tag }} is available, but the pull request could not be opened"
            echo ""
            echo "The vendored core was refreshed and verified successfully. Only the"
            echo "pull request failed, and almost always for one reason:"
            echo ""
            echo "**Organisation settings -> Actions -> General -> Workflow permissions**"
            echo "must allow *Read and write*, and *Allow GitHub Actions to create and"
            echo "approve pull requests*. Both are off by default."
            echo ""
            echo "Until then, update by hand:"
            echo ""
            echo '```sh'
            echo "git clone --depth 1 --branch ${{ steps.latest.outputs.tag }} https://github.com/dims-network/dims.git /tmp/core"
            echo "python /tmp/core/tools/dims-case sync ."
            echo '```'
          } >> "$GITHUB_STEP_SUMMARY"
          echo "::warning::Core ${{ steps.latest.outputs.tag }} is available but Actions may not open pull requests here."
"""


def _write_workflows(dest, visibility):
    wf = os.path.join(dest, ".github", "workflows")
    os.makedirs(wf, exist_ok=True)
    # A private study keeps its assets out of git, so the asset existence check
    # would report every file as missing.
    open(os.path.join(wf, "ci.yml"), "w").write(
        CI_YML % {"check_assets": "true" if visibility == "public" else "false"})
    open(os.path.join(wf, "core-update.yml"), "w").write(SYNC_YML)
    if visibility == "public":
        open(os.path.join(wf, "pages.yml"), "w").write(PAGES_YML)
    else:
        # No Pages for a private study: there is nothing publishable to deploy.
        p = os.path.join(wf, "pages.yml")
        if os.path.exists(p):
            os.remove(p)
        open(os.path.join(wf, "privacy.yml"), "w").write(PRIVACY_YML)


def _dir_hash(path):
    """Stable hash of a directory's contents, for the vendor integrity check."""
    h = hashlib.sha256()
    for root, dirs, files in os.walk(path):
        dirs.sort()
        for name in sorted(files):
            if name.startswith("."):
                continue
            full = os.path.join(root, name)
            h.update(os.path.relpath(full, path).encode())
            with open(full, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()


def _core_version():
    try:
        out = subprocess.run(["git", "describe", "--tags", "--abbrev=0"],
                             cwd=CORE_ROOT, capture_output=True, text=True)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip().lstrip("v")
    except OSError:
        pass
    return "0.0.0-dev"


BEGIN = "<!-- study-owned tabs: BEGIN"


END = "<!-- study-owned tabs: END -->"


def _write_index(dest):
    """Refresh index.html from the scaffold, keeping the study's own tab list.

    The vendored core changes; a study's own tabs do not. Without this, every
    core refresh would silently delete them -- and with no build step, that list
    of script tags IS the configuration.
    """
    scaffold_index = os.path.join(CORE_ROOT, SCAFFOLD, "index.html")
    target = os.path.join(dest, "index.html")
    new = open(scaffold_index).read()
    if os.path.exists(target):
        old = open(target).read()
        i, j = old.find(BEGIN), old.find(END)
        if i != -1 and j != -1:
            keep = old[i:j + len(END)]
            ni, nj = new.find(BEGIN), new.find(END)
            if ni != -1 and nj != -1:
                new = new[:ni] + keep + new[nj + len(END):]
    open(target, "w").write(new)


def _register_study_tabs(dest):
    """List whatever is in tabs/ inside the preserved block."""
    tabs_dir = os.path.join(dest, "tabs")
    if not os.path.isdir(tabs_dir):
        return
    files = sorted(f for f in os.listdir(tabs_dir) if f.endswith(".js"))
    if not files:
        return
    target = os.path.join(dest, "index.html")
    s = open(target).read()
    i, j = s.find(BEGIN), s.find(END)
    if i == -1 or j == -1:
        return
    tags = "\n".join(f'    <script src="tabs/{f}"></script>' for f in files)
    block = (BEGIN + "\n"
             "         Tabs that only make sense for this study. Same contract\n"
             "         as a built-in one: docs/contracts/tab.md -->\n"
             + tags + "\n    " + END)
    open(target, "w").write(s[:i] + block + s[j + len(END):])


def _write_vendor(dest):
    for src_rel, dst_rel in VENDOR.items():
        src, dst = os.path.join(CORE_ROOT, src_rel), os.path.join(dest, dst_rel)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("test", "node_modules", "*.md"))
    return {rel: _dir_hash(os.path.join(dest, rel)) for rel in VENDOR.values()}


def verify_vendor(dest, strict=False):
    """Problems with a study's vendored core, as a list of messages.

    By default this compares vendor/ against the hashes the study recorded in
    its own dims-case.json. That catches a hand-edit and needs no network, so
    it is what a contributor runs locally.

    Both sides of that comparison live in the study, though, so a vendor/ taken
    from a *modified* core agrees with itself and passes. `strict` rebuilds
    vendor/ from this checkout of the core and compares against that instead,
    which is the comparison a fork cannot satisfy. CI runs it from a checkout
    of the exact release the study pins, which is what makes a pin a pin.
    """
    case = json.load(open(os.path.join(dest, "dims-case.json")))
    version = case.get("dimsCore")
    recorded = case.get("vendorHashes") or {}
    problems = []

    expected = dict(recorded)
    if strict:
        with tempfile.TemporaryDirectory() as scratch:
            expected = _write_vendor(scratch)
        for rel in recorded:
            if rel not in expected:
                problems.append(
                    f"{rel} is vendored here but is not part of core {version}.")

    for rel, want in expected.items():
        path = os.path.join(dest, rel)
        if not os.path.isdir(path):
            problems.append(f"{rel} is missing. Run `dims-case sync .`.")
            continue
        if _dir_hash(path) != want:
            problems.append(
                f"{rel} does not match dims-core {version}. Never edit vendored "
                f"code -- fix it in dims-network/dims and bump the pin.")
        elif strict and recorded.get(rel) != want:
            # The bytes are right but the study's record of them is not, so an
            # offline check would pass or fail for the wrong reason.
            problems.append(
                f"{rel} matches core {version}, but dims-case.json records a "
                f"different hash for it. Re-run `dims-case sync .`.")

    return problems


GITIGNORE_MARK = "# private study: data lives outside the repo"


# Always refreshed: generated files a study has no reason to edit. serve.py is
# the host, not the study.
#
# It was not always in this list, and the consequence was invisible: case-demo
# and case-ortho kept the pre-monorepo 101-line version -- no data.local.json
# support and no path-traversal guard -- and no amount of core bumping could
# have given it to them. Only `adopt` copied it, once.
SCAFFOLD_FILES = ("serve.py",)

# Seeded once, then the study's own. Karnatak's build_assets.py drives motion
# capture and its requirements.txt grew the study's own dependencies, so
# overwriting these on a version bump would delete work.
#
# But "never overwritten" left the studies that had *not* touched them stuck on
# whatever the scaffold looked like the day they were seeded, which is the same
# drift the vendored core exists to prevent. So the hash of what was written is
# recorded, exactly as it is for vendor/: a file that still matches its record
# is untouched and is refreshed; a file that does not is the study's, and is
# left alone with a line saying so.
SCAFFOLD_SEED_FILES = ("build_assets.py", "requirements.txt",
                       "data.local.json.example")


def _file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def _refresh_scaffold_files(dest, case=None, report=print):
    """Refresh generated files; seed and update untouched ones.

    Returns the map of seeded-file hashes to record in dims-case.json.
    """
    seeded = dict((case or {}).get("seededHashes") or {})

    for name in SCAFFOLD_FILES:
        src = os.path.join(CORE_ROOT, SCAFFOLD, name)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(dest, name))

    for name in SCAFFOLD_SEED_FILES:
        src = os.path.join(CORE_ROOT, SCAFFOLD, name)
        dst = os.path.join(dest, name)
        if not os.path.exists(src):
            continue
        if not os.path.exists(dst):
            shutil.copy(src, dst)
            seeded[name] = _file_hash(dst)
            report(f"  seeded {name}")
            continue
        current = _file_hash(dst)
        if current == _file_hash(src):
            seeded[name] = current              # already up to date
        elif seeded.get(name) == current:
            shutil.copy(src, dst)
            seeded[name] = _file_hash(dst)
            report(f"  updated {name} (unmodified since it was seeded)")
        else:
            # Either the study edited it, or it predates the recording of
            # hashes. Both mean: not ours to overwrite.
            report(f"  kept {name} (this study's own; the scaffold's version "
                   f"has moved on)")
    return seeded


def _write_hooks(dest):
    """Install both hooks, overwriting whatever is there.

    Hooks are generated code, like index.html and the workflows, so a core
    bump has to refresh them -- otherwise a study keeps the hooks it was
    created with, and a fix to a guard never reaches the study that needs it.
    That is why case-karnatak still carried a pre-push that inspected the
    staging area and passed every push.
    """
    hooks = os.path.join(dest, ".githooks")
    os.makedirs(hooks, exist_ok=True)
    for name, body in (("pre-commit", PRE_COMMIT), ("pre-push", PRE_PUSH)):
        path = os.path.join(hooks, name)
        with open(path, "w") as fh:
            fh.write(body)
        os.chmod(path, 0o755)


def _install_private_bits(dest):
    _write_hooks(dest)

    # Appending unconditionally is how this block ended up in one .gitignore
    # twice: `adopt` wrote it and a later call wrote it again.
    gitignore = os.path.join(dest, ".gitignore")
    existing = open(gitignore).read() if os.path.exists(gitignore) else ""
    if GITIGNORE_MARK not in existing:
        with open(gitignore, "a") as fh:
            if existing and not existing.endswith("\n"):
                fh.write("\n")
            fh.write("\n" + GITIGNORE_MARK + "\n")
            for r in RESTRICTED:
                fh.write(f"{r}/*\n!{r}/.gitkeep\n")
            fh.write("data.local.json\n")

    example = os.path.join(dest, "data.local.json.example")
    if not os.path.exists(example):
        with open(example, "w") as fh:
            json.dump({"assetsRoot": "/absolute/path/to/the/data"}, fh, indent=2)
            fh.write("\n")
