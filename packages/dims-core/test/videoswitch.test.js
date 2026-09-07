// Switching video must redraw the tab you are looking at.
//
// It did not: changing video resets every tab's activation flag so it recomputes
// when next shown, but the VISIBLE tab never gets a "next shown". You had to
// switch away and back. Two hardcoded branches named rqa and crosswavelet, so
// even those two were the only ones that half-worked.
const test = require('node:test');
const assert = require('node:assert');
const { makeEnv } = require('./harness.js');

const QUIET = ['log', 'warn', 'error', 'info', 'debug'];

// A tab that records every activation, so the test can see redraws happen.
const SPY = `
  window.__activations = [];
  window.__videoChanges = [];
  window.DIMS.registerTab({
    id: 'spy', label: 'Spy', order: 5,
    gate: () => true,
    onActivate(app, container) {
      window.__activations.push(app.currentVideoID);
      container.textContent = 'showing ' + app.currentVideoID;
    },
    onVideoChange(app, videoID) { window.__videoChanges.push(videoID); }
  });`;

async function boot(config, files, extra) {
  const saved = {};
  for (const k of QUIET) { saved[k] = console[k]; console[k] = () => {}; }
  try {
    const env = makeEnv({ config, files, scripts: [
      'packages/dims-core/video-component.js',
      'packages/dims-core/dims-core.js',
      'packages/dims-tabs/timeseries.js',
      'packages/dims-tabs/rqa.js',
    ]});
    const w = env.window;
    for (const k of QUIET) if (w.console) w.console[k] = () => {};
    if (extra) w.eval(extra);
    for (let i = 0; i < 200 && !(w.dimsApp && w.dimsApp.config); i++) await new Promise(r => setTimeout(r, 5));
    await new Promise(r => setTimeout(r, 30));
    return w;
  } finally { for (const k of QUIET) console[k] = saved[k]; }
}

const CSV = 'Time,a\n0,1\n1,2\n2,3\n';
const CFG = {
  videoIDs: ['s1', 's2'],
  dataTypes: { s1: ['a'], s2: ['a'] },
  include_RQA: ['a'],
  defaultWindowSize: 5,
};
const FILES = {
  'assets/timeseries/s1_a.csv': CSV,
  'assets/timeseries/s2_a.csv': CSV,
};

test('the visible tab is redrawn when the video changes', async () => {
  const w = await boot(CFG, FILES, SPY);
  w.dimsApp.switchTab('spy');
  await new Promise(r => setTimeout(r, 30));
  assert.deepStrictEqual([...w.__activations], ['s1'], 'activated once, for the first video');

  await w.dimsApp.loadVideoData('s2');
  await new Promise(r => setTimeout(r, 50));

  // s1 is included: the first load notifies too, which is right — a tab should
  // clear its state whenever the video it was drawing is replaced, including
  // when it is replaced by the first one.
  assert.deepStrictEqual([...w.__videoChanges], ['s1', 's2'],
    'the tab should be told the video changed');
  assert.deepStrictEqual([...w.__activations], ['s1', 's2'],
    'the visible tab must be redrawn for the new video, without switching away and back');
  assert.strictEqual(w.document.getElementById('spyContainer').textContent, 'showing s2');
});

test('a tab that is NOT visible is not redrawn until it is shown', async () => {
  // The other half of the rule: invalidate everything, but only pay for what
  // is on screen.
  const w = await boot(CFG, FILES, SPY);
  w.dimsApp.switchTab('timeseries');
  await new Promise(r => setTimeout(r, 20));
  const before = [...w.__activations].length;

  await w.dimsApp.loadVideoData('s2');
  await new Promise(r => setTimeout(r, 50));
  assert.strictEqual([...w.__activations].length, before,
    'a hidden tab should not recompute on a video change');

  w.dimsApp.switchTab('spy');
  await new Promise(r => setTimeout(r, 30));
  assert.strictEqual([...w.__activations].pop(), 's2',
    'and when shown, it should draw the current video');
});

test('the core names no tab in its video-change path', async () => {
  // The bug existed because loadVideoData hardcoded rqa and crosswavelet.
  const fs = require('fs');
  const path = require('path');
  const { ROOT } = require('./harness.js');
  const src = fs.readFileSync(path.join(ROOT, 'packages/dims-core/dims-core.js'), 'utf8');
  const hardcoded = src.split('\n').filter(l =>
    /currentTab\s*===\s*['"]/.test(l) && !l.trimStart().startsWith('//'));
  assert.deepStrictEqual(hardcoded, [],
    'the host must not special-case any tab by name');
});
