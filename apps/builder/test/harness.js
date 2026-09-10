// Headless harness for the wizard's front end.
//
// `builder.js` had no test of any kind, and the shape of what went wrong says
// why it needed one: `collectNetwork()` rebuilt the network config from the two
// controls that existed, so reopening a study and clicking Next silently
// deleted `layout` -- a key nothing in the wizard could show and nothing in the
// wizard would put back. A round trip is the one property that catches that
// whole class, and it needs a DOM.
//
// Like the dashboard, the wizard has no build step and no module system: the
// page is index.html plus one script. So this loads exactly that, with `fetch`
// stubbed, and hands the tests the window.
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const STATIC = path.resolve(__dirname, '..', 'dims_builder', 'static');

// The wizard talks to the server on load. Every test here is about what the
// page does with a config, not about the API, so the routes it touches during
// boot return the empty shapes their handlers would.
const DEFAULT_ROUTES = {
  '/api/project': { project: null },
  '/api/files': { files: [] },
  '/api/samples': { files: [] },
  '/api/config': { config: {} },
};

function boot({ routes = {}, quiet = true } = {}) {
  const html = fs.readFileSync(path.join(STATIC, 'index.html'), 'utf8');
  const dom = new JSDOM(html, {
    url: 'http://localhost/', runScripts: 'outside-only', pretendToBeVisual: true,
  });
  const w = dom.window;

  const answers = { ...DEFAULT_ROUTES, ...routes };
  const calls = [];
  w.fetch = (url, opts = {}) => {
    calls.push({ url, opts });
    const key = Object.keys(answers).find((k) => String(url).startsWith(k));
    return Promise.resolve({
      ok: true, status: 200,
      // `api()` decides how to read a response from its content type, so the
      // stub has to carry one or every call through it throws.
      headers: { get: (h) => (String(h).toLowerCase() === 'content-type'
        ? 'application/json' : null) },
      json: () => Promise.resolve(key ? answers[key] : {}),
      text: () => Promise.resolve(''),
    });
  };
  w.alert = () => {};
  w.confirm = () => true;
  w.scrollTo = () => {};
  if (quiet) {
    for (const k of ['log', 'warn', 'error', 'info', 'debug']) w.console[k] = () => {};
  }

  // builder.js keeps its state and helpers in the script's own scope -- there
  // is no module system and nothing needs to be global in a browser. So the
  // test seam is one appended line rather than an export in the shipped file:
  // the page stays exactly what it is, and the suite gets a handle on it.
  // The shared figure geometry, which the page gets from the server at
  // /vendor/figure-geometry.js. Evaluated first, as the page loads it first.
  const geometry = path.resolve(
    __dirname, '..', '..', '..', 'packages', 'dims-tabs', 'figure-geometry.js');
  w.eval(fs.readFileSync(geometry, 'utf8'));

  const src = fs.readFileSync(path.join(STATIC, 'builder.js'), 'utf8');
  w.eval(src + `
    ;window.__page = {
      get state() { return state; },
      collectNetwork, applyOpenedConfig, renderDiagram, redrawDiagramOnly,
      addPerson, removePerson, place, unplace, toggleEdge, pairKey,
      placedPositions, unplacedTypes, wireDiagram, pairKeysToList,
      renderAlign, renderAnalysisTypes, syncAnalysisDefaults, allPairs,
      cancelLink, closeSpotMenu,
    };`);
  return { window: w, page: w.__page, calls };
}

module.exports = { boot };
