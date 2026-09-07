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


SHARED_STEPS = {"step_RQA.py", "step_cRQA.py", "step_crosswavelet.py",
                "requirements.txt"}


PRE_COMMIT = '''#!/bin/sh
# Refuses to stage data in a private case.
#
# This is the guard that matters: it stops data BEFORE it enters history, where
# removing it means a rewrite and the data has usually already been pushed.
# A .gitignore is not this guard -- `git add -f` walks straight through one.
python3 - "$@" <<'PY' || exit 1
import json, subprocess, sys
try:
    case = json.load(open("dims-case.json"))
except (OSError, ValueError):
    sys.exit(0)
if case.get("visibility") != "private":
    sys.exit(0)
allow = case.get("publishable") or []
staged = subprocess.run(["git", "diff", "--cached", "--name-only"],
                        capture_output=True, text=True).stdout.split()
restricted = case.get("restricted") or []
bad = []
for f in staged:
    if not any(f.startswith(r) for r in restricted):
        continue
    if any(f.startswith(a) for a in allow):
        continue
    if f.endswith(("MANIFEST.json", ".gitkeep")):
        continue
    bad.append(f)
if bad:
    print("BLOCKED: this study is declared private and these are data files:")
    for f in bad:
        print("  " + f)
    print("")
    print("If one of these is genuinely publishable, add its directory to")
    print("\\"publishable\\" in dims-case.json. Do not use --no-verify: CI")
    print("checks the same thing and will fail the branch.")
    sys.exit(1)
PY
'''


CI_YML = """name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  check:
    uses: dims-network/.github/.github/workflows/reusable-dashboard-ci.yml@main
    with:
      python_paths: ""
      js_glob: "vendor/dims-core/*.js vendor/dims-tabs/*.js"
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


def _install_private_bits(dest):
    hooks = os.path.join(dest, ".githooks")
    os.makedirs(hooks, exist_ok=True)
    for name in ("pre-commit", "pre-push"):
        p = os.path.join(hooks, name)
        with open(p, "w") as fh:
            fh.write(PRE_COMMIT)
        os.chmod(p, 0o755)
    with open(os.path.join(dest, ".gitignore"), "a") as fh:
        fh.write("\n# private study: data lives outside the repo\n")
        for r in RESTRICTED:
            fh.write(f"{r}/*\n!{r}/.gitkeep\n")
        fh.write("data.local.json\n")
    example = os.path.join(dest, "data.local.json.example")
    if not os.path.exists(example):
        with open(example, "w") as fh:
            json.dump({"assetsRoot": "/absolute/path/to/the/data"}, fh, indent=2)
            fh.write("\n")
