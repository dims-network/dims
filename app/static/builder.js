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
  rqa: new Set(),
  cw: new Set(),
  elan: false,
};

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
  if (n === 4) renderAnalysisTypes();
  if (n === 5) refreshValidation();
  if (n === 7) renderDeploy();
}

function unlockStep(n) {
  state.maxStep = Math.max(state.maxStep, n);
}

// ---- STEP 1: project -------------------------------------------------------
function srcChoice() {
  return $('input[name="src"]:checked').value; // "bundled" | "url" | "local"
}
$$('input[name="src"]').forEach((r) =>
  r.addEventListener("change", () => {
    const c = srcChoice();
    $("#src_url").disabled = c !== "url";
    $("#src_local").disabled = c !== "local";
  })
);

$("#btn-create").addEventListener("click", async () => {
  const c = srcChoice();
  // "bundled" → empty string lets the server use the built-in template.
  const source = c === "url" ? $("#src_url").value.trim()
               : c === "local" ? $("#src_local").value.trim()
               : "";
  const payload = {
    output_dir: $("#output_dir").value.trim(),
    template_source: source,
    config: {
      title: $("#title").value,
      subtitle: $("#subtitle").value,
      authors: $("#authors").value,
      contacts: $("#contacts").value,
      defaultWindowSize: Number($("#defaultWindowSize").value) || 5,
    },
  };
  setMsg(1, "Acquiring template…", "spinner");
  try {
    const r = await api("/api/project", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setMsg(1, "Project ready at " + r.output_dir, "ok");
    unlockStep(2);
    gotoStep(2);
  } catch (e) {
    setMsg(1, e.message, "error");
  }
});

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

async function uploadFiles(fileList) {
  for (const f of fileList) {
    const fd = new FormData();
    fd.append("file", f);
    setMsg(2, `Uploading ${f.name}…`, "spinner");
    try {
      const r = await api("/api/upload", { method: "POST", body: fd });
      state.files.push(r.file);
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
    row.className = "filerow";
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
  const tIdx = header.indexOf("Time");
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

$("#next-2").addEventListener("click", () => {
  if (!state.files.some((f) => f.videoID)) {
    setMsg(2, "Add at least one file with a session ID.", "error");
    return;
  }
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

function renderAnalysisTypes() {
  const types = allDataTypes();
  const rqaBox = $("#rqa_types");
  const cwBox = $("#cw_types");
  const enabled = (box) => box.closest(".analysis").querySelector('input[type=checkbox]').checked;
  const mk = (box, setRef, disabled) => {
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
  mk(rqaBox, state.rqa, !$("#t_rqa").checked);
  mk(cwBox, state.cw, !$("#t_cw").checked);
}

// Enabling an analysis selects all available data types by default (the user
// can then deselect chips); disabling clears the selection. This way ticking
// RQA / cross-wavelet always lands those keys in config.json.
function syncAnalysisDefaults() {
  const types = allDataTypes();
  if ($("#t_rqa").checked) { if (state.rqa.size === 0) types.forEach((t) => state.rqa.add(t)); }
  else state.rqa.clear();
  if ($("#t_cw").checked) { if (state.cw.size === 0) types.forEach((t) => state.cw.add(t)); }
  else state.cw.clear();
}
["t_rqa", "t_cw", "t_elan"].forEach((id) =>
  $("#" + id).addEventListener("change", () => { syncAnalysisDefaults(); renderAnalysisTypes(); })
);

$("#next-4").addEventListener("click", async () => {
  state.elan = $("#t_elan").checked;
  const rqa = $("#t_rqa").checked ? Array.from(state.rqa) : [];
  const cw = $("#t_cw").checked ? Array.from(state.cw) : [];
  if (cw.length === 1) {
    setMsg(4, "Cross-wavelet compares pairs — pick at least 2 data types (or turn it off).", "error");
    return;
  }
  await api("/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      include_RQA: rqa,
      include_crosswavelet: cw,
      include_elan: state.elan,
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
      if (chunk.includes("__ERROR__") || /__EXIT__:[1-9]/.test(chunk)) failed = true;
      log.textContent += chunk.replace(/__EXIT__:\d+\n/g, "");
      log.scrollTop = log.scrollHeight;
    }
    setMsg(6, failed ? "Precompute finished with errors — check the log." : "Precompute complete.",
      failed ? "error" : "ok");
    unlockStep(7);
    if (!failed) gotoStep(7);
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

function renderDeploy() {
  $("#deploy-cmds").textContent =
`# Your finished dashboard lives in your output folder.
# Deploy to GitHub Pages:
cd <your-output-folder>
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
