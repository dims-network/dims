"""Run the template's own analysis scripts and preview server in the generated
project. The builder never reimplements the analyses — it subprocesses the
template's opt/step_*.py and serve.py.

All run_* functions are generators yielding text lines so the server can stream
progress to the browser.
"""
import os
import subprocess
import sys

# The template's opt/requirements.txt has two known defects we repair when
# generating the install list (we never touch the template itself):
#   * a stray `json` line — json is stdlib, not pip-installable.
#   * `scipy==1.26.4` — no such scipy release exists (1.26.4 is a *numpy*
#     version; it's a typo upstream), so the pin can never resolve.
# `numpy` is imported by the scripts but absent from the template's list; it
# arrives transitively via pandas/scipy, but we add it explicitly to be safe.
_BOGUS_REQS = {"json"}
_PIN_OVERRIDES = {"scipy": "scipy"}  # drop the impossible exact pin
_EXTRA_REQS = ["numpy"]


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


def _filtered_requirements(project: str) -> str:
    """Write a cleaned requirements file (stray 'json' removed) and return path."""
    src = os.path.join(project, "opt", "requirements.txt")
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
    """Create project/.venv and install the template's analysis requirements."""
    vpy = _venv_python(project)
    if not os.path.exists(vpy):
        yield from _stream([sys.executable, "-m", "venv", ".venv"], cwd=project)
    yield from _stream([vpy, "-m", "pip", "install", "--upgrade", "pip"], cwd=project)
    reqs = _filtered_requirements(project)
    yield from _stream(
        [vpy, "-m", "pip", "install", "-r", os.path.relpath(reqs, project)],
        cwd=project,
    )


# Legacy per-analysis runners. Kept only so an older caller does not break;
# discover_steps() is what the wizard uses now.
def run_rqa(project: str):
    yield from _run_step(project, "rqa", "opt/step_RQA.py", "assets/rqa")


def run_crosswavelet(project: str):
    yield from _run_step(project, "crosswavelet", "opt/step_crosswavelet.py",
                         "assets/crosswavelet", extra=["--verbose"])


def run_crqa(project: str):
    yield from _run_step(project, "crqa", "opt/step_cRQA.py", "assets/crqa")


def _run_step(project, step_id, script, out_dir, extra=None):
    vpy = _venv_python(project)
    cmd = [vpy, script, "--config", "config.json", "--output-dir", out_dir]
    yield from _stream(cmd + list(extra or []), cwd=project)


# Which analyses a generated project offers, and how to run each one.
#
# This used to be three hardcoded functions plus a three-branch orchestrator, so
# adding one analysis meant edits in four files across this repo. A project now
# declares its own: any opt/step_*.py it ships can be run, and its config key
# decides whether it should be.
#
# Naming is the contract, and it is the template's: step_<id>.py writes into
# assets/<id>/ and is switched on by include_<id>.
def discover_steps(project: str):
    """[(step_id, script, output_dir, config_key), ...] for this project."""
    opt = os.path.join(project, "opt")
    if not os.path.isdir(opt):
        return []
    found = []
    for name in sorted(os.listdir(opt)):
        if not (name.startswith("step_") and name.endswith(".py")):
            continue
        raw = name[len("step_"):-len(".py")]
        found.append((raw.lower(), os.path.join("opt", name),
                      os.path.join("assets", raw.lower()), f"include_{raw}"))
    return found


def _enabled(config: dict, key: str) -> bool:
    """Match the key case-insensitively: the historical ones are include_RQA and
    include_cRQA, which no naming rule would have predicted."""
    wanted = key.lower()
    return any(k.lower() == wanted and bool(v) for k, v in (config or {}).items())


def run_precompute(project: str, do_rqa=None, do_crosswavelet=None, do_crqa=None,
                   config: dict = None, stop_on_failure: bool = True):
    """Run every analysis this project's config enables.

    Yields log lines, as before. The booleans are still accepted so an older
    caller keeps working, but passing `config` is what lets the project decide
    rather than this function knowing three analyses by name.

    A failure is announced as __FAILED__:<step> and, by default, stops the run.
    Continuing produced output that was partly stale and looked complete.
    """
    if config is None:
        config = {}
        for key, flag in (("include_RQA", do_rqa), ("include_crosswavelet", do_crosswavelet),
                          ("include_cRQA", do_crqa)):
            if flag:
                config[key] = True

    yield "=== Setting up Python environment ===\n"
    yield from create_venv(project)

    steps = [s for s in discover_steps(project) if _enabled(config, s[3])]
    if not steps:
        yield "\nNo analyses are enabled in config.json - nothing to precompute.\n"
        yield "=== Precompute complete ===\n"
        return

    failures = []
    for step_id, script, out_dir, _key in steps:
        yield f"\n=== Running {step_id} ===\n"
        code = None
        for line in _run_step(project, step_id, script, out_dir,
                              extra=["--verbose"] if step_id == "crosswavelet" else None):
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
                yield f"\nStopping: {step_id} failed. Running the rest would leave output\n"
                yield "that is partly missing but looks complete.\n"
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
