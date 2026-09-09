"use strict";

// ---- tiny helpers ----------------------------------------------------------
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  const ct = res.headers.get("content-type") || "";
  const body = ct.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) throw new Error((body && body.error) || res.statusText);
  return body;
}

function setMsg(step, text, kind = "") {
  const el = $(`#msg-${step}`);
  el.textContent = text || "";
  el.className = "msg " + kind;
}

// ---- wizard state ----------------------------------------------------------
const state = {
  step: 1,
  maxStep: 1,
  files: [],          // {id, name, role, videoID, dataType, columns, issues}
  rqa: new Set(),     // selected data types (single-series RQA)
  cw: new Set(),      // selected pair keys "a|b" (cross-wavelet)
  crqa: new Set(),    // selected pair keys "a|b" (cross-RQA)
  elan: false,
  network: false,
  placedByName: false,   // the diagram was filled in by inference, not by hand
  // The figures on the diagram, in the order they are drawn. `match` is only
  // ever carried in from a config that had one; the wizard writes no regular
  // expressions any more.
  people: [],           // [{id, label, color, match?}]
  // Keyed by data type: where on the diagram each measure sits, and separately
  // whatever a hand-written config put there that the diagram cannot show.
  effectors: {},        // {dataType: {group?, label?, part?}}
  effectorExtras: {},   // {dataType: {x?, y?}}
  armed: null,          // a node clicked once, waiting for the other end
  opened: false,      // reopened an existing study rather than making one
};

// Data types and group labels come from a researcher's filenames and typing,
// and go straight into innerHTML below.
function esc(v) {
  return String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

const ROLES = ["video", "timeseries", "transcript", "elan", "unknown"];

function gotoStep(n) {
  if (n > state.maxStep) return;
  state.step = n;
  $$(".panel").forEach((p) => (p.hidden = +p.dataset.panel !== n));
  $$(".step").forEach((b) => {
    const s = +b.dataset.step;
    b.classList.toggle("active", s === n);
    b.classList.toggle("done", s < state.maxStep && s !== n);
    b.disabled = s > state.maxStep;
  });
  if (n === 3) renderAlign();
  if (n === 4) { renderAnalysisTypes(); renderDiagram(); reflectNetwork(); }
  if (n === 5) refreshValidation();
  if (n === 7) { renderDeploy(); renderPrivacyReminder(); }
}

function unlockStep(n) {
  state.maxStep = Math.max(state.maxStep, n);
}

// ---- STEP 1: the study -----------------------------------------------------
// There is one scaffold and it is in this repository, so the wizard does not ask
// where to get it. It used to, and every answer but the default was a way to get
// it wrong.
function mode() {
  return $('input[name="mode"]:checked').value;   // "new" | "open"
}
function visibility() {
  return $('input[name="vis"]:checked').value;    // "private" | "public"
}

$$('input[name="mode"]').forEach((r) =>
  r.addEventListener("change", () => {
    const opening = mode() === "open";
    // Visibility is settled when a study is created -- changing it means
    // rewriting its guards and workflows, which is `dims-case`'s job, not a
    // radio button's. Everything else stays editable, because editing it is
    // what reopening is for: the title is the likeliest thing anyone comes
    // back to change.
    $("#new-only").hidden = opening;
    $("#open-visibility").hidden = true;
    $("#btn-create").textContent = opening ? "Open study \u2192" : "Create study \u2192";
    $("#dir-hint").textContent = opening
      ? "The folder of a study the builder made earlier."
      : "A new or empty folder. The dashboard is created inside it.";
  })
);

$("#btn-create").addEventListener("click", async () => {
  const dir = $("#output_dir").value.trim();
  if (!dir) { setMsg(1, "Please give a folder.", "error"); return; }

  if (mode() === "open") {
    setMsg(1, "Opening\u2026", "spinner");
    try {
      const r = await api("/api/open", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ output_dir: dir }),
      });
      state.opened = true;
      state.outputDir = r.output_dir;
      state.files = r.files || [];
      applyOpenedConfig(r.config || {}, r.visibility);
      const vis = $("#open-visibility");
      vis.hidden = false;
      vis.innerHTML = `This study is <strong>${r.visibility}</strong>. ` +
        "To change that, edit <code>visibility</code> in its " +
        "<code>dims-case.json</code> and run <code>dims-case sync</code> — it " +
        "rewrites the guards and workflows, which a setting here could not do.";
      renderFiles();
      setMsg(1, `Opened ${r.output_dir} \u2014 ${state.files.length} file(s), ` +
                `built with core ${r.dims_core || "unknown"}.`, "ok");
      showPrivacyNote(r.visibility, null);
      // Everything is known, so nothing needs re-deciding to get to the end.
      unlockStep(7);
      gotoStep(2);
    } catch (e) {
      setMsg(1, e.message, "error");
    }
    return;
  }

  setMsg(1, "Creating\u2026", "spinner");
  try {
    const r = await api("/api/project", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        output_dir: dir,
        visibility: visibility(),
        config: {
          title: $("#title").value,
          subtitle: $("#subtitle").value,
          authors: $("#authors").value,
          contacts: $("#contacts").value,
          defaultWindowSize: Number($("#defaultWindowSize").value) || 5,
        },
      }),
    });
    state.outputDir = r.output_dir;
    setMsg(1, (r.reused ? "Refreshed " : "Created ") + r.output_dir +
              ` (core ${r.dims_core}).`, "ok");
    showPrivacyNote(r.visibility, r.hooks_command);
    unlockStep(2);
    gotoStep(2);
  } catch (e) {
    setMsg(1, e.message, "error");
  }
});

// The one thing a private study needs a person to do, and the one thing nothing
// can do for them: git hooks are per-clone, so a fresh clone has none.
function showPrivacyNote(vis, hooks) {
  state.visibility = vis;
  state.hooks = hooks;
  const box = $("#privacy-note");
  if (vis !== "private") { box.hidden = true; return; }
  box.hidden = false;
  box.innerHTML =
    "<strong>This study is private.</strong> Its data is kept out of git by " +
    "hooks, and git only runs them once you say so \u2014 in this folder, and " +
    "in every clone of it:" +
    (hooks ? `<pre class="codebox">${hooks}</pre>` : "") +
    "<small>Until then nothing stops a commit from including a recording.</small>";
}

// Reading a built study back into the wizard's own controls.
function applyOpenedConfig(cfg, vis) {
  const set = (id, v) => { const el = $("#" + id); if (el && v != null) el.value = v; };
  set("title", cfg.title); set("subtitle", cfg.subtitle);
  set("authors", cfg.authors); set("contacts", cfg.contacts);
  set("defaultWindowSize", cfg.defaultWindowSize);
  $$('input[name="vis"]').forEach((r) => { r.checked = r.value === (vis || "private"); });

  state.rqa = new Set(cfg.include_RQA || []);
  state.cw = new Set((cfg.include_crosswavelet || []).map((p) => p.join("|")));
  state.crqa = new Set((cfg.include_cRQA || []).map((p) => p.join("|")));
  state.elan = !!cfg.include_elan;
  state.network = !!cfg.include_network;
  $("#t_rqa").checked = state.rqa.size > 0;
  $("#t_cw").checked = state.cw.size > 0;
  $("#t_crqa").checked = state.crqa.size > 0;
  $("#t_elan").checked = state.elan;
  $("#t_network").checked = state.network;

  const tuning = cfg.analysis || {};
  const num = (id, v) => { if (v != null) $("#" + id).value = v; };
  num("rqa_window", (tuning.rqa || {}).window);
  num("rqa_step", (tuning.rqa || {}).step);
  num("rqa_target", (tuning.rqa || {}).targetRecurrence);
  num("crqa_window", (tuning.crqa || {}).window);
  num("crqa_step", (tuning.crqa || {}).step);
  num("crqa_target", (tuning.crqa || {}).targetRecurrence);
  const cw = tuning.crosswavelet || {};
  num("cw_mc", cw.mcCount); num("cw_maxt", cw.maxTimePoints);
  num("cw_maxf", cw.maxFreqPoints);
  if (Array.isArray(cw.scaleAvgBand)) $("#cw_band").value = cw.scaleAvgBand.join(", ");
  if (cw.saveFullResolution != null) $("#cw_full").checked = !!cw.saveFullResolution;

  if (Array.isArray(cfg.perspectives) && cfg.perspectives.length) {
    $("#cameras").open = true;
    $("#perspectives").value = cfg.perspectives.join(", ");
    $("#videoSrcTemplate").value = cfg.videoSrcTemplate || "";
    $("#fallbackVideoSrcTemplate").value = cfg.fallbackVideoSrcTemplate || "";
  }
  const net = cfg.include_network;
  state.people = [];
  state.effectors = {};
  state.effectorExtras = {};
  state.placedByName = false;
  if (net && typeof net === "object") {
    (Array.isArray(net.groups) ? net.groups : []).forEach((g, i) => {
      addPerson(g.label || "Person " + (i + 1), g.color, g.match);
    });
    if (Array.isArray(net.band)) $("#network_band").value = net.band.join(", ");

    (Array.isArray(net.effectors) ? net.effectors : []).forEach((eff) => {
      if (!eff || !eff.series) return;
      const row = {};
      if (eff.group) row.group = eff.group;
      if (eff.label) row.label = eff.label;
      if (eff.part) row.part = eff.part;
      state.effectors[eff.series] = row;
      const extra = {};
      if (eff.x !== undefined) extra.x = eff.x;
      if (eff.y !== undefined) extra.y = eff.y;
      if (Object.keys(extra).length) state.effectorExtras[eff.series] = extra;
    });

    // Every study that exists predates `effectors` and says all of this by
    // naming its measures `teacher_righthandspeed`. Rather than opening with an
    // empty diagram and asking the researcher to place six nodes they already
    // described, run the same inference the tab runs and show the answer. What
    // they press Next on is then the explicit form, which is the migration.
    if (!Object.keys(state.effectors).length && state.people.some((p) => p.match)) {
      state.placedByName = placeByName(cfg);
    }
  }
}

// The tab's own inference, run once at load: the group's regular expression says
// whose it is, and a body-part token in what is left of the name says where.
// Kept deliberately close to grouping()/nodeLabel()/bodyPart() in
// packages/dims-tabs/network.js -- if they disagree, opening a study in the
// wizard would silently move its nodes.
const BODY_TOKENS = ["lefthand", "righthand", "hand", "nose", "head",
                     "torso", "hip", "foot"];

function placeByName(cfg) {
  const types = new Set();
  Object.values(cfg.dataTypes || {}).forEach((list) => (list || []).forEach((t) => types.add(t)));
  (cfg.include_crosswavelet || []).forEach((pair) => (pair || []).forEach((t) => types.add(t)));
  let placed = 0;
  types.forEach((name) => {
    const person = state.people.find((p) => p.match && new RegExp(p.match, "i").test(name));
    if (!person) return;
    const rest = name.replace(new RegExp(person.match, "i"), "").replace(/^[_\-\s]+/, "");
    const token = BODY_TOKENS.find((t) => rest.toLowerCase().indexOf(t) !== -1)
      || BODY_TOKENS.find((t) => name.toLowerCase().indexOf(t) !== -1);
    if (!token) return;
    state.effectors[name] = { group: person.label, part: SPOT_ALIASES[token] || token };
    if (rest) state.effectors[name].label = rest;
    placed++;
  });
  return placed > 0;
}

// ---- STEP 2: files ---------------------------------------------------------
const dz = $("#dropzone");
["dragenter", "dragover"].forEach((ev) =>
  dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); })
);
["dragleave", "drop"].forEach((ev) =>
  dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); })
);
dz.addEventListener("drop", (e) => uploadFiles(e.dataTransfer.files));
$("#filepick").addEventListener("change", (e) => uploadFiles(e.target.files));

// The example study ships with the builder, so someone can reach a finished
// dashboard before they have data of their own -- and so "it does not work with
// the samples" means one specific thing.
$("#btn-samples").addEventListener("click", async () => {
  const btn = $("#btn-samples");
  btn.disabled = true;
  setMsg(2, "Loading the example study\u2026", "spinner");
  try {
    const r = await api("/api/samples", { method: "POST" });
    const added = r.files || [];
    added.forEach((f) => state.files.push(f));
    const sessions = new Set(added.map((f) => f.videoID).filter(Boolean));
    // Only claim the split when one happened. A message that describes what
    // usually happens rather than what just did is how someone learns to stop
    // reading them.
    const split = added.some((f) => f.role === "timeseries" &&
      f.dataType && !f.name.toLowerCase().includes(f.dataType.toLowerCase()));
    setMsg(2, `Loaded ${added.length} file(s) across ${sessions.size} session(s).` +
              (split ? " A CSV with several measurement columns was split into one file per measure." : ""),
           "ok");
    renderFiles();
  } catch (e) {
    setMsg(2, e.message, "error");
  } finally {
    btn.disabled = false;
  }
});

async function uploadFiles(fileList) {
  for (const f of fileList) {
    const fd = new FormData();
    fd.append("file", f);
    setMsg(2, `Uploading ${f.name}…`, "spinner");
    try {
      const r = await api("/api/upload", { method: "POST", body: fd });
      // A multi-column CSV comes back as several files (one per value column).
      const got = r.files || (r.file ? [r.file] : []);
      got.forEach((file) => state.files.push(file));
    } catch (e) {
      setMsg(2, `${f.name}: ${e.message}`, "error");
    }
  }
  setMsg(2, "");
  renderFiles();
}

function renderFiles() {
  const wrap = $("#filelist");
  wrap.innerHTML = "";
  for (const f of state.files) {
    const row = document.createElement("div");
    row.className = "filerow" + (f.in_place ? " in-place" : "");
    const roleOpts = ROLES.map((r) => `<option value="${r}" ${r === f.role ? "selected" : ""}>${r}</option>`).join("");
    const showDt = f.role === "timeseries";
    row.innerHTML = `
      <div class="fname">${f.name}</div>
      <select data-k="role" data-id="${f.id}">${roleOpts}</select>
      <input data-k="videoID" data-id="${f.id}" placeholder="session / video ID" value="${f.videoID || ""}" />
      <input data-k="dataType" data-id="${f.id}" placeholder="data type" value="${f.dataType || ""}" ${showDt ? "" : "disabled"} />
      <button class="del" data-id="${f.id}" title="Remove">&times;</button>
      <div class="issues">${(f.issues || []).map((i) => `<div class="issue ${i.level}">${i.level === "error" ? "✗" : "⚠"} ${i.message}</div>`).join("")}</div>
    `;
    wrap.appendChild(row);
  }
  wrap.querySelectorAll("[data-k]").forEach((el) =>
    el.addEventListener("change", () => assign(el.dataset.id, el.dataset.k, el.value))
  );
  wrap.querySelectorAll(".del").forEach((el) =>
    el.addEventListener("click", () => removeFile(el.dataset.id))
  );
  renderPerspectives();
}

// ---- multi-camera ----------------------------------------------------------
// dims-core builds a camera selector from `perspectives` and resolves each file
// through `videoSrcTemplate`. Which angles a given session actually has is a
// separate list, because recordings fail and not every session has every angle.
function sessionIDs() {
  const seen = [];
  state.files.forEach((f) => {
    if (f.videoID && !seen.includes(f.videoID)) seen.push(f.videoID);
  });
  return seen;
}

function perspectiveNames() {
  return $("#perspectives").value.split(",").map((s) => s.trim()).filter(Boolean);
}

function renderPerspectives() {
  const box = $("#videoPerspectives");
  const names = perspectiveNames();
  const sessions = sessionIDs();
  if (!names.length || !sessions.length) { box.innerHTML = ""; return; }
  box.innerHTML = "<p class=\"hint\">Which angles each session actually has. " +
    "Leave a session with none ticked and it falls back to the first that exists.</p>" +
    sessions.map((sid) => `
      <div class="filerow">
        <div class="fname">${sid}</div>
        <div class="chips">${names.map((n) => `
          <label class="chip"><input type="checkbox" data-sid="${sid}" value="${n}" /> ${n}</label>
        `).join("")}</div>
      </div>`).join("");
}
$("#perspectives").addEventListener("input", renderPerspectives);

function collectPerspectives() {
  const names = perspectiveNames();
  if (!names.length) return {};
  const per = {};
  $$('#videoPerspectives input[type="checkbox"]').forEach((cb) => {
    if (!cb.checked) return;
    (per[cb.dataset.sid] = per[cb.dataset.sid] || []).push(cb.value);
  });
  const out = { perspectives: names };
  if (Object.keys(per).length) out.videoPerspectives = per;
  const tmpl = $("#videoSrcTemplate").value.trim();
  const fb = $("#fallbackVideoSrcTemplate").value.trim();
  if (tmpl) out.videoSrcTemplate = tmpl;
  if (fb) out.fallbackVideoSrcTemplate = fb;
  return out;
}

// ---- STEP 3: align video & data -------------------------------------------
// Trim/pad are non-destructive specs stored on the server; the bars here preview
// the *effective* (trimmed/padded) extents live against a shared playback axis.
const fmt = (s) => (s == null ? "—" : `${(+s).toFixed(2)}s`);

async function renderAlign() {
  const list = $("#align-list");
  let data;
  try {
    data = await api("/api/sessions");
  } catch (e) {
    list.innerHTML = `<p class="hint">${e.message}</p>`;
    return;
  }
  const sessions = data.sessions.filter((s) => s.video || s.series.length);
  if (!sessions.length) {
    list.innerHTML = '<p class="hint">No sessions yet — add files in the previous step.</p>';
    return;
  }
  // Nothing to decide is worth saying. An empty-looking step reads as one that
  // failed to load, and the reader cannot tell which.
  const comparable = sessions.filter((s) => s.video && s.series.length);
  if (!comparable.length) {
    list.innerHTML = '<div class="note">Nothing to align: no session here has ' +
      'both a video and measurements to compare it against. Go on to the next step.</div>';
    return;
  }
  list.innerHTML = "";
  sessions.forEach((s) => list.appendChild(alignCard(s, data.ffmpeg_available)));
}

// Effective (post-edit) durations derived from the live control values.
function videoKeep(s, trim) {
  const dur = s.video ? s.video.duration : null;
  if (dur == null) return null;
  if (!trim) return dur;
  return Math.max(0, trim.end - trim.start);
}
function seriesSpan(ser) {           // original signal span (≈ its max)
  return ser.bounds ? ser.bounds.max : 0;
}
function seriesTotal(ser, pad) {     // span after padding
  return seriesSpan(ser) + (pad ? pad.start + pad.end : 0);
}

// --- client-side CSV value lookup (for the slider scrubber) -----------------
function parseCsvLookup(text) {
  const lines = text.trim().split(/\r?\n/);
  const header = lines[0].split(",").map((h) => h.trim());
  // Time column matched case-insensitively (e.g. "time", "TIME").
  const tIdx = header.findIndex((h) => h.toLowerCase() === "time");
  const cols = header.map((h, i) => ({ h, i })).filter((x) => x.h && x.i !== tIdx);
  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    const parts = lines[i].split(",");
    const t = parseFloat(parts[tIdx]);
    if (!isNaN(t)) rows.push({ t, parts });
  }
  rows.sort((a, b) => a.t - b.t);
  return { cols, rows };
}
function lookupAt(lk, t) {
  const rows = lk.rows;
  if (!rows.length) return null;
  let lo = 0, hi = rows.length - 1;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (rows[mid].t < t) lo = mid + 1; else hi = mid; }
  if (lo > 0 && Math.abs(rows[lo - 1].t - t) < Math.abs(rows[lo].t - t)) lo--;
  return rows[lo];
}

function alignCard(s, ffmpegOK) {
  // Live edit state for this card (seeded from the server's stored specs).
  const vDur = s.video ? s.video.duration : null;
  const dataDur = s.series.length ? Math.max(...s.series.map(seriesSpan)) : null;
  const aligned = vDur != null && dataDur != null && Math.abs(vDur - dataDur) < 0.1;
  const ed = {
    trim: s.video && s.video.trim ? { ...s.video.trim } : null,
    pad: { start: 0, end: 0 },
  };
  const firstPad = s.series.find((x) => x.pad);
  if (firstPad) ed.pad = { ...firstPad.pad };
  const lookups = {};  // series id -> parsed CSV, filled in lazily

  const card = document.createElement("div");
  card.className = "align-card";
  card.innerHTML = `
    <div class="align-head"><strong>${s.videoID}</strong>
      <span class="align-durs"></span></div>
    <div class="align-decision"></div>
    <div class="tracks"></div>`;
  const durs = card.querySelector(".align-durs");
  const tracks = card.querySelector(".tracks");

  // --- shared-timeline preview ------------------------------------------------
  function drawTracks() {
    const keep = videoKeep(s, ed.trim);
    const dataDur = s.series.length
      ? Math.max(...s.series.map((x) => seriesTotal(x, ed.pad))) : 0;
    const scale = Math.max(keep || 0, dataDur, 0.001);
    const pct = (t) => `${(100 * t / scale).toFixed(3)}%`;
    let html = "";
    if (vDur != null) {
      html += `<div class="track">
        <div class="track-label">🎞 video</div>
        <div class="track-lane">
          <div class="bar bar-video" style="left:0;width:${pct(keep)}">${keep.toFixed(2)}s</div>
        </div></div>`;
    }
    s.series.forEach((ser) => {
      const total = seriesTotal(ser, ed.pad);
      const sigStart = ed.pad.start, sigEnd = ed.pad.start + seriesSpan(ser);
      html += `<div class="track">
        <div class="track-label">📈 ${ser.dataType || ser.name}</div>
        <div class="track-lane">
          <div class="bar bar-pad" style="left:0;width:${pct(total)}"></div>
          <div class="bar bar-signal" style="left:${pct(sigStart)};width:${pct(sigEnd - sigStart)}">${seriesSpan(ser).toFixed(2)}s</div>
        </div></div>`;
    });
    // Alignment marker at the video's end (where data should reach).
    if (vDur != null) {
      html += `<div class="track-axis"><span style="left:${pct(keep)}">video ends ${keep.toFixed(2)}s</span></div>`;
    }
    tracks.innerHTML = html;

    const keepTxt = vDur != null ? `video ${fmt(keep)}` : "no video";
    const dataTxt = s.series.length ? `data ${fmt(dataDur)}` : "no data";
    const gap = (vDur != null && s.series.length) ? +(keep - dataDur).toFixed(2) : null;
    durs.innerHTML = `${keepTxt} &nbsp;·&nbsp; ${dataTxt}` +
      (gap != null
        ? ` &nbsp;·&nbsp; <span class="${Math.abs(gap) < 0.05 ? "ok" : "warn"}">${Math.abs(gap) < 0.05 ? "✓ aligned" : (gap > 0 ? "+" : "") + gap + "s"}</span>`
        : "");
  }

  // Look up + show the value of every series at time t (for the scrubber).
  async function ensureLookups() {
    await Promise.all(s.series.map(async (ser) => {
      if (lookups[ser.id]) return;
      try {
        const text = await (await fetch(`/api/staged/${ser.id}`)).text();
        lookups[ser.id] = parseCsvLookup(text);
      } catch (e) { lookups[ser.id] = { cols: [], rows: [] }; }
    }));
  }
  function valuesAt(t) {
    const parts = [];
    s.series.forEach((ser) => {
      const lk = lookups[ser.id];
      if (!lk) return;
      const row = lookupAt(lk, t);
      if (!row) return;
      lk.cols.forEach((c) => {
        const label = lk.cols.length > 1 ? `${ser.dataType || ser.name}·${c.h}` : (ser.dataType || ser.name);
        parts.push(`${label} <strong>${(row.parts[c.i] ?? "—")}</strong>`);
      });
    });
    return parts.join(" &nbsp; ");
  }

  // --- (a) trim ---------------------------------------------------------------
  let trim = null;
  if (vDur != null) {
    const defStart = ed.trim ? ed.trim.start : 0;
    const defEnd = ed.trim ? ed.trim.end : Math.min(dataDur != null ? dataDur : vDur, vDur);
    trim = document.createElement("div");
    trim.className = "align-tool";
    trim.hidden = !ed.trim;  // revealed via the decision buttons (or if already set)
    trim.innerHTML = `
      <div class="align-tool-title">a) Trim video — drag the handles to pick the window to keep</div>
      <video class="vpreview" src="/api/staged/${s.video.id}" muted preload="metadata"></video>
      <div class="scrub-readout"></div>
      <div class="dual-range">
        <input type="range" class="t-start" min="0" max="${vDur}" step="0.01" value="${defStart}" />
        <input type="range" class="t-end" min="0" max="${vDur}" step="0.01" value="${defEnd}" />
      </div>
      <div class="align-row">
        <span class="t-readout"></span>
        <button class="ghost t-reset">Reset</button>
        <button class="primary t-apply" ${ffmpegOK ? "" : "disabled title='ffmpeg unavailable — run: pip install imageio-ffmpeg'"}>Apply trim</button>
      </div>`;
    const startEl = trim.querySelector(".t-start");
    const endEl = trim.querySelector(".t-end");
    const readout = trim.querySelector(".t-readout");
    const scrub = trim.querySelector(".scrub-readout");
    const video = trim.querySelector(".vpreview");
    const win = () => {
      let a = +startEl.value, b = +endEl.value;
      return a <= b ? [a, b] : [b, a];
    };
    const sync = () => {
      const [a, b] = win();
      ed.trim = (a > 0.001 || b < vDur - 0.001) ? { start: a, end: b } : null;
      readout.innerHTML = `keep <strong>${a.toFixed(2)}–${b.toFixed(2)}s</strong> (length <strong>${(b - a).toFixed(2)}s</strong>)`;
      drawTracks();
    };
    // Dragging either handle scrubs the video frame + shows series values at t.
    const scrubTo = async (t) => {
      t = Math.max(0, Math.min(t, vDur));
      try { video.currentTime = t; } catch (e) { /* metadata not ready yet */ }
      await ensureLookups();
      scrub.innerHTML = `<span class="scrub-t">@ ${t.toFixed(2)}s</span> ${valuesAt(t)}`;
    };
    [startEl, endEl].forEach((el) =>
      el.addEventListener("input", () => { sync(); scrubTo(+el.value); }));
    trim.querySelector(".t-reset").addEventListener("click", async () => {
      startEl.value = 0; endEl.value = vDur; sync();
      await applyAlign("/api/trim_video", { videoID: s.videoID, clear: true }, `Resetting ${s.videoID}…`);
    });
    trim.querySelector(".t-apply").addEventListener("click", async () => {
      const [a, b] = win();
      await applyAlign("/api/trim_video", { videoID: s.videoID, start: a, end: b }, `Trimming ${s.videoID}…`);
    });
    card.appendChild(trim);
    sync();
  }

  // --- (b) pad ----------------------------------------------------------------
  let pad = null;
  if (s.series.length) {
    pad = document.createElement("div");
    pad.className = "align-tool";
    pad.hidden = !firstPad;
    pad.innerHTML = `
      <div class="align-tool-title">b) Pad time-series with zeros at start and/or end</div>
      <div class="align-row">
        <label class="pad-lbl">start <input type="number" class="p-start" min="0" step="0.1" value="${ed.pad.start || 0}" /> s</label>
        <label class="pad-lbl">end <input type="number" class="p-end" min="0" step="0.1" value="${ed.pad.end || 0}" /> s</label>
        <button class="primary p-apply">Apply padding</button>
      </div>
      <small class="hint">Applies to all ${s.series.length} CSV(s) in this session. Padding the start shifts the signal later.</small>`;
    const pStart = pad.querySelector(".p-start");
    const pEnd = pad.querySelector(".p-end");
    const sync = () => {
      ed.pad = { start: Math.max(0, +pStart.value || 0), end: Math.max(0, +pEnd.value || 0) };
      drawTracks();
    };
    pStart.addEventListener("input", sync);
    pEnd.addEventListener("input", sync);
    pad.querySelector(".p-apply").addEventListener("click", async () => {
      await applyAlign("/api/pad_timeseries",
        { videoID: s.videoID, pad_start: ed.pad.start, pad_end: ed.pad.end },
        `Padding ${s.videoID}…`);
    });
    card.appendChild(pad);
  }

  // --- decision: tell the user whether alignment is needed, gate the tools ----
  const decision = card.querySelector(".align-decision");
  function renderDecision() {
    let msg;
    if (vDur == null) msg = `<span class="warn">⚠ No video for this session — only padding is available.</span>`;
    else if (dataDur == null) msg = `<span class="warn">⚠ No time-series for this session — only trimming is available.</span>`;
    else if (aligned) msg = `<span class="ok">✓ Video and data are both ~${fmt(vDur)} — already aligned. No action needed, but you can adjust below.</span>`;
    else {
      const d = +(vDur - dataDur).toFixed(2);
      msg = `<span class="warn">⚠ Video is ${fmt(vDur)} but data is ${fmt(dataDur)} (${d > 0 ? "video is " + d + "s longer" : "data is " + (-d) + "s longer"}). Choose how to align:</span>`;
    }
    const btns = [];
    if (trim) btns.push(`<button class="ghost d-trim">✂ Trim video</button>`);
    if (pad) btns.push(`<button class="ghost d-pad">0⃣ Pad time-series</button>`);
    decision.innerHTML = `<p class="decision-msg">${msg}</p><div class="align-row">${btns.join("")}</div>`;
    const dt = decision.querySelector(".d-trim");
    const dp = decision.querySelector(".d-pad");
    if (dt) dt.addEventListener("click", () => { trim.hidden = !trim.hidden; dt.classList.toggle("on", !trim.hidden); });
    if (dp) dp.addEventListener("click", () => { pad.hidden = !pad.hidden; dp.classList.toggle("on", !pad.hidden); });
  }
  renderDecision();

  drawTracks();
  return card;
}

async function applyAlign(path, body, busyMsg) {
  setMsg(3, busyMsg, "spinner");
  try {
    await api(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    setMsg(3, "Saved — applied when you build.", "ok");
    renderAlign();
  } catch (e) {
    setMsg(3, e.message, "error");
  }
}

async function assign(id, key, value) {
  const f = state.files.find((x) => x.id === id);
  const patch = { id };
  patch[key] = value;
  try {
    const r = await api("/api/assign", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    Object.assign(f, r.file);
    renderFiles();
  } catch (e) {
    setMsg(2, e.message, "error");
  }
}

async function removeFile(id) {
  await api(`/api/upload/${id}`, { method: "DELETE" });
  state.files = state.files.filter((x) => x.id !== id);
  renderFiles();
}

$("#next-2").addEventListener("click", async () => {
  if (!state.files.some((f) => f.videoID)) {
    setMsg(2, "Add at least one file with a session ID.", "error");
    return;
  }
  const cameras = collectPerspectives();
  if (cameras.perspectives && !cameras.videoSrcTemplate) {
    setMsg(2, "Angles are named, but nothing says where their video files are. " +
              "Fill in the path template, or clear the angle names.", "error");
    return;
  }
  await api("/api/config", {
    method: "POST", headers: { "Content-Type": "application/json" },
    // Sent even when empty, so clearing the angles clears them in the study too.
    body: JSON.stringify({
      perspectives: cameras.perspectives || null,
      videoPerspectives: cameras.videoPerspectives || null,
      videoSrcTemplate: cameras.videoSrcTemplate || null,
      fallbackVideoSrcTemplate: cameras.fallbackVideoSrcTemplate || null,
    }),
  });
  setMsg(2, "");
  unlockStep(3);
  gotoStep(3);
});
$("#back-2").addEventListener("click", () => gotoStep(1));

// ---- STEP 3: align (nav) ---------------------------------------------------
$("#next-3").addEventListener("click", () => { unlockStep(4); gotoStep(4); });
$("#back-3").addEventListener("click", () => gotoStep(2));

// ---- STEP 4: analyses ------------------------------------------------------
function allDataTypes() {
  const s = new Set();
  state.files.forEach((f) => { if (f.role === "timeseries" && f.dataType) s.add(f.dataType); });
  return Array.from(s);
}

// All unordered pairs of available data types, as {key:"a|b", a, b, label}.
function allPairs() {
  const arr = allDataTypes();
  const out = [];
  for (let i = 0; i < arr.length; i++)
    for (let j = i + 1; j < arr.length; j++)
      out.push({ key: `${arr[i]}|${arr[j]}`, a: arr[i], b: arr[j], label: `${arr[i]} × ${arr[j]}` });
  return out;
}

// ---- the network diagram ---------------------------------------------------
//
// The wizard used to ask for this as a table of dropdowns, and what a row meant
// only became visible after the analyses had run and the dashboard was open. It
// also could not express the thing anyone actually wants to do: put this measure
// on that person's left hand, and draw a line to that one.
//
// So the diagram is the control. Its geometry is lifted from
// packages/dims-tabs/network.js -- the same viewBox, the same body coordinates,
// the same node radius -- so what you arrange here is what the dashboard draws.
const SVG_NS = "http://www.w3.org/2000/svg";
const VIEW_W = 1000, NODE_R = 26;
const SHOULDER_Y = 150, HIP_Y = 330, FOOT_Y = 545;

// Six positions, not the tab's eight tokens: `nose` sits on `head` and `hand`
// on `lefthand`, so two of the names are aliases for one place. The diagram
// writes the unambiguous one and reads either.
const SPOTS = [
  { part: "head", label: "head", dx: 0, y: 85 },
  { part: "righthand", label: "right hand", dx: -100, y: 300 },
  { part: "lefthand", label: "left hand", dx: 100, y: 300 },
  { part: "torso", label: "torso", dx: 0, y: 235 },
  { part: "hip", label: "hip", dx: 0, y: HIP_Y },
  { part: "foot", label: "foot", dx: 0, y: FOOT_Y },
];
const SPOT_ALIASES = { nose: "head", hand: "lefthand" };
const PERSON_COLORS = ["#e84393", "#00b894", "#5b8cff", "#d29922", "#a78bfa"];

function svgEl(name, attrs) {
  const node = document.createElementNS(SVG_NS, name);
  Object.entries(attrs || {}).forEach(([k, v]) => node.setAttribute(k, v));
  return node;
}

const spotOf = (part) => SPOT_ALIASES[part] || part;
const personCx = (index, total) => (VIEW_W * (index + 1)) / (total + 1);

// Where each placed measure sits, so edges and nodes agree on one answer.
function placedPositions() {
  const out = {};
  const total = state.people.length;
  state.people.forEach((person, i) => {
    Object.entries(state.effectors).forEach(([dt, eff]) => {
      if (eff.group !== person.label || !eff.part) return;
      const spot = SPOTS.find((sp) => sp.part === spotOf(eff.part));
      if (spot) out[dt] = { x: personCx(i, total) + spot.dx, y: spot.y, person };
    });
  });
  return out;
}

function unplacedTypes() {
  return allDataTypes().filter((dt) => {
    const eff = state.effectors[dt];
    return !(eff && eff.group && eff.part);
  });
}

// A translucent body under the nodes, so a chart of people looks like one.
// Copied from the tab's appendFigure(); if that geometry moves, this follows.
function appendFigure(svg, color, cx) {
  const g = svgEl("g", {
    opacity: 0.3, fill: color, stroke: color, "stroke-width": 10,
    "stroke-linecap": "round", "stroke-linejoin": "round",
  });
  const shoulderL = cx - 60, shoulderR = cx + 60;
  const hipL = cx - 32, hipR = cx + 32;
  g.appendChild(svgEl("circle", { cx, cy: 85, r: 30, stroke: "none" }));
  g.appendChild(svgEl("path", {
    d: `M ${shoulderL} ${SHOULDER_Y} L ${shoulderR} ${SHOULDER_Y} `
     + `L ${hipR} ${HIP_Y} L ${hipL} ${HIP_Y} Z`, stroke: "none" }));
  [[shoulderL, SHOULDER_Y, cx + 100, 300],
   [shoulderR, SHOULDER_Y, cx - 100, 300],
   [hipL, HIP_Y, cx - 35, FOOT_Y],
   [hipR, HIP_Y, cx + 35, FOOT_Y]].forEach(([x1, y1, x2, y2]) => {
    g.appendChild(svgEl("line", { x1, y1, x2, y2, fill: "none" }));
  });
  svg.appendChild(g);
}

// Figures, then edges, then nodes. One function, because the rename path
// redraws the picture without touching the people strip -- rebuilding that
// steals focus from the input being typed into -- and the two must not drift.
function drawInto(svg) {
  svg.innerHTML = "";
  const total = state.people.length;
  const positions = placedPositions();

  state.people.forEach((person, i) => appendFigure(svg, person.color, personCx(i, total)));

  // Edges under the nodes, dashed: on this diagram a line is a request for an
  // analysis, not a result. The dashboard decides how it is finally drawn.
  Array.from(state.cw).forEach((key) => {
    const [a, b] = key.split("|");
    const pa = positions[a], pb = positions[b];
    if (!pa || !pb) return;
    svg.appendChild(svgEl("line", {
      x1: pa.x, y1: pa.y, x2: pb.x, y2: pb.y, class: "diagram-edge",
      stroke: "#9aa3b2", "stroke-width": 3, "stroke-dasharray": "8 8",
      "data-edge": key,
    }));
  });

  state.people.forEach((person, i) => {
    const cx = personCx(i, total);
    SPOTS.forEach((spot) => {
      const at = { x: cx + spot.dx, y: spot.y };
      const dt = Object.keys(positions).find((k) =>
        positions[k].person === person
        && spotOf(state.effectors[k].part) === spot.part);
      const g = svgEl("g", {
        class: "spot" + (dt ? " filled" : "") + (state.armed === dt ? " armed" : ""),
        "data-spot": spot.part, "data-person": person.id,
      });
      if (dt) g.setAttribute("data-dt", dt);
      g.appendChild(svgEl("circle", {
        cx: at.x, cy: at.y, r: NODE_R,
        fill: dt ? person.color : "transparent",
        stroke: dt ? person.color : "#2b303b",
        "stroke-width": dt ? 3 : 2,
        "stroke-dasharray": dt ? "" : "5 5",
      }));
      const text = svgEl("text", {
        x: at.x, y: at.y + NODE_R + 18, "text-anchor": "middle",
        fill: dt ? "#e6e8ec" : "#9aa3b2", "font-size": 14,
      });
      text.textContent = dt ? (state.effectors[dt].label || dt) : spot.label;
      g.appendChild(text);
      g.appendChild(svgEl("title", {})).textContent = dt
        ? dt + " — click to link, × to remove"
        : "Put a time series on " + person.label + "'s " + spot.label;
      if (dt) {
        const clear = svgEl("g", { class: "spot-clear", "data-clear": dt });
        clear.appendChild(svgEl("circle", {
          cx: at.x + NODE_R - 4, cy: at.y - NODE_R + 4, r: 10,
          fill: "#21252e", stroke: "#2b303b", "stroke-width": 1,
        }));
        const x = svgEl("text", {
          x: at.x + NODE_R - 4, y: at.y - NODE_R + 8,
          "text-anchor": "middle", fill: "#9aa3b2", "font-size": 13,
        });
        x.textContent = "×";
        clear.appendChild(x);
        g.appendChild(clear);
      }
      svg.appendChild(g);
    });
  });
}

function renderDiagram() {
  const svg = $("#network-diagram");
  if (!svg) return;
  renderPeople();
  redrawDiagramOnly();
  renderDiagramHint();
  renderCwSummary();
  renderCost();
}

// Renaming redraws on every keystroke, and rebuilding the people strip steals
// focus from the input being typed into. Only the picture is redrawn.
function redrawDiagramOnly() {
  const svg = $("#network-diagram");
  if (svg) drawInto(svg);
  renderUnplaced();
}

function renderPeople() {
  const host = $("#people");
  if (!host) return;
  host.innerHTML = state.people.map((p) => `
    <span class="person" data-person="${esc(p.id)}">
      <input type="color" data-person-color="${esc(p.id)}" value="${esc(p.color)}" />
      <input type="text" data-person-label="${esc(p.id)}" value="${esc(p.label)}" />
      <button type="button" data-person-remove="${esc(p.id)}"
              title="Remove ${esc(p.label)}">×</button>
    </span>`).join("");
}

function renderUnplaced() {
  const host = $("#unplaced");
  if (!host) return;
  const left = unplacedTypes();
  if (!allDataTypes().length) {
    host.innerHTML = '<span class="hint">No time series yet — add some in step 2.</span>';
  } else if (!left.length) {
    host.innerHTML = '<span class="hint">Every time series is on the diagram.</span>';
  } else {
    host.innerHTML = '<span class="hint">Not placed yet:</span> '
      + left.map((dt) => `<span class="chip disabled">${esc(dt)}</span>`).join(" ");
  }
}

function renderDiagramHint() {
  const host = $("#diagram-hint");
  if (!host) return;
  if (!state.people.length) {
    host.textContent = "Add a person to start. Each one gets a figure — one is "
      + "enough if you are comparing a single body's own effectors.";
  } else if (state.armed) {
    host.textContent = "Linking from " + state.armed + " — click another node to "
      + "ask for the cross-wavelet between them, or click it again to cancel.";
  } else if (state.placedByName) {
    host.textContent = "These were placed from their names — check them, then "
      + "click an empty circle to add one, or two placed ones to link them.";
  } else {
    host.textContent = "Click an empty circle to put a time series there. "
      + "Click two placed ones to draw a line between them.";
  }
}

// The cross-wavelet block no longer has chips of its own: a line on the diagram
// is one cross-wavelet pair, and picking it in two places is how they drift.
function renderCwSummary() {
  const host = $("#cw_summary");
  if (!host) return;
  const n = pairKeysToList(state.cw).length;
  host.textContent = n
    ? n + " pair" + (n === 1 ? "" : "s") + " drawn on the diagram below."
    : "No pairs yet — draw a line between two nodes on the diagram below.";
}

// ---- the diagram's interactions --------------------------------------------

// state.cw keys are order-sensitive: pairKeysToList filters against allPairs(),
// which emits them in allDataTypes() order, so an edge drawn from B to A is
// dropped in silence unless it is normalised here.
function pairKey(a, b) {
  const order = allDataTypes();
  return order.indexOf(a) <= order.indexOf(b) ? a + "|" + b : b + "|" + a;
}

function addPerson(label, color, match) {
  const id = "p" + (state.people.length + 1) + "-" + Math.random().toString(36).slice(2, 7);
  const person = {
    id,
    label: label || "Person " + (state.people.length + 1),
    color: color || PERSON_COLORS[state.people.length % PERSON_COLORS.length],
  };
  if (match) person.match = match;
  state.people.push(person);
  return id;
}

function removePerson(id) {
  const person = state.people.find((p) => p.id === id);
  if (!person) return;
  state.people = state.people.filter((p) => p.id !== id);
  // Their measures come off the diagram rather than moving to somebody else.
  Object.keys(state.effectors).forEach((dt) => {
    if (state.effectors[dt].group === person.label) unplace(dt);
  });
}

function unplace(dt) {
  delete state.effectors[dt];
  if (state.armed === dt) state.armed = null;
  Array.from(state.cw).forEach((key) => {
    if (key.split("|").indexOf(dt) !== -1) state.cw.delete(key);
  });
}

function place(dt, personId, part) {
  const person = state.people.find((p) => p.id === personId);
  if (!person) return;
  // One measure is one node, so placing it somewhere new moves it.
  state.effectors[dt] = { ...(state.effectors[dt] || {}), group: person.label, part };
}

function toggleEdge(a, b) {
  if (a === b) return;
  const key = pairKey(a, b);
  if (state.cw.has(key)) state.cw.delete(key); else state.cw.add(key);
  $("#t_cw").checked = true;      // or include_crosswavelet collapses to []
}

function closeSpotMenu() {
  const menu = $("#spot-menu");
  if (menu) { menu.hidden = true; menu.innerHTML = ""; }
}

function openSpotMenu(personId, part, at) {
  const menu = $("#spot-menu");
  const left = unplacedTypes();
  const person = state.people.find((p) => p.id === personId);
  if (!menu || !person) return;
  const spot = SPOTS.find((sp) => sp.part === part);
  menu.innerHTML = left.length
    ? `<div class="spot-menu-head">On ${esc(person.label)}'s ${esc(spot ? spot.label : part)}</div>`
      + left.map((dt) => `<button type="button" data-pick="${esc(dt)}">${esc(dt)}</button>`).join("")
    : '<div class="spot-menu-head">Every time series is already placed.</div>';
  menu.dataset.person = personId;
  menu.dataset.part = part;
  menu.style.left = at.left + "px";
  menu.style.top = at.top + "px";
  menu.hidden = false;
}

function wireDiagram() {
  const svg = $("#network-diagram");
  if (!svg) return;

  svg.addEventListener("click", (e) => {
    const clear = e.target.closest("[data-clear]");
    if (clear) { unplace(clear.dataset.clear); renderDiagram(); return; }
    const spot = e.target.closest("[data-spot]");
    if (!spot) return;
    const dt = spot.dataset.dt;
    if (!dt) {
      const box = svg.getBoundingClientRect();
      const node = spot.getBoundingClientRect();
      openSpotMenu(spot.dataset.person, spot.dataset.spot, {
        left: node.left - box.left + node.width,
        top: node.top - box.top,
      });
      return;
    }
    closeSpotMenu();
    if (state.armed === dt) state.armed = null;
    else if (state.armed) { toggleEdge(state.armed, dt); state.armed = null; }
    else state.armed = dt;
    renderDiagram();
  });

  $("#spot-menu").addEventListener("click", (e) => {
    const pick = e.target.closest("[data-pick]");
    if (!pick) return;
    const menu = $("#spot-menu");
    place(pick.dataset.pick, menu.dataset.person, menu.dataset.part);
    closeSpotMenu();
    renderDiagram();
  });

  $("#add-person").addEventListener("click", () => { addPerson(); renderDiagram(); });

  $("#people").addEventListener("click", (e) => {
    const rm = e.target.closest("[data-person-remove]");
    if (!rm) return;
    removePerson(rm.dataset.personRemove);
    renderDiagram();
  });

  $("#people").addEventListener("input", (e) => {
    const labelId = e.target.dataset.personLabel;
    const colorId = e.target.dataset.personColor;
    const person = state.people.find((p) => p.id === (labelId || colorId));
    if (!person) return;
    if (labelId) {
      // The effectors reference a person by label, so renaming has to follow.
      const was = person.label;
      person.label = e.target.value;
      Object.values(state.effectors).forEach((eff) => {
        if (eff.group === was) eff.group = person.label;
      });
    } else {
      person.color = e.target.value;
    }
    redrawDiagramOnly();
  });
}

function renderAnalysisTypes() {
  const types = allDataTypes();
  const pairs = allPairs();
  renderCwSummary();

  // RQA: single-type chips (one signal vs itself).
  const mkTypes = (box, setRef, disabled) => {
    box.innerHTML = "";
    types.forEach((t) => {
      const c = document.createElement("span");
      c.className = "chip" + (setRef.has(t) ? " on" : "") + (disabled ? " disabled" : "");
      c.textContent = t;
      c.addEventListener("click", () => {
        if (disabled) return;
        setRef.has(t) ? setRef.delete(t) : setRef.add(t);
        renderAnalysisTypes();
      });
      box.appendChild(c);
    });
    if (!types.length) box.innerHTML = '<span class="hint">No data types yet — add time-series CSVs in step 2.</span>';
  };

  // Cross-wavelet / cross-RQA: one chip per pair; a type can appear in many.
  const mkPairs = (box, setRef, disabled) => {
    box.innerHTML = "";
    pairs.forEach((p) => {
      const c = document.createElement("span");
      c.className = "chip" + (setRef.has(p.key) ? " on" : "") + (disabled ? " disabled" : "");
      c.textContent = p.label;
      c.addEventListener("click", () => {
        if (disabled) return;
        setRef.has(p.key) ? setRef.delete(p.key) : setRef.add(p.key);
        renderAnalysisTypes();
      });
      box.appendChild(c);
    });
    if (pairs.length < 1)
      box.innerHTML = '<span class="hint">Need at least 2 data types to form a pair — add time-series CSVs in step 2.</span>';
  };

  mkTypes($("#rqa_types"), state.rqa, !$("#t_rqa").checked);
  mkPairs($("#crqa_types"), state.crqa, !$("#t_crqa").checked);
  renderCost();
}

// What has been asked for, in the units that decide how long step 6 takes.
// Without this the first sign that a choice was expensive is being forty
// minutes into a run with nothing to look at.
function renderCost() {
  const box = $("#cost");
  if (!box) return;
  const sessions = sessionIDs().length;
  const bits = [];
  if ($("#t_rqa").checked) bits.push(`${state.rqa.size} recurrence`);
  if ($("#t_crqa").checked) bits.push(`${pairKeysToList(state.crqa).length} cross-recurrence`);
  if ($("#t_cw").checked) bits.push(`${pairKeysToList(state.cw).length} cross-wavelet`);
  if (!bits.length || !sessions) {
    box.textContent = sessions
      ? "Nothing switched on yet — the dashboard will show the video, the measurements and any transcript."
      : "";
    box.className = "note";
    return;
  }
  const mc = Number($("#cw_mc").value || 0);
  const cwRuns = $("#t_cw").checked ? pairKeysToList(state.cw).length * sessions : 0;
  const slow = mc > 0 && cwRuns > 0;
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
  box.innerHTML =
    `Across ${plural(sessions, "session", "sessions")}: ` + bits.join(", ") +
    ` — ${plural(sessions * bits.reduce((a, b) => a + parseInt(b, 10), 0),
                 "analysis run", "analysis runs")}. ` +
    (slow
      ? "<strong>" + (cwRuns === 1 ? "That run estimates" : `${cwRuns} of them estimate`) +
        ` a chance level from ${mc} surrogates${cwRuns === 1 ? "" : " each"}</strong> — that is the slow ` +
        "part, minutes per run on a long recording, and the reason step 6 can " +
        "take hours. Lower the count, or set it to 0 if you are not using the " +
        "network."
      : "None of these estimate a chance level, so step 6 is seconds to minutes.");
  box.className = "note" + (slow ? " warn" : "");
}
["cw_mc"].forEach((id) => $("#" + id).addEventListener("input", renderCost));

// Turn a Set of "a|b" pair keys into a list of [a, b] pairs (only those whose
// data types still exist).
function pairKeysToList(setRef) {
  const valid = new Set(allPairs().map((p) => p.key));
  return Array.from(setRef)
    .filter((k) => valid.has(k))
    .map((k) => k.split("|"));
}

// Enabling an analysis selects everything by default (the user then deselects);
// disabling clears the selection. RQA selects all types; cw/cRQA select all pairs.
function syncAnalysisDefaults() {
  const types = allDataTypes();
  const pairKeys = allPairs().map((p) => p.key);
  if ($("#t_rqa").checked) { if (state.rqa.size === 0) types.forEach((t) => state.rqa.add(t)); }
  else state.rqa.clear();
  if ($("#t_cw").checked) { if (state.cw.size === 0) pairKeys.forEach((k) => state.cw.add(k)); }
  else state.cw.clear();
  if ($("#t_crqa").checked) { if (state.crqa.size === 0) pairKeys.forEach((k) => state.crqa.add(k)); }
  else state.crqa.clear();
}
["t_rqa", "t_cw", "t_crqa", "t_elan", "t_network"].forEach((id) =>
  $("#" + id).addEventListener("change", () => {
    syncAnalysisDefaults();
    renderAnalysisTypes();
    renderDiagram();
    reflectNetwork();
  })
);

// The diagram's listeners are delegated and bound once; the picture itself is
// rebuilt from state on every change, the way every other view here is.
wireDiagram();

// The network draws its edges from cross-wavelet output and reads the chance
// level, so switching it on has two consequences the wizard states rather than
// applying silently.
function reflectNetwork() {
  const on = $("#t_network").checked;
  const note = $("#network-note");
  note.hidden = !on;
  if (!on) return;
  if (!$("#t_cw").checked) {
    $("#t_cw").checked = true;
    syncAnalysisDefaults();
    renderAnalysisTypes();
    note.innerHTML = "<strong>Cross-wavelet was switched on too</strong> \u2014 " +
      "the network's edges are its coherence, so there is nothing to draw " +
      "without it. The chance level is on as well (100 surrogates): an " +
      "unrelated pair scores about 0.25, not 0, so without one no edge can be " +
      "told from coincidence.";
  }
  if (!$("#cw_mc").value || Number($("#cw_mc").value) === 0) {
    $("#cw_mc").value = 100;
    $("#cw_mc").dataset.auto = "1";
  }
}

// Switching the network off must not leave its surrogate count behind: that is
// the slow part of the whole pipeline, and paying for it with nothing reading it
// is the exact state the analysis default exists to avoid.
$("#t_network").addEventListener("change", () => {
  if (!$("#t_network").checked && $("#cw_mc").dataset.auto === "1") {
    $("#cw_mc").value = "";
    delete $("#cw_mc").dataset.auto;
  }
  renderCost();
});
$("#cw_mc").addEventListener("input", () => { delete $("#cw_mc").dataset.auto; });

// A number field left blank means "keep the default", which is different from
// zero and must not be written as one.
function numOrNull(id) {
  const raw = $("#" + id).value.trim();
  if (raw === "") return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

function bandOrNull(id) {
  const raw = $("#" + id).value.trim();
  if (!raw) return null;
  const parts = raw.split(",").map((x) => Number(x.trim()));
  if (parts.length !== 2 || parts.some((x) => !Number.isFinite(x))) return "bad";
  return parts.sort((a, b) => a - b);
}

function collectTuning() {
  const block = {};
  const put = (step, key, value) => {
    if (value === null || value === undefined) return;
    (block[step] = block[step] || {})[key] = value;
  };
  put("rqa", "window", numOrNull("rqa_window"));
  put("rqa", "step", numOrNull("rqa_step"));
  put("rqa", "targetRecurrence", numOrNull("rqa_target"));
  put("crqa", "window", numOrNull("crqa_window"));
  put("crqa", "step", numOrNull("crqa_step"));
  put("crqa", "targetRecurrence", numOrNull("crqa_target"));
  put("crosswavelet", "mcCount", numOrNull("cw_mc"));
  put("crosswavelet", "maxTimePoints", numOrNull("cw_maxt"));
  put("crosswavelet", "maxFreqPoints", numOrNull("cw_maxf"));
  const band = bandOrNull("cw_band");
  if (band && band !== "bad") put("crosswavelet", "scaleAvgBand", band);
  if (!$("#cw_full").checked) put("crosswavelet", "saveFullResolution", false);
  return Object.keys(block).length ? block : null;
}

// The diagram is the source. A person becomes a group, a placed measure becomes
// an effector, and the layout is `figure` because a body diagram that configured
// a column chart would be a lie.
function collectNetwork() {
  if (!$("#t_network").checked) return false;
  const groups = state.people.map((p) => {
    const g = { label: p.label };
    if (p.color) g.color = p.color;
    // Only ever carried in from a config that already had one.
    if (p.match) g.match = p.match;
    return g;
  });

  const effectors = allDataTypes().map((dt) => {
    const cur = state.effectors[dt] || {};
    const extra = state.effectorExtras[dt] || {};
    const said = cur.group || cur.label || cur.part
      || extra.x !== undefined || extra.y !== undefined;
    if (!said) return null;
    const out = { series: dt };
    if (cur.group) out.group = cur.group;
    if (cur.label) out.label = cur.label;
    if (cur.part) out.part = cur.part;
    // Carried through, not rebuilt: the diagram has no coordinate handles, and
    // dropping what it cannot show is the bug this function already had once.
    if (extra.x !== undefined) out.x = extra.x;
    if (extra.y !== undefined) out.y = extra.y;
    return out;
  }).filter(Boolean);

  const band = bandOrNull("network_band");
  if (!groups.length && !effectors.length && (!band || band === "bad")) return true;
  const out = {};
  if (groups.length) out.groups = groups;
  if (effectors.length) out.effectors = effectors;
  if (band && band !== "bad") out.band = band;
  if (effectors.length) out.layout = "figure";
  return out;
}

$("#next-4").addEventListener("click", async () => {
  state.elan = $("#t_elan").checked;
  const rqa = $("#t_rqa").checked ? Array.from(state.rqa) : [];
  const cw = $("#t_cw").checked ? pairKeysToList(state.cw) : [];
  const crqa = $("#t_crqa").checked ? pairKeysToList(state.crqa) : [];
  if ($("#t_cw").checked && cw.length < 1) {
    setMsg(4, "Cross-wavelet compares pairs — select at least one pair (or turn it off).", "error");
    return;
  }
  if ($("#t_crqa").checked && crqa.length < 1) {
    setMsg(4, "Cross-RQA compares pairs — select at least one pair (or turn it off).", "error");
    return;
  }
  if ($("#t_network").checked && cw.length < 1) {
    setMsg(4, "The network draws cross-wavelet coherence as its edges, so it " +
              "needs at least one cross-wavelet pair.", "error");
    return;
  }
  for (const [id, label] of [["cw_band", "the cross-wavelet averaging band"],
                             ["network_band", "the network's period band"]]) {
    if (bandOrNull(id) === "bad") {
      setMsg(4, `Give ${label} as two numbers, shortest first — for example 0.5, 8.`, "error");
      return;
    }
  }
  await api("/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      include_RQA: rqa,
      include_crosswavelet: cw,
      include_cRQA: crqa,
      include_elan: state.elan,
      include_network: collectNetwork(),
      analysis: collectTuning(),
    }),
  });
  setMsg(4, "");
  unlockStep(5);
  gotoStep(5);
});
$("#back-4").addEventListener("click", () => gotoStep(3));

// ---- STEP 4: build ---------------------------------------------------------
async function refreshValidation() {
  const v = await api("/api/validate", { method: "POST" });
  $("#config-preview").textContent = JSON.stringify(v.config, null, 2);
  const box = $("#validation");
  const items = [...v.config_issues];
  Object.values(v.file_issues).forEach((lst) => items.push(...lst));
  box.innerHTML = items.length
    ? items.map((i) => `<div class="issue ${i.level}">${i.level === "error" ? "✗" : "⚠"} ${i.message}</div>`).join("")
    : '<div class="issue" style="color:var(--ok)">✓ Everything looks good.</div>';
  $("#btn-build").disabled = v.blocking;
  if (v.blocking) setMsg(5, "Fix the errors above before building.", "error");
  else setMsg(5, "");
}

// Per-session video vs data length mismatches (after any trim/pad specs).
async function alignmentMismatches() {
  try {
    const data = await api("/api/sessions");
    const out = [];
    data.sessions.forEach((s) => {
      if (!s.video || !s.series.length) return;
      const vlen = s.video.trim ? s.video.trim.end - s.video.trim.start : s.video.duration;
      if (vlen == null) return;  // duration unknown (no ffmpeg) — can't compare
      const dlen = Math.max(...s.series.map(
        (x) => (x.bounds ? x.bounds.max : 0) + (x.pad ? x.pad.start + x.pad.end : 0)));
      if (Math.abs(vlen - dlen) >= 0.1)
        out.push({ videoID: s.videoID, vlen: vlen.toFixed(2), dlen: dlen.toFixed(2) });
    });
    return out;
  } catch (e) { return []; }
}

$("#btn-build").addEventListener("click", async () => {
  // Warn (non-blocking) when a session's video and time-series lengths differ —
  // the dashboard maps data Time onto the video clock, so a mismatch leaves
  // dead space or cuts the signal off. The user can go back to step 3 to align.
  const mism = await alignmentMismatches();
  if (mism.length) {
    const lines = mism.map((m) => `  • ${m.videoID}: video ${m.vlen}s vs data ${m.dlen}s`).join("\n");
    const proceed = confirm(
      "Video and time-series lengths don't match for:\n\n" + lines +
      "\n\nThe dashboard may not display ideally when they differ (the video and " +
      "signals won't line up). You can fix this in step 3 (Align).\n\nBuild anyway?");
    if (!proceed) { gotoStep(3); return; }
  }
  setMsg(5, "Building…", "spinner");
  try {
    const r = await api("/api/build", { method: "POST" });
    setMsg(5, `Built! ${r.placed.length} file(s) placed in ${r.output_dir}`, "ok");
    unlockStep(6);
    gotoStep(6);
  } catch (e) {
    setMsg(5, e.message, "error");
    refreshValidation();
  }
});
$("#back-5").addEventListener("click", () => gotoStep(4));

// ---- STEP 6: precompute ----------------------------------------------------
$("#btn-precompute").addEventListener("click", async () => {
  const log = $("#precompute-log");
  log.textContent = "";
  $("#btn-precompute").disabled = true;
  setMsg(6, "Running… this may take a few minutes.", "spinner");
  try {
    const res = await fetch("/api/precompute", { method: "POST" });
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let failed = false;
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      const chunk = dec.decode(value, { stream: true });
      if (chunk.includes("__ERROR__") || chunk.includes("__FAILED__:") ||
          /__EXIT__:[1-9]/.test(chunk)) failed = true;
      log.textContent += chunk.replace(/__EXIT__:\d+\n/g, "")
                            .replace(/__FAILED__:\S+\n/g, "");
      log.scrollTop = log.scrollHeight;
    }
    setMsg(6, failed ? "Precompute finished with errors — check the log." : "Precompute complete.",
      failed ? "error" : "ok");
    // Only open the preview/deploy step if the analyses actually ran. A
    // dashboard built on a failed precompute looks complete and is not.
    if (!failed) { unlockStep(7); gotoStep(7); }
  } catch (e) {
    setMsg(6, e.message, "error");
  } finally {
    $("#btn-precompute").disabled = false;
  }
});
$("#skip-6").addEventListener("click", () => { unlockStep(7); gotoStep(7); });

// ---- STEP 7: preview / deploy ---------------------------------------------
$("#btn-preview").addEventListener("click", async () => {
  setMsg(7, "Starting preview server…", "spinner");
  try {
    const r = await api("/api/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ port: 8000 }),
    });
    setMsg(7, "Preview running at " + r.url, "ok");
    window.open(r.url, "_blank");
  } catch (e) {
    setMsg(7, e.message, "error");
  }
});

// The hooks are the one thing nothing can do for the user, and step 1 has long
// scrolled away by the time they are about to put the study somewhere.
function renderPrivacyReminder() {
  const box = $("#privacy-note-2");
  if (!box) return;
  if (state.visibility !== "private") { box.hidden = true; return; }
  box.hidden = false;
  box.innerHTML =
    "<strong>This study is private.</strong> Before you put it in git, in this " +
    "folder and in every clone:" +
    `<pre class="codebox">${state.hooks || "git config core.hooksPath .githooks"}</pre>` +
    "<small>That is what makes the guards run. Until then a commit can include " +
    "a recording, and removing it afterwards means rewriting history.</small>";
}

function renderDeploy() {
  const dir = state.outputDir || "<your study folder>";
  // A private study must not be handed `git add -A`. That is the one command
  // the guards exist to intercept, and they only run once the user has pointed
  // git at them -- which is a thing a person does, in every clone, and might
  // not have done yet. Telling them to run it anyway would be the wizard
  // walking its own user into the failure it spent step 1 warning about.
  $("#deploy-cmds").textContent = state.visibility === "private"
? `# This study is private: its recordings must not enter git history.
cd ${dir}
git init
git config core.hooksPath .githooks     # do this BEFORE the first commit
git add -A                              # the hook refuses anything restricted
git commit -m "DIMS dashboard"

# The dashboard code and config are committed; assets/ stays out, and
# data.local.json points the study at wherever the recordings really live.
# To show it to someone, serve it locally:
python serve.py                         # http://localhost:8000

# Publishing it means publishing the recordings. If that is what you want,
# say so deliberately: set "visibility": "public" in dims-case.json and list
# what may be published under "publishable".`
: `# This study is public: assets are committed with it.
cd ${dir}
git init && git add -A && git commit -m "DIMS dashboard"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
# then enable Pages (branch: main, folder: /root) in the repo settings.

# Netlify:  netlify deploy --dir . --prod
# Vercel:   vercel --prod
# Any host works as long as it supports HTTP Range requests (video seeking).`;
}

// ---- nav clicks ------------------------------------------------------------
$$(".step").forEach((b) =>
  b.addEventListener("click", () => gotoStep(+b.dataset.step))
);

gotoStep(1);
