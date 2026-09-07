// A figure drawn while its pane was hidden has no width to measure, so Plotly
// keeps a stale size and does not notice when the pane reappears. The symptom
// is a plot that comes back the wrong size and stays wrong until something
// forces a relayout -- which is why dragging the time slider appeared to fix
// it. These tests pin the redraw to the tab switch, where it belongs.
const test = require('node:test');
const assert = require('node:assert');
const { makeEnv } = require('./harness.js');

const QUIET = ['log', 'warn', 'error', 'info', 'debug'];

async function boot(config, files = {}) {
  const saved = {};
  for (const k of QUIET) { saved[k] = console[k]; console[k] = () => {}; }
  try {
    const env = makeEnv({
      config, files,
      scripts: [
        'packages/dims-core/video-component.js',
        'packages/dims-core/dims-core.js',
        'packages/dims-tabs/timeseries.js',
        'packages/dims-tabs/rqa.js',
        'packages/dims-tabs/crosswavelet.js',
        'packages/dims-tabs/crqa.js',
        'packages/dims-tabs/elan.js',
      ],
    });
    const w = env.window;
    for (const k of QUIET) if (w.console) w.console[k] = () => {};
    for (let i = 0; i < 200 && !(w.dimsApp && w.dimsApp.config); i++) {
      await new Promise(r => setTimeout(r, 5));
    }
    await new Promise(r => setTimeout(r, 20));
    return w;
  } finally {
    for (const k of QUIET) console[k] = saved[k];
  }
}

const CONFIG = {
  videoIDs: ['s1'],
  dataTypes: { s1: ['a', 'b'] },
  defaultWindowSize: 5,
  include_RQA: ['a'],
  include_crosswavelet: [['a', 'b']],
};

// A drawn figure, the way Plotly leaves one behind.
function fakeFigure(w, paneId, id) {
  const pane = w.document.getElementById(paneId);
  if (!pane) return null;
  const el = w.document.createElement('div');
  el.id = id;
  el.className = 'js-plotly-plot';
  el._fullLayout = { width: 300, height: 200 };
  pane.appendChild(el);
  return el;
}

test('switching to a tab re-measures the figures in it', async () => {
  const w = await boot(CONFIG);
  const ids = [...w.document.querySelectorAll('.tab-button')].map(b => b.dataset.tab);
  assert.ok(ids.length >= 2, `need two tabs to switch between, got ${ids}`);

  const target = ids.find(id => id !== w.dimsApp.currentTab);
  const paneId = w.dimsApp.paneIdFor(w.dimsApp.tabs.find(t => t.id === target));
  assert.ok(fakeFigure(w, paneId, 'figureInHiddenPane'), `no pane ${paneId}`);

  w.__resized.length = 0;
  w.dimsApp.switchTab(target);
  await new Promise(r => setTimeout(r, 30));

  assert.ok(w.__resized.includes('figureInHiddenPane'),
    `the newly shown pane's figure was never resized (resized: ${w.__resized})`);
});

test('a figure that never finished drawing is skipped, not thrown over', async () => {
  const w = await boot(CONFIG);
  const ids = [...w.document.querySelectorAll('.tab-button')].map(b => b.dataset.tab);
  const target = ids.find(id => id !== w.dimsApp.currentTab);
  const paneId = w.dimsApp.paneIdFor(w.dimsApp.tabs.find(t => t.id === target));

  const half = fakeFigure(w, paneId, 'neverDrawn');
  delete half._fullLayout;                       // marked, but never laid out
  fakeFigure(w, paneId, 'properlyDrawn');

  w.__resized.length = 0;
  assert.doesNotThrow(() => w.dimsApp.switchTab(target));
  await new Promise(r => setTimeout(r, 30));

  assert.ok(w.__resized.includes('properlyDrawn'), 'the drawn figure was skipped');
  assert.ok(!w.__resized.includes('neverDrawn'), 'resized a figure with no layout');
});

test('a settled window resize re-measures the visible tab only', async () => {
  const w = await boot(CONFIG);
  const ids = [...w.document.querySelectorAll('.tab-button')].map(b => b.dataset.tab);
  const shown = w.dimsApp.currentTab || ids[0];
  w.dimsApp.switchTab(shown);
  await new Promise(r => setTimeout(r, 20));

  const shownPane = w.dimsApp.paneIdFor(w.dimsApp.tabs.find(t => t.id === shown));
  const other = ids.find(id => id !== shown);
  const otherPane = w.dimsApp.paneIdFor(w.dimsApp.tabs.find(t => t.id === other));
  fakeFigure(w, shownPane, 'visibleFigure');
  fakeFigure(w, otherPane, 'hiddenFigure');

  w.__resized.length = 0;
  w.dispatchEvent(new w.Event('resize'));
  await new Promise(r => setTimeout(r, 250));    // past the 150 ms debounce

  assert.ok(w.__resized.includes('visibleFigure'), 'the visible figure was not resized');
  assert.ok(!w.__resized.includes('hiddenFigure'),
    'resized a hidden pane, which cannot be measured and wastes the relayout');
});
