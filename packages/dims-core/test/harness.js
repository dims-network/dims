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
  // Real Plotly attaches an .on() to the plot element; the host uses it to catch
  // clicks on a chart. Without it the load path throws and every later
  // assertion is really testing the error branch.
  // Real Plotly marks the graph div with .js-plotly-plot and hangs _fullLayout
  // on it once drawn. Anything that looks for drawn figures -- the resize pass
  // on tab switch, for one -- finds nothing without them, so the stub sets both
  // or the test passes while the product is broken.
  const resized = [];
  const attach = (el) => {
    if (el && typeof el.on !== 'function') {
      el._handlers = {};
      el.on = (ev, fn) => { (el._handlers[ev] = el._handlers[ev] || []).push(fn); };
      el.emit = (ev, payload) => (el._handlers[ev] || []).forEach(fn => fn(payload));
    }
    if (el && el.classList) {
      el.classList.add('js-plotly-plot');
      el._fullLayout = el._fullLayout || { width: 0, height: 0 };
    }
    return el;
  };
  w.Plotly = {
    newPlot: (el, data, layout) => {
      attach(typeof el === 'string' ? w.document.getElementById(el) : el);
      // The layout is kept, not only the trace count: a caption is something a
      // reader acts on, so a test that cannot see it cannot check it. The
      // coherence chance level is drawn as one, and its absence is a sentence.
      plotted.push({ el: el && (el.id || el), n: (data || []).length,
                     data: data || [], layout: layout || {} });
      return Promise.resolve();
    },
    react: (el) => { attach(typeof el === 'string' ? w.document.getElementById(el) : el); return Promise.resolve(); },
    purge: () => {}, relayout: () => Promise.resolve(),
    Plots: { resize: (el) => { resized.push(el && el.id); } },
  };
  w.__resized = resized;
  w.__attachPlotly = attach;
  w.React = { createElement: (...a) => ({ __el: a }), Fragment: 'F' };
  w.ReactDOM = { render: () => {}, createRoot: () => ({ render: () => {} }) };
  // A real (small) CSV parser, not a stub that always returns nothing. With an
  // empty result the host takes its "no valid data" branch, so any test about
  // what happens once data is loaded silently exercises nothing.
  w.Papa = {
    parse: (text, opts) => {
      const lines = String(text).trim().split(/\r?\n/).filter(Boolean);
      const header = (lines.shift() || '').split(',').map(h => h.trim());
      const data = lines.map(line => {
        const cells = line.split(',');
        const row = {};
        header.forEach((h, i) => {
          const v = (cells[i] ?? '').trim();
          row[h] = opts && opts.dynamicTyping && v !== '' && !isNaN(v) ? Number(v) : v;
        });
        return row;
      });
      const result = { data, errors: [], meta: { fields: header } };
      if (opts && opts.complete) opts.complete(result);
      return result;
    },
  };
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
