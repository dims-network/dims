// Headless harness for the dashboard host.
//
// The dashboard has no build step and no module system by design, so its
// scripts are loaded in document order exactly as index.html does it. This
// stubs the four CDN libraries and gives the tests a real DOM to assert on.
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.resolve(__dirname, '..', '..', '..');

// The markup every tab depends on, lifted from the scaffold's index.html.
const BODY = `
  <div class="controls">
    <select id="videoSelect"></select>
    <input id="windowSize" type="number" value="5">
    <select id="themeSelect"></select>
    <span id="status"></span>
  </div>
  <h1 id="title"></h1><h3 id="subtitle"></h3>
  <div id="authors"></div><div id="contacts"></div>
  <div class="main-content">
    <div class="chart-section">
      <div class="slider-container"><div id="timeSlider"></div></div>
      <div id="plotContainer"></div>
    </div>
    <div class="video-section">
      <div id="fullVideoContainer"></div>
      <div id="segmentVideoContainer"></div>
      <div id="transcriptDisplay"></div>
    </div>
  </div>`;

function makeEnv({ config, files = {}, scripts }) {
  const dom = new JSDOM(`<!doctype html><html><head></head><body>${BODY}</body></html>`, {
    url: 'http://localhost/', runScripts: 'outside-only', pretendToBeVisual: true,
  });
  const w = dom.window;

  // Stub the CDN globals. Plotly calls are recorded so tests can assert what
  // was drawn without a renderer.
  const plotted = [];
  w.Plotly = {
    newPlot: (el, data, layout) => { plotted.push({ el: el && el.id, n: (data || []).length }); return Promise.resolve(); },
    react: () => Promise.resolve(), purge: () => {}, relayout: () => Promise.resolve(),
    Plots: { resize: () => {} },
  };
  w.React = { createElement: (...a) => ({ __el: a }), Fragment: 'F' };
  w.ReactDOM = { render: () => {}, createRoot: () => ({ render: () => {} }) };
  w.Papa = { parse: (t, o) => { const r = { data: [], errors: [], meta: {} }; o && o.complete && o.complete(r); return r; } };
  w.TimeRangeVideo = function () { return null; };
  w.__plotted = plotted;

  // fetch backed by an in-memory file map, so a test declares exactly what
  // assets exist — which is how tab gating gets exercised honestly.
  const store = Object.assign({ 'config.json': JSON.stringify(config) }, files);
  w.fetch = (url) => {
    const key = String(url).replace(/^\.\//, '').split('?')[0];
    if (!(key in store)) return Promise.resolve({ ok: false, status: 404, statusText: 'Not Found' });
    const body = store[key];
    return Promise.resolve({
      ok: true, status: 200,
      json: () => Promise.resolve(JSON.parse(body)),
      text: () => Promise.resolve(body),
    });
  };
  w.requestAnimationFrame = (cb) => setTimeout(cb, 0);
  w.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });

  for (const rel of scripts) {
    const code = fs.readFileSync(path.join(ROOT, rel), 'utf8');
    w.eval(code);
  }
  return { dom, window: w };
}

module.exports = { makeEnv, ROOT };
