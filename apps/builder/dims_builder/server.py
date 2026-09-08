"""Flask app: JSON API for the wizard + static file serving.

Holds a single in-memory builder session (this is a local, single-user tool).
Staged uploads live under app/_staging/ until the build step copies them into
the generated project's assets/.
"""
import csv
import os
import shutil
import uuid

from flask import Flask, Response, jsonify, request, send_file, send_from_directory

from . import media, precompute, project, validate

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(HERE, "static")
STAGING_DIR = os.path.join(HERE, "_staging")

# Two complete sessions that ship with the builder, so someone can see a working
# dashboard before they have data of their own -- and so a bug report can say
# "with the samples" and mean one specific thing.
SAMPLES_DIR = os.path.join(os.path.dirname(HERE), "samples")

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
        visibility = (data.get("visibility") or "private").strip()
        meta = data.get("config") or {}
        if not output_dir:
            return jsonify(error="Please choose a folder for the study."), 400
        try:
            report = project.create_project(output_dir, visibility)
        except project.ProjectError as e:
            return jsonify(error=str(e)), 400
        state["output_dir"] = report["output_dir"]
        state["visibility"] = visibility
        for k in ("title", "subtitle", "authors", "contacts", "defaultWindowSize"):
            if k in meta:
                state["config"][k] = meta[k]
        return jsonify(ok=True, config=state["config"], **report)

    @app.post("/api/open")
    def api_open():
        """Reopen a study the builder made earlier, with everything filled in.

        Files already in assets/ are staged from where they are, so reopening
        does not copy a study's data anywhere -- for a private study that would
        be the wrong thing to do quietly.
        """
        data = request.get_json(force=True)
        output_dir = (data.get("output_dir") or "").strip()
        if not output_dir:
            return jsonify(error="Please choose the study's folder."), 400
        try:
            found = project.read_project(output_dir)
        except project.ProjectError as e:
            return jsonify(error=str(e)), 400

        state["output_dir"] = found["output_dir"]
        state["visibility"] = found["visibility"]
        state["config"] = dict(found["config"])
        state["staged"] = {}
        for item in found["assets"]:
            fid = uuid.uuid4().hex
            entry = {
                "id": fid, "name": item["name"], "path": item["path"],
                "role": item["role"], "videoID": item["videoID"],
                "dataType": item["dataType"],
                "columns": _csv_columns(item["path"]) if item["role"] == "timeseries" else [],
                "in_place": True,
            }
            entry["issues"] = validate.validate_file(item["role"], item["path"])
            state["staged"][fid] = entry
        return jsonify(ok=True, output_dir=found["output_dir"],
                       visibility=found["visibility"],
                       dims_core=found["dims_core"],
                       config=_assemble_config(),
                       files=[_public(e) for e in state["staged"].values()])

    @app.post("/api/samples")
    def api_samples():
        """Stage the sample sessions that ship with the builder.

        Copied into staging and pushed through the same inference, splitting and
        validation an upload takes -- so the button exercises the real path
        rather than a shortcut around it, and `session2.csv` still demonstrates
        the auto-split into three measures.
        """
        if not os.path.isdir(SAMPLES_DIR):
            return jsonify(error="The sample data is missing from this install "
                                 f"(expected at {SAMPLES_DIR})."), 400
        names = sorted(n for n in os.listdir(SAMPLES_DIR)
                       if not n.startswith(".") and not n.endswith(".md")
                       and os.path.isfile(os.path.join(SAMPLES_DIR, n)))
        if not names:
            return jsonify(error="The sample folder is empty."), 400
        added = []
        for name in names:
            with open(os.path.join(SAMPLES_DIR, name), "rb") as fh:
                added.extend(_stage_stream(fh, name))
        return jsonify(files=added, count=len(added))

    @app.post("/api/upload")
    def api_upload():
        if "file" not in request.files:
            return jsonify(error="No file in request."), 400
        f = request.files["file"]
        added = _stage_stream(f, os.path.basename(f.filename or "file"))
        return jsonify(files=added, file=added[0] if added else None)

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
        return jsonify(ok=True, file=_public(entry))

    @app.delete("/api/upload/<fid>")
    def api_delete_upload(fid):
        entry = state["staged"].pop(fid, None)
        # A file reopened from a study lives in its assets/, not in staging.
        # Removing it here would delete the study's data because someone took a
        # row off a list, which is not what that gesture means.
        if entry and not entry.get("in_place"):
            try:
                os.remove(entry["path"])
            except OSError:
                pass
        return jsonify(ok=True)

    @app.get("/api/staged/<fid>")
    def api_staged(fid):
        """Serve a staged upload (range-enabled) for the align step's previews:
        the video element seeks into it, and CSVs are fetched to look up values."""
        entry = state["staged"].get(fid)
        if not entry or not os.path.exists(entry["path"]):
            return jsonify(error="Unknown file id."), 404
        mime = {"video": "video/mp4", "timeseries": "text/csv"}.get(entry["role"])
        return send_file(entry["path"], mimetype=mime, conditional=True)

    @app.get("/api/sessions")
    def api_sessions():
        return jsonify(sessions=_session_summary(),
                       ffmpeg_available=media.ffmpeg_exe() is not None)

    # Trim/pad are stored as *specs* on the staged entries and only applied to
    # copies at build time. The uploaded originals are never modified, so edits
    # are non-destructive and freely re-adjustable.
    @app.post("/api/trim_video")
    def api_trim_video():
        data = request.get_json(force=True)
        vid = data.get("videoID")
        video = next((e for e in state["staged"].values()
                      if e["role"] == "video" and e.get("videoID") == vid), None)
        if not video:
            return jsonify(error=f"No video found for session '{vid}'."), 404
        if data.get("clear"):
            video.pop("trim", None)
            return jsonify(ok=True, sessions=_session_summary(),
                           ffmpeg_available=media.ffmpeg_exe() is not None)
        try:
            start = float(data.get("start", 0))
            end = float(data.get("end", 0))
        except (TypeError, ValueError):
            return jsonify(error="Trim start/end must be numbers."), 400
        if end <= start:
            return jsonify(error="Trim window end must be after start."), 400
        if not media.ffmpeg_exe():
            return jsonify(error="ffmpeg is unavailable; run: pip install imageio-ffmpeg"), 400
        video["trim"] = {"start": start, "end": end}
        return jsonify(ok=True, sessions=_session_summary(),
                       ffmpeg_available=media.ffmpeg_exe() is not None)

    @app.post("/api/pad_timeseries")
    def api_pad_timeseries():
        data = request.get_json(force=True)
        vid = data.get("videoID")
        series = [e for e in state["staged"].values()
                  if e["role"] == "timeseries" and e.get("videoID") == vid]
        if not series:
            return jsonify(error=f"No time-series CSVs found for session '{vid}'."), 404
        try:
            pad_start = max(0.0, float(data.get("pad_start", 0)))
            pad_end = max(0.0, float(data.get("pad_end", 0)))
        except (TypeError, ValueError):
            return jsonify(error="Padding amounts must be numbers."), 400
        for e in series:
            if pad_start <= 0 and pad_end <= 0:
                e.pop("pad", None)
            else:
                e["pad"] = {"start": pad_start, "end": pad_end}
        return jsonify(ok=True, sessions=_session_summary(),
                       ffmpeg_available=media.ffmpeg_exe() is not None)

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
            # Apply any align spec to the *placed copy* — the staged original is
            # left untouched, so the user keeps their pristine source files.
            dest = os.path.join(state["output_dir"], rel)
            try:
                if e["role"] == "video" and e.get("trim"):
                    media.trim_video(dest, e["trim"]["start"], e["trim"]["end"])
                elif e["role"] == "timeseries" and e.get("pad"):
                    media.pad_timeseries(dest, e["pad"]["start"], e["pad"]["end"])
            except (RuntimeError, ValueError) as exc:
                return jsonify(error=f"Aligning '{rel}': {exc}"), 400
            placed.append(rel)

        project.write_config(state["output_dir"], cfg)
        return jsonify(ok=True, placed=placed, config=cfg, output_dir=state["output_dir"])

    @app.post("/api/precompute")
    def api_precompute():
        if not state["output_dir"]:
            return jsonify(error="No project."), 400
        cfg = _assemble_config()
        proj = state["output_dir"]

        def generate():
            # Pass the config rather than three booleans: the project's own
            # opt/step_*.py decide what can run, so adding an analysis to the
            # template no longer needs a change here.
            try:
                for line in precompute.run_precompute(proj, config=cfg):
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
    PUBLIC_FIELDS = ("id", "name", "role", "videoID", "dataType", "columns",
                     "issues", "in_place")

    def _public(entry):
        return {k: entry.get(k) for k in PUBLIC_FIELDS}

    def _stage_stream(stream, safe_name):
        """Stage one incoming file and return the rows the wizard should show.

        One path for an upload and for the sample data, so the button that loads
        the samples exercises what a real file goes through rather than a
        shortcut around it -- including the split below, which is the behaviour
        the samples exist to demonstrate.
        """
        fid = uuid.uuid4().hex
        staged_path = os.path.join(STAGING_DIR, f"{fid}__{safe_name}")
        if hasattr(stream, "save"):
            stream.save(staged_path)
        else:
            with open(staged_path, "wb") as out:
                shutil.copyfileobj(stream, out)

        role = infer_role(safe_name)
        vid, dt = _suggest_ids(safe_name, role)

        # A CSV with Time plus several value columns becomes one single-column
        # CSV per measure, which is the layout every analysis reads.
        if role == "timeseries":
            base = os.path.splitext(safe_name)[0]
            splits = media.split_timeseries_csv(staged_path, STAGING_DIR, fid, base)
            if splits:
                rows = []
                for sp in splits:
                    entry = {
                        "id": sp["id"], "name": sp["name"], "path": sp["path"],
                        "role": "timeseries", "videoID": base,
                        "dataType": sp["dataType"],
                        "columns": ["Time", sp["column"]],
                    }
                    entry["issues"] = validate.validate_file("timeseries", sp["path"])
                    state["staged"][sp["id"]] = entry
                    rows.append(_public(entry))
                try:
                    os.remove(staged_path)      # only the splits are kept
                except OSError:
                    pass
                return rows

        entry = {
            "id": fid, "name": safe_name, "path": staged_path,
            "role": role, "videoID": vid, "dataType": dt,
            "columns": _csv_columns(staged_path) if role == "timeseries" else [],
        }
        entry["issues"] = validate.validate_file(role, staged_path)
        state["staged"][fid] = entry
        return [_public(entry)]

    def _session_summary():
        """Per-session video & time-series geometry for the align step.

        Groups staged files by videoID; for each session reports the video with
        its *original* duration and any trim spec, and every time-series CSV with
        its original Time bounds and any pad spec. Durations are the originals —
        the frontend computes the effective (trimmed/padded) extents for preview.
        """
        sessions = {}
        order = []
        for e in state["staged"].values():
            vid = e.get("videoID")
            if not vid:
                continue
            if vid not in sessions:
                sessions[vid] = {"videoID": vid, "video": None, "series": []}
                order.append(vid)
            s = sessions[vid]
            if e["role"] == "video" and s["video"] is None:
                s["video"] = {"id": e["id"], "name": e["name"],
                              "duration": media.video_duration(e["path"]),
                              "trim": e.get("trim")}
            elif e["role"] == "timeseries":
                s["series"].append({"id": e["id"], "name": e["name"],
                                    "dataType": e.get("dataType", ""),
                                    "bounds": media.series_bounds(e["path"]),
                                    "pad": e.get("pad")})
        return [sessions[v] for v in order]

    def _assemble_config():
        """The study's config: what the files say, plus what the wizard was told.

        `videoIDs` and `dataTypes` are **derived** and never edited by hand --
        they are a description of what is in assets/, and a config that
        disagrees with the folder produces a tab that draws nothing. Everything
        else comes from the wizard's own steps and is passed through, so a key
        the wizard learns tomorrow needs no change here.
        """
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

        # The coherence null is expensive and only the network reads it, so the
        # analysis defaults it on when the network is on. Recording the number
        # here means the study says what it will do before it does it, rather
        # than the wizard and the analysis each having an opinion.
        if cfg.get("include_network"):
            tuning = dict(cfg.get("analysis") or {})
            cw = dict(tuning.get("crosswavelet") or {})
            cw.setdefault("mcCount", 100)
            tuning["crosswavelet"] = cw
            cfg["analysis"] = tuning
        return cfg

    return app
