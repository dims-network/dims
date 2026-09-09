"""Create the study, place the user's files in it, and write its config.json.

This module never reimplements an analysis. It copies the scaffold and arranges
files into the layout `docs/contracts/assets.md` describes, and everything about
*being a study* -- the pinned core, the privacy guards, the workflows -- is
delegated to `dims_case`, which is what `dims-case new` uses. A study the wizard
makes and a study made from the command line must be the same study: the
wizard's user is the one least able to work out why they differ.
"""
import json
import os
import shutil

# Every key a built-in tab or a shared analysis reads, and only those. The
# schema also documents keys owned by tabs that live in a study rather than in
# the core -- `include_trajectory`, `include_dtw` -- and the wizard does not
# offer them: a control for a tab that is not there is a dead end for exactly
# the person this tool is written for.
#
# `videoIDs` and `dataTypes` are derived from the staged files; the rest come
# from the wizard's own steps.
CONFIG_KEYS = [
    # identity
    "title", "subtitle", "authors", "contacts", "defaultWindowSize",
    # what there is
    "videoIDs", "dataTypes",
    # which tabs
    "include_RQA", "include_cRQA", "include_crosswavelet", "include_elan",
    "include_network",
    # multi-camera (dims-core's own: setupPerspectiveControl / buildVideoSrc)
    "perspectives", "videoPerspectives", "videoSrcTemplate",
    "fallbackVideoSrcTemplate",
    # per-analysis tuning
    "analysis",
]

#: Keys that mean something by their absence and are written only when set. A
#: study that never touched multi-camera should not carry `perspectives: []`,
#: which reads as a decision nobody made.
OPTIONAL_KEYS = {
    "include_network", "perspectives", "videoPerspectives",
    "videoSrcTemplate", "fallbackVideoSrcTemplate", "analysis",
    "subtitle", "authors", "contacts",
}

# The scaffold a new study starts from. It used to be a copy of the dashboard
# vendored into this repo as a git subtree, kept in step by hand with
# scripts/update-template.sh -- the last copy of the dashboard code left in the
# ecosystem, and the last thing that could drift.
#
# Now that the builder lives in the same repository as the core, it points
# straight at the scaffold. There is nothing to synchronise because there is
# nothing to copy.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))  # apps/builder/dims_builder/project.py -> repo root
BUNDLED_TEMPLATE = os.path.join(_REPO_ROOT, "packages", "dims-case-scaffold")

# What makes a directory a study. "opt" used to be here, back when every project
# carried its own copy of the analysis scripts; those come from the
# dims-analysis package now, so a project without opt/ is normal.
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


def _local_dims_case():
    """`dims_case.core` from **this** repository, whatever else is installed.

    The premise of this whole module is that a study the wizard makes and one
    `dims-case new` makes are the same study. That has to mean the `dims-case`
    shipped beside this builder, and a plain `import dims_case` does not
    guarantee it: an editable install pointing at another checkout wins, and the
    wizard then copies this repository's scaffold and another repository's
    vendored core into one folder, stamped with the other one's version.

    Found on a development machine where an old editable install pointed at a
    1.5.1 checkout: every study the wizard produced would have carried v2
    payloads and v1.5.1 tabs. The dashboard says so now rather than drawing
    nothing, which is how it surfaced -- but a study that cannot work should not
    be built in the first place.

    `core.py` is loaded by path rather than the package, because the package's
    `__init__` re-exports through an absolute `from dims_case.core import ...`,
    which finds the installed copy again and puts us back where we started.
    """
    import importlib.util
    import sys

    core_py = os.path.join(_REPO_ROOT, "packages", "dims-case", "dims_case", "core.py")
    if not os.path.exists(core_py):                  # pragma: no cover - install
        raise ProjectError(
            "The dashboard core is missing from this install (expected "
            f"{core_py}). Reinstall with: pip install 'dims-network[builder]'")

    cached = sys.modules.get("_dims_case_local")
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location("_dims_case_local", core_py)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_dims_case_local"] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:                         # pragma: no cover - install
        sys.modules.pop("_dims_case_local", None)
        raise ProjectError(
            f"Could not load the dashboard core from {core_py}: {exc}") from exc
    if os.path.abspath(module.CORE_ROOT) != os.path.abspath(_REPO_ROOT):
        raise ProjectError(                          # pragma: no cover - defensive
            f"The dashboard core resolved to {module.CORE_ROOT}, not to this "
            f"builder's own repository ({_REPO_ROOT}). A study built from two "
            f"different checkouts would not work.")
    return module


def is_template_dir(path: str) -> bool:
    return all(os.path.exists(os.path.join(path, m)) for m in TEMPLATE_MARKERS)


def _copy_into(src_item: str, dest_item: str) -> None:
    """Copy a file or directory tree, merging directories and overwriting files."""
    if os.path.isdir(src_item):
        shutil.copytree(src_item, dest_item, dirs_exist_ok=True, ignore=_IGNORE)
    else:
        shutil.copyfile(src_item, dest_item)


def create_project(output_dir: str, visibility: str = "private") -> dict:
    """Make `output_dir` a study, or refresh one that is already there.

    There is one scaffold and it is in this repository, so there is nothing to
    choose. The wizard used to ask -- offering a git URL and a local path -- and
    every answer but the default was a way to get it wrong: the URL pointed at
    the pre-monorepo template, which carries a dashboard with no vendored core,
    so a study built from it would have been a fork.

    `visibility` is the researcher's declaration, not an inference. It is asked
    because `docs/contracts/data-visibility.md` says it must be: much DIMS data
    is video of identifiable people, and "private" is what turns on the
    pre-commit hook, the pre-push hook and the CI guard. This used to be
    hard-coded to "private" and then contradicted by writing none of the guards
    -- a study that declared itself private and blocked nothing, handed to the
    person least able to notice.

    Returns a dict describing what was done, for the wizard to report.
    """
    if visibility not in ("private", "public"):
        raise ProjectError(
            f"Visibility must be 'private' or 'public', not {visibility!r}.")

    output_dir = os.path.abspath(os.path.expanduser(output_dir))
    if not is_template_dir(BUNDLED_TEMPLATE):
        raise ProjectError(
            "The DIMS scaffold is missing from this install (expected at "
            f"{BUNDLED_TEMPLATE}). Reinstall with: pip install 'dims-network[builder]'")

    existing = os.path.exists(output_dir) and bool(os.listdir(output_dir))
    if existing and not is_template_dir(output_dir):
        raise ProjectError(
            f"'{output_dir}' is not empty and is not a DIMS study. Choose an "
            f"empty folder, or a folder the builder made earlier.")

    if existing:
        # Refresh the code, leave config.json and assets/ alone: they are the
        # study's own and the build step rewrites config.json deliberately.
        for item in TEMPLATE_CODE:
            src = os.path.join(BUNDLED_TEMPLATE, item)
            if os.path.exists(src):
                _copy_into(src, os.path.join(output_dir, item))
    else:
        os.makedirs(output_dir, exist_ok=True)
        shutil.copytree(BUNDLED_TEMPLATE, output_dir, dirs_exist_ok=True,
                        ignore=_IGNORE)

    return _write_case(output_dir, visibility, reused=existing)


def _write_case(output_dir: str, visibility: str, reused: bool) -> dict:
    """The pinned core, the workflows and the privacy guards, through dims_case.

    Every one of these used to be either missing or hand-written here. Going
    through the same functions `dims-case new` uses is what makes a study the
    wizard produces and a study made from the command line the same thing --
    which this module's own docstring has claimed for some time.
    """
    core = _local_dims_case()
    core._write_index(output_dir)
    core._register_study_tabs(output_dir)
    hashes = core._write_vendor(output_dir)
    core._write_workflows(output_dir, visibility)
    if visibility == "private":
        core._install_private_bits(output_dir)

    case_path = os.path.join(output_dir, "dims-case.json")
    case = {}
    if os.path.exists(case_path):
        try:
            with open(case_path) as fh:
                case = json.load(fh)
        except (OSError, ValueError):
            case = {}
    case.update({
        "case": case.get("case") or os.path.basename(output_dir),
        "visibility": visibility,
        "dimsCore": core._core_version(),
        "publishable": case.get("publishable") or [],
        # One list, read by every guard. Writing it here rather than letting the
        # guards fall back is the difference between a study that declares
        # itself private and one that is: an earlier example omitted the key and
        # the study written from it blocked nothing.
        "restricted": list(core.RESTRICTED),
        "vendorHashes": hashes,
    })
    with open(case_path, "w") as fh:
        json.dump(case, fh, indent=2)
        fh.write("\n")

    if not is_template_dir(output_dir):
        raise ProjectError(
            "The study is missing config.json, serve.py or assets/ after being "
            "created. This is a bug in the builder, not something you did.")

    return {
        "output_dir": output_dir,
        "visibility": visibility,
        "reused": reused,
        "dims_core": case["dimsCore"],
        # The one thing a private study needs a human to do, and the one thing
        # nothing can do for them: hooks are per-clone.
        "hooks_command": ("git config core.hooksPath .githooks"
                          if visibility == "private" else None),
    }


def read_project(output_dir: str) -> dict:
    """A study's own description of itself, for reopening it in the wizard.

    Reading a study back is what turns this from a generator into something a
    researcher returns to. Without it the first correction after a build sends
    them into config.json by hand, which is the audience this tool exists for.
    """
    output_dir = os.path.abspath(os.path.expanduser(output_dir))
    if not os.path.isdir(output_dir):
        raise ProjectError(f"No such folder: {output_dir}")
    if not is_template_dir(output_dir):
        raise ProjectError(
            f"'{output_dir}' is not a DIMS study: a study has config.json, "
            f"serve.py and assets/. Pick the folder a build produced.")

    try:
        with open(os.path.join(output_dir, "config.json")) as fh:
            config = json.load(fh)
    except (OSError, ValueError) as exc:
        raise ProjectError(f"Could not read that study's config.json: {exc}")

    case = {}
    case_path = os.path.join(output_dir, "dims-case.json")
    if os.path.exists(case_path):
        try:
            with open(case_path) as fh:
                case = json.load(fh)
        except (OSError, ValueError):
            case = {}

    return {
        "output_dir": output_dir,
        "config": config,
        "visibility": case.get("visibility") or "private",
        "dims_core": case.get("dimsCore"),
        "assets": _existing_assets(output_dir),
    }


def _existing_assets(output_dir: str) -> list:
    """What is already in assets/, as the wizard's own file rows.

    Named by the conventions in `docs/contracts/assets.md`, read back: the name
    *is* the interface, so it is also what says which session and measure a file
    belongs to.
    """
    found = []
    for role, (subdir, _name) in ASSET_LAYOUT.items():
        directory = os.path.join(output_dir, "assets", subdir)
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if name.startswith("."):
                continue
            path = os.path.join(directory, name)
            if not os.path.isfile(path):
                continue
            base = os.path.splitext(name)[0]
            video_id, data_type = base, ""
            if role == "timeseries" and "_" in base:
                video_id, data_type = base.rsplit("_", 1)
            elif role == "transcript" and base.endswith("_transcript"):
                video_id = base[: -len("_transcript")]
            found.append({"role": role, "name": name, "path": path,
                          "videoID": video_id, "dataType": data_type})
    return found


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


SCHEMA_PATH = os.path.join(_REPO_ROOT, "docs", "contracts", "config.schema.json")


def _schema():
    try:
        with open(SCHEMA_PATH) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _prune(cfg: dict) -> dict:
    """Only the keys the core reads, and only the optional ones that were set.

    Writing every key empty makes a config that reads as a series of decisions
    nobody made -- `perspectives: []` beside `videoSrcTemplate: ""` says this
    study considered multi-camera and declined, which is not what happened.
    `include_elan: false` is different and stays: it is a switch with two
    meanings, and off is one of them.
    """
    out = {}
    for key in CONFIG_KEYS:
        value = cfg.get(key)
        if key in OPTIONAL_KEYS and value in (None, "", [], {}, False):
            continue
        out[key] = value
    out["videoIDs"] = out.get("videoIDs") or []
    out["dataTypes"] = out.get("dataTypes") or {}
    for key in ("include_RQA", "include_cRQA", "include_crosswavelet"):
        out[key] = out.get(key) or []
    out["include_elan"] = bool(out.get("include_elan"))
    out["defaultWindowSize"] = out.get("defaultWindowSize") or 5
    out["title"] = out.get("title") or ""
    return out


def schema_problems(cfg: dict) -> list:
    """What `docs/contracts/config.schema.json` says is wrong with `cfg`.

    The builder validates against the same file CI validates every study
    against, so a config it writes cannot be one the core would reject. Without
    this the failure surfaces much later and in the worst possible form -- an
    empty tab, which is indistinguishable from a study that has no data.

    An unreadable or missing schema is not a reason to refuse to build: the
    wizard should still work from a checkout that has been trimmed.
    """
    schema = _schema()
    if schema is None:
        return []
    try:
        import jsonschema
    except ImportError:                              # pragma: no cover - install
        return []
    validator = jsonschema.Draft202012Validator(schema)
    problems = []
    for error in sorted(validator.iter_errors(cfg), key=lambda e: list(e.path)):
        where = ".".join(str(p) for p in error.path) or "config.json"
        problems.append(f"{where}: {error.message}")
    return problems


def write_config(output_dir: str, cfg: dict) -> str:
    """Write config.json, refusing a config the core would not accept."""
    out = _prune(cfg)
    problems = schema_problems(out)
    if problems:
        raise ProjectError(
            "This configuration does not match what a DIMS study accepts:\n  - "
            + "\n  - ".join(problems))
    path = os.path.join(output_dir, "config.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
        f.write("\n")
    return path
