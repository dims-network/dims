// Characterisation tests for tab construction and switching.
//
// Written against the pre-refactor host so they pin the behaviour that must
// survive the move to self-registering tab modules. They assert what a user
// sees — which tabs exist, which pane is visible — not how it is built, so
// they stay valid across the refactor.
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
      // Same order index.html uses: the host first, then the tab modules.
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
    // initialize() is async and kicked off by the bootstrap; wait for it.
    for (let i = 0; i < 200 && !(w.dimsApp && w.dimsApp.config); i++) {
      await new Promise(r => setTimeout(r, 5));
    }
    await new Promise(r => setTimeout(r, 20));
    return w;
  } finally {
    for (const k of QUIET) console[k] = saved[k];
  }
}

const labels = w => [...w.document.querySelectorAll('.tab-button')].map(b => b.textContent.trim());
const ids = w => [...w.document.querySelectorAll('.tab-button')].map(b => b.dataset.tab);

const BASE = { videoIDs: ['s1'], dataTypes: { s1: ['a', 'b'] }, defaultWindowSize: 5 };

test('no optional analyses: no tab bar', async () => {
  const w = await boot({ ...BASE });
  assert.deepStrictEqual(ids(w), [], 'a config with nothing enabled should show no tabs');
});

test('each include_* key adds exactly its own tab', async () => {
  const w = await boot({
    ...BASE,
    include_RQA: ['a'],
    include_cRQA: [['a', 'b']],
    include_crosswavelet: [['a', 'b']],
    include_elan: true,
  });
  assert.deepStrictEqual(ids(w), ['timeseries', 'rqa', 'crosswavelet', 'crqa', 'elan']);
  assert.ok(labels(w).includes('ELAN Annotations'), `labels were ${JSON.stringify(labels(w))}`);
});

test('RQA alone does not bring cross-wavelet or ELAN with it', async () => {
  const w = await boot({ ...BASE, include_RQA: ['a'] });
  assert.deepStrictEqual(ids(w), ['timeseries', 'rqa']);
});

test('cross-wavelet accepts the legacy flat data-type list', async () => {
  // DIMS_Dashboard and Ortho still ship this older form.
  const w = await boot({ ...BASE, include_crosswavelet: ['a', 'b'] });
  assert.ok(ids(w).includes('crosswavelet'), 'flat list should still enable the tab');
});

test('a single explicit cross-wavelet pair enables the tab', async () => {
  // Regression: the gate tested length >= 2 for both config forms, so one
  // pair -- a complete, valid analysis -- silently produced no tab.
  const w = await boot({ ...BASE, include_crosswavelet: [['a', 'b']] });
  assert.ok(ids(w).includes('crosswavelet'),
    'one explicit pair is a valid analysis and must show the tab');
});

test('a flat list of one data type does NOT enable cross-wavelet', async () => {
  // The other side of the same rule: one type cannot form a pair.
  const w = await boot({ ...BASE, include_crosswavelet: ['a'] });
  assert.ok(!ids(w).includes('crosswavelet'), 'a single data type cannot be a pair');
});

test('a pane exists for every tab, and only the active one is shown', async () => {
  const w = await boot({ ...BASE, include_RQA: ['a'], include_elan: true });
  const panes = ['plotContainer', 'rqaContainer', 'elanContainer'];
  for (const id of panes) assert.ok(w.document.getElementById(id), `missing pane #${id}`);

  w.dimsApp.switchTab('rqa');
  assert.strictEqual(w.document.getElementById('rqaContainer').style.display, 'block');
  assert.strictEqual(w.document.getElementById('elanContainer').style.display, 'none');

  w.dimsApp.switchTab('elan');
  assert.strictEqual(w.document.getElementById('elanContainer').style.display, 'block');
  assert.strictEqual(w.document.getElementById('rqaContainer').style.display, 'none');
});

test('switching tabs marks exactly one button active', async () => {
  const w = await boot({ ...BASE, include_RQA: ['a'], include_elan: true });
  w.dimsApp.switchTab('elan');
  const active = [...w.document.querySelectorAll('.tab-button.active')].map(b => b.dataset.tab);
  assert.deepStrictEqual(active, ['elan']);
});

// --- what a re-render throws away, and what it must not ----------------------
//
// The list of built-in tab caches was written out three times -- the
// constructor, rerenderAll and the video switch -- and they had drifted:
// rerenderAll left elanSelectedTiers set while the other two cleared it.
// Collapsing them into one list is right; collapsing them into one *behaviour*
// is not, because a theme change would then discard which ELAN tiers the
// viewer had asked to see. These tests say which is which, so the next person
// to notice the near-duplication does not "fix" it.

test('a re-render drops the cached payloads', async () => {
  const w = await boot({ ...BASE, include_RQA: ['a'], include_elan: true });
  const app = w.dimsApp;
  app.rqaData = { some: 'payload' };
  app.crossWaveletData = { some: 'payload' };
  app.crqaData = { some: 'payload' };
  app.elanData = { some: 'payload' };

  app._resetTabCaches();

  assert.strictEqual(app.rqaData, null);
  assert.strictEqual(app.crossWaveletData, null);
  assert.strictEqual(app.crqaData, null);
  assert.strictEqual(app.elanData, null);
});

test('a re-render keeps the ELAN tiers the viewer chose', async () => {
  const w = await boot({ ...BASE, include_RQA: ['a'], include_elan: true });
  const app = w.dimsApp;
  app.elanSelectedTiers = ['gaze', 'speech'];

  // The cache reset on its own must not touch it...
  app.elanData = { some: 'payload' };
  app._resetTabCaches();
  assert.deepStrictEqual(app.elanSelectedTiers, ['gaze', 'speech'],
    'the tier selection is a choice the viewer made, not a fetched payload');

  // ...nor must a whole re-render, which is what a theme switch triggers.
  //
  // `rerenderAll` is not async: it schedules `loadVideoData` and returns, and
  // the clear it has to survive sits after an `await` inside that. Asserting
  // here without yielding reads the value this test set two lines up and never
  // reaches the code under test -- which is what it did, so it passed while the
  // behaviour was broken.
  app.rerenderAll();
  await new Promise(r => setTimeout(r, 0));
  await new Promise(r => setTimeout(r, 60));
  assert.deepStrictEqual(app.elanSelectedTiers, ['gaze', 'speech'],
    'switching theme must not discard the tier selection');
});

test('changing recording does discard them, because the tiers were its own', async () => {
  // The other half of the asymmetry. A fix for the test above that simply
  // stopped clearing would pass it and break this.
  const w = await boot({ ...BASE, videoIDs: ['s1', 's2'], include_elan: true });
  const app = w.dimsApp;
  app.elanSelectedTiers = ['gaze', 'speech'];

  await app.loadVideoData('s2');
  assert.strictEqual(app.elanSelectedTiers, null,
    'tier names belong to a recording, so a new one starts over');
});

// --- a study that declares no window size, and one with no transcripts -------

test('a config without defaultWindowSize still labels its segment', async () => {
  // `defaultWindowSize` is optional in the schema. Without one, the initial
  // updateVideos was handed `undefined`, and `t - undefined / 2` is NaN -- so a
  // fresh load read "Segment (NaN s – NaN s)" before anything was clicked.
  const { defaultWindowSize, ...noWindow } = BASE;
  const w = await boot(noWindow);
  const app = w.dimsApp;

  assert.ok(Number.isFinite(app.windowSize()),
    `windowSize() returned ${app.windowSize()} for a config that declares none`);

  // The label is a prop on the React component, which the harness stubs -- so
  // it never reaches the DOM and cannot be read off the page. Capture it where
  // it is built instead.
  const titles = [];
  const realCreate = w.React.createElement;
  w.React.createElement = (type, props, ...rest) => {
    if (props && typeof props.title === 'string') titles.push(props.title);
    return realCreate(type, props, ...rest);
  };
  try {
    app.updateVideos(0, app.windowSize());
  } finally {
    w.React.createElement = realCreate;
  }

  assert.ok(titles.length, 'updateVideos rendered no titled component');
  for (const title of titles) {
    assert.ok(!title.includes('NaN'),
      `a video panel is labelled "${title}" for a config with no defaultWindowSize`);
  }
});

test('an absent optional file is not reported as a failure', async () => {
  // A study with no transcripts logged a console error per recording change
  // for a file its config never claimed. The panel already handles absence.
  const errors = [];
  const w = await boot(BASE);
  const app = w.dimsApp;
  const saved = w.console.error;
  w.console.error = (...a) => errors.push(a.join(' '));
  try {
    const got = await app.loadJSON('assets/transcripts/nope_transcript.json',
                                   { optional: true });
    assert.strictEqual(got, null, 'an absent optional file must still read as null');
  } finally {
    w.console.error = saved;
  }
  assert.deepStrictEqual(errors, [],
    `an absent optional file was reported as an error: ${errors.join(' | ')}`);
});
