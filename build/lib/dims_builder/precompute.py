"""Run the analyses a generated project asks for, and its preview server.

The builder never reimplements an analysis. It used to subprocess the
template's own ``opt/step_*.py``, which is where the shared analyses lived
before the migration; they are now the ``dims-analysis`` package, so this
subprocesses ``dims-analysis run`` instead. A project may still ship its own
``opt/step_*.py`` -- a study-owned analysis, like ORTHO's categorical RQA --
and those are run after the shared ones.

That change was overdue and its absence was fatal: the bundled scaffold has no
``opt/`` at all, so step discovery found nothing and, worse, the environment
setup opened ``opt/requirements.txt`` before checking whether there was
anything to do. Every project the wizard generated failed at step 6 with a
FileNotFoundError, for the audience least able to read one.

All run_* functions are generators yielding text lines so the server can stream
progress to the browser.
"""
import os
import subprocess
import sys

# A study's own opt/requirements.txt, cleaned. One entry is dropped: `json`,
# which is stdlib and not pip-installable, and which the template this app was
# written against used to ship.
#
# There was a second repair, replacing `scipy==1.26.4` -- no such release; 1.26.4
# is a numpy version -- with an unpinned `scipy`. That template is gone (this
# module's own docstring says the bundled scaffold has no opt/ at all), and what
# the rule did instead was strip the version from *any* scipy pin, so a study
# that legitimately pinned scipy==1.11.4 had it quietly removed. Repairing a
# file nobody wrote any more, by un-pinning one somebody did, is worse than not
# repairing at all.
#
# `numpy` is imported by the scripts but may be absent from a study's list; it
# arrives transitively via pandas/scipy, and is added explicitly to be safe.
_BOGUS_REQS = {"json"}
_PIN_OVERRIDES = {}
_EXTRA_REQS = ["numpy"]


# The monorepo this builder is part of: apps/builder/dims_builder -> dims/.
# The analyses are installed from here because dims-network is not on PyPI.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))


def _venv_python(project: str) -> str:
    if os.name == "nt":
        return os.path.join(project, ".venv", "Scripts", "python.exe")
    return os.path.join(project, ".venv", "bin", "python")


def _stream(cmd, cwd):
    """Run `cmd` in `cwd`, yielding combined stdout/stderr lines, then a final
    status line. Yields '__EXIT__:<code>' last."""
    yield f"$ {' '.join(cmd)}\n"
    proc = subprocess.Popen(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    for line in iter(proc.stdout.readline, ""):
        yield line
    proc.stdout.close()
    code = proc.wait()
    yield f"__EXIT__:{code}\n"


def _filtered_requirements(project: str):
    """A cleaned copy of the project's own requirements, or None if it has none.

    Only a study that ships its own analyses has an opt/requirements.txt. The
    scaffold does not, and this used to be opened unconditionally.
    """
    src = os.path.join(project, "opt", "requirements.txt")
    if not os.path.exists(src):
        return None
    cleaned = os.path.join(project, "opt", "_requirements.builder.txt")
    lines = []
    with open(src) as f:
        for raw in f:
            name = raw.strip()
            if not name or name.startswith("#"):
                continue
            base = name.split("==")[0].split(">=")[0].strip().lower()
            if base in _BOGUS_REQS:
                continue
            lines.append(_PIN_OVERRIDES.get(base, name))
    for extra in _EXTRA_REQS:
        if extra not in {l.split("==")[0].split(">=")[0].strip().lower() for l in lines}:
            lines.append(extra)
    with open(cleaned, "w") as f:
        f.write("\n".join(lines) + "\n")
    return cleaned


def create_venv(project: str):
    """Create project/.venv with the analyses installed.

    dims-network is not on PyPI, so the package is installed editable from the
    monorepo this builder is running out of -- which is the only copy the user
    is guaranteed to have, since they are running its wizard.
    """
    vpy = _venv_python(project)
    if not os.path.exists(vpy):
        yield from _stream([sys.executable, "-m", "venv", ".venv"], cwd=project)
    yield from _stream([vpy, "-m", "pip", "install", "--upgrade", "pip"], cwd=project)
    yield from _stream([vpy, "-m", "pip", "install", "-e", _REPO_ROOT], cwd=project)
    reqs = _filtered_requirements(project)
    if reqs:
        yield "\nThis study ships analyses of its own; installing their requirements.\n"
        yield from _stream(
            [vpy, "-m", "pip", "install", "-r", os.path.relpath(reqs, project)],
            cwd=project,
        )


def _run_step(project, step_id, script, out_dir, extra=None):
    vpy = _venv_python(project)
    cmd = [vpy, script, "--config", "config.json", "--output-dir", out_dir]
    yield from _stream(cmd + list(extra or []), cwd=project)


# Analyses the project ships ITSELF, beyond the shared ones.
#
# This used to be how every analysis was found: the pre-migration template
# carried opt/step_RQA.py and friends, and the builder scanned for them. Those
# moved into the dims-analysis package, so scanning finds nothing in a modern
# project -- which is exactly what the scaffold is. What remains here is the
# study-owned case: ORTHO's categorical gaze RQA, Karnatak's mocap steps.
#
# Naming is the contract: step_<id>.py writes into assets/<id>/ and is switched
# on by include_<id>.
_SHARED_STEP_IDS = {"rqa", "crqa", "crosswavelet"}


def discover_steps(project: str):
    """[(step_id, script, output_dir, config_key), ...] the project ships itself."""
    opt = os.path.join(project, "opt")
    if not os.path.isdir(opt):
        return []
    found = []
    for name in sorted(os.listdir(opt)):
        if not (name.startswith("step_") and name.endswith(".py")):
            continue
        raw = name[len("step_"):-len(".py")]
        if raw.lower() in _SHARED_STEP_IDS:
            # A leftover copy of a shared analysis. Running it would produce a
            # second, older answer beside the package's.
            continue
        found.append((raw.lower(), os.path.join("opt", name),
                      os.path.join("assets", raw.lower()), f"include_{raw}"))
    return found


def _enabled(config: dict, key: str) -> bool:
    """Match the key case-insensitively: the historical ones are include_RQA and
    include_cRQA, which no naming rule would have predicted."""
    wanted = key.lower()
    return any(k.lower() == wanted and bool(v) for k, v in (config or {}).items())


def run_precompute(project: str, config: dict = None,
                   stop_on_failure: bool = True):
    """Run every analysis this project's config enables.

    Yields log lines. The project's config decides, rather than this function
    knowing three analyses by name -- which is what the three `do_rqa`-style
    booleans that used to sit here did. They were "still accepted so an older
    caller keeps working"; there was no older caller, in an app that is not
    published and not importable from outside this repository.

    A failure is announced as __FAILED__:<step> and, by default, stops the run.
    Continuing produced output that was partly stale and looked complete.
    """
    config = config or {}

    own = [s for s in discover_steps(project) if _enabled(config, s[3])]
    shared_wanted = any(k.lower().startswith("include_") and bool(v)
                        for k, v in (config or {}).items())

    # Check BEFORE building an environment. Setting up a venv first, and
    # reading a requirements file that a modern project does not have, is how
    # this used to fail for every project the wizard generated.
    if not shared_wanted and not own:
        yield "No analyses are enabled in config.json - nothing to precompute.\n"
        yield "=== Precompute complete ===\n"
        return

    yield "=== Setting up Python environment ===\n"
    yield from create_venv(project)

    failures = []

    if shared_wanted:
        yield "\n=== Running the analyses this config enables ===\n"
        code = None
        for line in _stream([_venv_python(project), "-m", "dims_analysis.cli",
                             "run", "--config", "config.json"], cwd=project):
            if line.startswith("__EXIT__:"):
                try:
                    code = int(line.split(":", 1)[1].strip() or 0)
                except ValueError:
                    code = 1
            yield line
        if code:
            failures.append("dims-analysis")
            yield "__FAILED__:dims-analysis\n"
            if stop_on_failure:
                yield "\nStopping: the analyses failed. Running the rest would leave\n"
                yield "output that is partly missing but looks complete.\n"
                own = []

    for step_id, script, out_dir, _key in own:
        yield f"\n=== Running {step_id} (this study's own) ===\n"
        code = None
        for line in _run_step(project, step_id, script, out_dir):
            if line.startswith("__EXIT__:"):
                try:
                    code = int(line.split(":", 1)[1].strip() or 0)
                except ValueError:
                    code = 1
            yield line
        if code:
            failures.append(step_id)
            yield f"__FAILED__:{step_id}\n"
            if stop_on_failure:
                yield f"\nStopping: {step_id} failed.\n"
                break

    if failures:
        yield f"\n=== Precompute FAILED: {', '.join(failures)} ===\n"
    else:
        yield "\n=== Precompute complete ===\n"


# --- Preview ---------------------------------------------------------------

_preview_procs = {}  # project -> Popen


def start_preview(project: str, port: int = 8000) -> str:
    """Launch the template's serve.py for `project`; return the local URL.

    Reuses the bundled python (serve.py is stdlib-only). Idempotent per project.
    """
    existing = _preview_procs.get(project)
    if existing and existing.poll() is None:
        return f"http://localhost:{port}"
    proc = subprocess.Popen(
        [sys.executable, "serve.py", str(port)], cwd=project,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    _preview_procs[project] = proc
    return f"http://localhost:{port}"
