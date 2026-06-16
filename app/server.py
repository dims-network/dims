"""Flask app: JSON API for the wizard + static file serving.

Holds a single in-memory builder session (this is a local, single-user tool).
Staged uploads live under app/_staging/ until the build step copies them into
the generated project's assets/.
"""
import csv
import os
import uuid

from flask import Flask, Response, jsonify, request, send_from_directory

from . import precompute, project, validate

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(HERE, "static")
STAGING_DIR = os.path.join(HERE, "_staging")

# Infer the asset role from a filename.
TRANSCRIPT_SUFFIX = "_transcript.json"


def infer_role(filename: str) -> str:
    name = filename.lower()
    if name.endswith(".mp4"):
        return "video"
    if name.endswith(TRANSCRIPT_SUFFIX):
        return "transcript"
    if name.endswith(".json"):
        return "transcript"  # likely a transcript; user can correct
    if name.endswith(".csv"):
        return "timeseries"
    if name.endswith(".eaf"):
        return "elan"
    return "unknown"


def _suggest_ids(filename: str, role: str):
    """Suggest (videoID, dataType) from a filename following template conventions."""
    base = os.path.splitext(os.path.basename(filename))[0]
    if role == "video":
        return base, ""
    if role == "transcript":
        return base[: -len("_transcript")] if base.endswith("_transcript") else base, ""
    if role == "elan":
        return base, ""
    if role == "timeseries":
        # {videoID}_{dataType}; if no underscore, leave dataType blank
        if "_" in base:
            vid, dt = base.rsplit("_", 1)
            return vid, dt
        return base, ""
    return base, ""


def _csv_columns(path: str):
    try:
        with open(path, newline="") as f:
            header = next(csv.reader(f), [])
        return [c.strip() for c in header if c.strip()]
    except Exception:  # noqa: BLE001
        return []


def create_app():
    app = Flask(__name__, static_folder=None)
    os.makedirs(STAGING_DIR, exist_ok=True)

    # Single-session state.
    state = {
        "output_dir": None,
        "config": {},
        "staged": {},  # id -> {id, name, path, role, videoID, dataType, issues}
    }
    app.state = state

    # --- static ---
    @app.route("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.route("/static/<path:fname>")
    def static_files(fname):
        return send_from_directory(STATIC_DIR, fname)

    # --- API ---
    @app.post("/api/project")
    def api_project():
        data = request.get_json(force=True)
        output_dir = (data.get("output_dir") or "").strip()
        source = (data.get("template_source") or "").strip()
        meta = data.get("config") or {}
        if not output_dir:
            return jsonify(error="Please choose an output folder."), 400
        try:
            project.acquire_template(output_dir, source)
        except project.ProjectError as e:
            return jsonify(error=str(e)), 400
        state["output_dir"] = os.path.abspath(os.path.expanduser(output_dir))
        # seed metadata into config
        for k in ("title", "subtitle", "authors", "contacts", "defaultWindowSize"):
            if k in meta:
                state["config"][k] = meta[k]
        return jsonify(ok=True, output_dir=state["output_dir"], config=state["config"])

    @app.post("/api/upload")
    def api_upload():
        if "file" not in request.files:
            return jsonify(error="No file in request."), 400
        f = request.files["file"]
        fid = uuid.uuid4().hex
        safe_name = os.path.basename(f.filename or "file")
        staged_path = os.path.join(STAGING_DIR, f"{fid}__{safe_name}")
        f.save(staged_path)

        role = infer_role(safe_name)
        vid, dt = _suggest_ids(safe_name, role)
        entry = {
            "id": fid, "name": safe_name, "path": staged_path,
            "role": role, "videoID": vid, "dataType": dt,
            "columns": _csv_columns(staged_path) if role == "timeseries" else [],
        }
        entry["issues"] = validate.validate_file(role, staged_path)
        state["staged"][fid] = entry
        return jsonify(file={k: entry[k] for k in
                             ("id", "name", "role", "videoID", "dataType", "columns", "issues")})

    @app.post("/api/assign")
    def api_assign():
        data = request.get_json(force=True)
        fid = data.get("id")
        entry = state["staged"].get(fid)
        if not entry:
            return jsonify(error="Unknown file id."), 404
        for k in ("role", "videoID", "dataType"):
            if k in data:
                entry[k] = data[k]
        # re-validate with the (possibly new) role
        entry["issues"] = validate.validate_file(entry["role"], entry["path"])
        return jsonify(ok=True, file={k: entry[k] for k in
                       ("id", "name", "role", "videoID", "dataType", "columns", "issues")})

    @app.delete("/api/upload/<fid>")
    def api_delete_upload(fid):
        entry = state["staged"].pop(fid, None)
        if entry:
            try:
                os.remove(entry["path"])
            except OSError:
                pass
        return jsonify(ok=True)

    @app.route("/api/config", methods=["GET", "POST"])
    def api_config():
        if request.method == "POST":
            data = request.get_json(force=True)
            state["config"].update(data or {})
        return jsonify(config=_assemble_config())

    @app.post("/api/validate")
    def api_validate():
        cfg = _assemble_config()
        staged = list(state["staged"].values())
        file_issues = {e["id"]: validate.validate_file(e["role"], e["path"]) for e in staged}
        config_issues = validate.validate_config(cfg, staged)
        blocking = any(i["level"] == "error" for i in config_issues) or \
            any(i["level"] == "error" for lst in file_issues.values() for i in lst)
        return jsonify(config=cfg, file_issues=file_issues,
                       config_issues=config_issues, blocking=blocking)

    @app.post("/api/build")
    def api_build():
        if not state["output_dir"]:
            return jsonify(error="No project — complete step 1 first."), 400
        cfg = _assemble_config()
        staged = list(state["staged"].values())
        config_issues = validate.validate_config(cfg, staged)
        if any(i["level"] == "error" for i in config_issues):
            return jsonify(error="Validation failed.", config_issues=config_issues), 400

        placed = []
        for e in staged:
            if e["role"] not in project.ASSET_LAYOUT:
                continue
            if not e.get("videoID"):
                continue
            if e["role"] == "timeseries" and not e.get("dataType"):
                continue
            rel = project.place_asset(state["output_dir"], e["path"],
                                      e["role"], e["videoID"], e.get("dataType", ""))
            placed.append(rel)

        project.write_config(state["output_dir"], cfg)
        return jsonify(ok=True, placed=placed, config=cfg, output_dir=state["output_dir"])

    @app.post("/api/precompute")
    def api_precompute():
        if not state["output_dir"]:
            return jsonify(error="No project."), 400
        cfg = _assemble_config()
        do_rqa = bool(cfg.get("include_RQA"))
        do_cw = bool(cfg.get("include_crosswavelet"))
        proj = state["output_dir"]

        def generate():
            try:
                for line in precompute.run_precompute(proj, do_rqa, do_cw):
                    yield line
            except Exception as e:  # noqa: BLE001
                yield f"\n__ERROR__: {e}\n"

        return Response(generate(), mimetype="text/plain",
                        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})

    @app.post("/api/preview")
    def api_preview():
        if not state["output_dir"]:
            return jsonify(error="No project."), 400
        data = request.get_json(silent=True) or {}
        port = int(data.get("port") or 8000)
        url = precompute.start_preview(state["output_dir"], port)
        return jsonify(ok=True, url=url)

    # --- helpers ---
    def _assemble_config():
        """Derive videoIDs/dataTypes from staged files, merged with metadata + toggles."""
        cfg = dict(state["config"])
        video_ids = []
        data_types = {}
        for e in state["staged"].values():
            vid = e.get("videoID")
            if not vid:
                continue
            if vid not in video_ids:
                video_ids.append(vid)
            if e["role"] == "timeseries" and e.get("dataType"):
                data_types.setdefault(vid, [])
                if e["dataType"] not in data_types[vid]:
                    data_types[vid].append(e["dataType"])
        cfg["videoIDs"] = video_ids
        cfg["dataTypes"] = data_types
        cfg.setdefault("include_RQA", state["config"].get("include_RQA", []))
        cfg.setdefault("include_crosswavelet", state["config"].get("include_crosswavelet", []))
        cfg.setdefault("include_elan", state["config"].get("include_elan", False))
        cfg.setdefault("defaultWindowSize", state["config"].get("defaultWindowSize", 5))
        for k in ("title", "subtitle", "authors", "contacts"):
            cfg.setdefault(k, state["config"].get(k, ""))
        return cfg

    return app
