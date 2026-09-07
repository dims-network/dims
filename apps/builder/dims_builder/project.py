"""Acquire the DIMS template scaffold, place assets, and write config.json.

This module never reimplements the template's analysis logic; it only copies
the template tree and arranges user files into the template's strict layout.
"""
import json
import json
import os
import re
import shutil
import subprocess
import tempfile

# The 10 keys the template's config.json consumes (and only these — nothing
# ORTHO-specific). See plan "Grounding".
CONFIG_KEYS = [
    "videoIDs",
    "dataTypes",
    "include_RQA",
    "include_crosswavelet",
    "include_cRQA",
    "include_elan",
    "defaultWindowSize",
    "title",
    "subtitle",
    "authors",
    "contacts",
]

DEFAULT_TEMPLATE_URL = "https://github.com/dims-network/DIMS_dashboard_template"

# The scaffold a new study starts from. It used to be a copy of the dashboard
# vendored into this repo as a git subtree, kept in step by hand with
# scripts/update-template.sh -- the last copy of the dashboard code left in the
# ecosystem, and the last thing that could drift.
#
# Now that the builder lives in the same repository as the core, it points
# straight at the scaffold. There is nothing to synchronise because there is
# nothing to copy.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))          # apps/builder/app/project.py -> repo root
BUNDLED_TEMPLATE = os.path.join(_REPO_ROOT, "packages", "dims-case-scaffold")

# Markers that a directory really is the DIMS template scaffold.
# What makes a directory a dashboard scaffold. "opt" used to be here, back when
# every project carried its own copy of the analysis scripts; those come from
# the dims-analysis package now, so a project without opt/ is normal.
TEMPLATE_MARKERS = ["config.json", "serve.py", "assets"]

# Scaffold files that are *code*, refreshed into an existing project on every
# build so a project made from an older core picks up fixes. Everything else --
# config.json and the user's assets/ -- is the study's own and is left alone.
#
# The dashboard itself is no longer copied file by file: it arrives as a pinned,
# vendored core written by `dims-case`. What remains here is the page that loads
# it and the local preview server.
TEMPLATE_CODE = ("index.html", "serve.py", ".github", "vendor")

_IGNORE = shutil.ignore_patterns(".git", "__pycache__", ".venv", "node_modules")

# Role -> (subdirectory under assets/, filename builder taking videoID & dataType)
ASSET_LAYOUT = {
    "video": ("videos", lambda vid, dt: f"{vid}.mp4"),
    "timeseries": ("timeseries", lambda vid, dt: f"{vid}_{dt}.csv"),
    "transcript": ("transcripts", lambda vid, dt: f"{vid}_transcript.json"),
    "elan": ("elan", lambda vid, dt: f"{vid}.eaf"),
}


class ProjectError(Exception):
    """Raised for user-facing project setup failures."""


def _looks_like_url(source: str) -> bool:
    return bool(re.match(r"^(https?://|git@)", source.strip()))


def is_template_dir(path: str) -> bool:
    return all(os.path.exists(os.path.join(path, m)) for m in TEMPLATE_MARKERS)


def _copy_into(src_item: str, dest_item: str) -> None:
    """Copy a file or directory tree from `src_item` onto `dest_item` (merging
    directories, overwriting files)."""
    if os.path.isdir(src_item):
        shutil.copytree(src_item, dest_item, dirs_exist_ok=True, ignore=_IGNORE)
    else:
        shutil.copyfile(src_item, dest_item)


def _resolve_local_template(source: str):
    """Return (local_dir, cleanup) for a template `source`.

    A git URL is shallow-cloned into a temp dir (cleanup removes it); a local
    path or the bundled template is returned as-is (cleanup is a no-op). Raises
    ProjectError if the resolved directory isn't a DIMS template.
    """
    if _looks_like_url(source):
        tmp = tempfile.mkdtemp(prefix="dims_template_")
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", source, tmp],
                check=True, capture_output=True, text=True,
            )
        except FileNotFoundError:
            shutil.rmtree(tmp, ignore_errors=True)
            raise ProjectError("git is not installed; use a local template path instead.")
        except subprocess.CalledProcessError as e:
            shutil.rmtree(tmp, ignore_errors=True)
            raise ProjectError(f"git clone failed: {e.stderr.strip() or e}")
        shutil.rmtree(os.path.join(tmp, ".git"), ignore_errors=True)
        if not is_template_dir(tmp):
            shutil.rmtree(tmp, ignore_errors=True)
            raise ProjectError("Cloned template is missing expected files (config.json/serve.py/opt/assets).")
        return tmp, lambda: shutil.rmtree(tmp, ignore_errors=True)

    src = os.path.abspath(os.path.expanduser(source))
    if not os.path.isdir(src):
        raise ProjectError(f"Template path not found: {src}")
    if not is_template_dir(src):
        raise ProjectError(f"'{src}' does not look like a DIMS template (missing config/opt/assets).")
    return src, (lambda: None)


def acquire_template(output_dir: str, source: str) -> None:
    """Populate `output_dir` with the template scaffold.

    `source` may be:
      * empty / "bundled"  → copy the template bundled with the builder (default;
                             no git, no network — the non-coder path);
      * a git URL          → cloned (to fetch the latest template);
      * a local path       → copied (excluding .git/).

    If `output_dir` is already a DIMS project, the template's *code* (opt/ scripts
    and frontend — see TEMPLATE_CODE) is refreshed from `source` so updated
    analysis steps reach existing projects, while the user's config.json and
    assets/ are preserved. Raises ProjectError on failure.
    """
    output_dir = os.path.abspath(os.path.expanduser(output_dir))
    source = (source or "bundled").strip()
    if source.lower() == "bundled":
        source = BUNDLED_TEMPLATE
        if not is_template_dir(source):
            raise ProjectError(
                "The built-in template is missing from this builder install "
                f"(expected at {source}). Reinstall the builder, or choose a "
                "different template source."
            )

    exists = os.path.exists(output_dir) and bool(os.listdir(output_dir))
    if exists and not is_template_dir(output_dir):
        raise ProjectError(
            f"Output folder '{output_dir}' is not empty and is not a DIMS template. "
            "Choose an empty folder or an already-acquired project."
        )

    local_src, cleanup = _resolve_local_template(source)
    try:
        if exists:
            # Already a project: refresh template code (opt/ scripts, frontend),
            # leaving the user's config.json and assets/ untouched.
            for item in TEMPLATE_CODE:
                s = os.path.join(local_src, item)
                if os.path.exists(s):
                    _copy_into(s, os.path.join(output_dir, item))
        else:
            os.makedirs(output_dir, exist_ok=True)
            shutil.copytree(local_src, output_dir, dirs_exist_ok=True, ignore=_IGNORE)
    finally:
        cleanup()

    # Write the pinned core, exactly as `dims-case` does. Both callers go
    # through dims_case.core so a study built by the wizard and one built from
    # the command line are the same study -- the wizard's user is the one least
    # able to debug a difference.
    try:
        from dims_case.core import _write_vendor, _write_index, _core_version
        _write_index(output_dir)
        hashes = _write_vendor(output_dir)
        case_path = os.path.join(output_dir, "dims-case.json")
        if not os.path.exists(case_path):
            with open(case_path, "w") as fh:
                json.dump({"case": os.path.basename(os.path.abspath(output_dir)),
                           "visibility": "private",   # the safe default; the wizard asks
                           "dimsCore": _core_version(),
                           "publishable": [],
                           "vendorHashes": hashes}, fh, indent=2)
                fh.write("\n")
    except ImportError as exc:
        raise ProjectError(
            "Could not write the dashboard core into the project "
            f"({exc}). Install with: pip install 'dims-network[builder]'") from exc

    if not is_template_dir(output_dir):
        raise ProjectError("Acquired scaffold is missing expected files (config.json/serve.py/assets).")


def place_asset(output_dir: str, staged_path: str, role: str, video_id: str, data_type: str = "") -> str:
    """Copy a staged file into assets/ under the template's exact name.

    Returns the relative destination path (e.g. assets/timeseries/v1_bodysync.csv).
    """
    if role not in ASSET_LAYOUT:
        raise ProjectError(f"Unknown asset role: {role}")
    subdir, name_fn = ASSET_LAYOUT[role]
    dest_dir = os.path.join(output_dir, "assets", subdir)
    os.makedirs(dest_dir, exist_ok=True)
    filename = name_fn(video_id, data_type)
    dest = os.path.join(dest_dir, filename)
    shutil.copyfile(staged_path, dest)
    return os.path.join("assets", subdir, filename)


def write_config(output_dir: str, cfg: dict) -> str:
    """Write config.json containing exactly the template's keys."""
    out = {k: cfg.get(k) for k in CONFIG_KEYS}
    # Sensible fallbacks for anything left unset.
    out.setdefault("videoIDs", out.get("videoIDs") or [])
    out["videoIDs"] = out["videoIDs"] or []
    out["dataTypes"] = out.get("dataTypes") or {}
    out["include_RQA"] = out.get("include_RQA") or []
    out["include_crosswavelet"] = out.get("include_crosswavelet") or []
    out["include_cRQA"] = out.get("include_cRQA") or []
    out["include_elan"] = bool(out.get("include_elan"))
    out["defaultWindowSize"] = out.get("defaultWindowSize") or 5
    for k in ("title", "subtitle", "authors", "contacts"):
        out[k] = out.get(k) or ""
    path = os.path.join(output_dir, "config.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    return path
