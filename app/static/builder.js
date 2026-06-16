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
  if (n === 3) renderAnalysisTypes();
  if (n === 4) refreshValidation();
  if (n === 6) renderDeploy();
}

function unlockStep(n) {
  state.maxStep = Math.max(state.maxStep, n);
}

// ---- STEP 1: project -------------------------------------------------------
$$('input[name="src"]').forEach((r) =>
  r.addEventListener("change", () => {
    const local = $('input[name="src"]:checked').value === "local";
    $("#src_local").disabled = !local;
    $("#src_url").disabled = local;
  })
);

$("#btn-create").addEventListener("click", async () => {
  const useLocal = $('input[name="src"]:checked').value === "local";
  const source = useLocal ? $("#src_local").value.trim() : $("#src_url").value.trim();
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

// ---- STEP 3: analyses ------------------------------------------------------
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

["t_rqa", "t_cw", "t_elan"].forEach((id) =>
  $("#" + id).addEventListener("change", renderAnalysisTypes)
);

$("#next-3").addEventListener("click", async () => {
  state.elan = $("#t_elan").checked;
  const rqa = $("#t_rqa").checked ? Array.from(state.rqa) : [];
  const cw = $("#t_cw").checked ? Array.from(state.cw) : [];
  if (cw.length === 1) {
    setMsg(3, "Cross-wavelet compares pairs — pick at least 2 data types (or turn it off).", "error");
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
  setMsg(3, "");
  unlockStep(4);
  gotoStep(4);
});
$("#back-3").addEventListener("click", () => gotoStep(2));

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
  if (v.blocking) setMsg(4, "Fix the errors above before building.", "error");
  else setMsg(4, "");
}

$("#btn-build").addEventListener("click", async () => {
  setMsg(4, "Building…", "spinner");
  try {
    const r = await api("/api/build", { method: "POST" });
    setMsg(4, `Built! ${r.placed.length} file(s) placed in ${r.output_dir}`, "ok");
    unlockStep(5);
    gotoStep(5);
  } catch (e) {
    setMsg(4, e.message, "error");
    refreshValidation();
  }
});
$("#back-4").addEventListener("click", () => gotoStep(3));

// ---- STEP 5: precompute ----------------------------------------------------
$("#btn-precompute").addEventListener("click", async () => {
  const log = $("#precompute-log");
  log.textContent = "";
  $("#btn-precompute").disabled = true;
  setMsg(5, "Running… this may take a few minutes.", "spinner");
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
    setMsg(5, failed ? "Precompute finished with errors — check the log." : "Precompute complete.",
      failed ? "error" : "ok");
    unlockStep(6);
    if (!failed) gotoStep(6);
  } catch (e) {
    setMsg(5, e.message, "error");
  } finally {
    $("#btn-precompute").disabled = false;
  }
});
$("#skip-5").addEventListener("click", () => { unlockStep(6); gotoStep(6); });

// ---- STEP 6: preview / deploy ---------------------------------------------
$("#btn-preview").addEventListener("click", async () => {
  setMsg(6, "Starting preview server…", "spinner");
  try {
    const r = await api("/api/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ port: 8000 }),
    });
    setMsg(6, "Preview running at " + r.url, "ok");
    window.open(r.url, "_blank");
  } catch (e) {
    setMsg(6, e.message, "error");
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
