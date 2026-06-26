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


def run_rqa(project: str):
    vpy = _venv_python(project)
    yield from _stream(
        [vpy, "opt/step_RQA.py", "--config", "config.json", "--output-dir", "assets/rqa"],
        cwd=project,
    )


def run_crosswavelet(project: str):
    vpy = _venv_python(project)
    yield from _stream(
        [vpy, "opt/step_crosswavelet.py", "--config", "config.json",
         "--output-dir", "assets/crosswavelet", "--verbose"],
        cwd=project,
    )


def run_crqa(project: str):
    vpy = _venv_python(project)
    yield from _stream(
        [vpy, "opt/step_cRQA.py", "--config", "config.json", "--output-dir", "assets/crqa"],
        cwd=project,
    )


def run_precompute(project: str, do_rqa: bool, do_crosswavelet: bool, do_crqa: bool = False):
    """Full precompute pipeline as a single generator of log lines."""
    yield "=== Setting up Python environment ===\n"
    yield from create_venv(project)
    if do_rqa:
        yield "\n=== Running RQA ===\n"
        yield from run_rqa(project)
    if do_crosswavelet:
        yield "\n=== Running cross-wavelet ===\n"
        yield from run_crosswavelet(project)
    if do_crqa:
        yield "\n=== Running cross-RQA ===\n"
        yield from run_crqa(project)
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
