// The network tab came from a fork where it was the only tab using the
// registry. These check it behaves like any other tab now that it is in the
// core -- and that it still refuses to draw edges it cannot justify.
const test = require('node:test');
const assert = require('node:assert');
const { makeEnv } = require('./harness.js');

const SCRIPTS = [
  'packages/dims-core/video-component.js',
  'packages/dims-core/dims-core.js',
  'packages/dims-tabs/timeseries.js',
  'packages/dims-tabs/crosswavelet.js',
  'packages/dims-tabs/network.js',
];
const QUIET = ['log', 'warn', 'error', 'info', 'debug'];

// A minimal but structurally real cross-wavelet payload for two effector pairs.
function cwPayload({ withNull = true } = {}) {
  const nT = 8, nP = 4;
  const grid = (v) => Array.from({ length: nP }, () => Array.from({ length: nT }, () => v));
  const pair = (coh) => ({
    data_type1: 'a', data_type2: 'b',
    visualization: {
      time: Array.from({ length: nT }, (_, i) => i * 0.5),
      period: [0.5, 1, 2, 4],
      freqs: [2, 1, 0.5, 0.25],
      coherence: grid(coh),
      power: grid(1),
      phase: grid(0),
      coi: Array.from({ length: nT }, () => 4),
      sig95_xwt: grid(1),
      ...(withNull ? { sig95_wtc: [0.6, 0.6, 0.6, null] } : {}),
    },
    statistics: { mean_coherence: coh },
  });
  return JSON.stringify({
    video_id: 's1',
    crosswavelet_pairs: {
      'teacher_lefthandspeed_vs_student_lefthandspeed': pair(0.9),
      'teacher_righthandspeed_vs_student_righthandspeed': pair(0.2),
    },
  });
}

async function boot(config, files) {
  const saved = {};
  for (const k of QUIET) { saved[k] = console[k]; console[k] = () => {}; }
  try {
    const env = makeEnv({ config, files, scripts: SCRIPTS });
    const w = env.window;
    for (const k of QUIET) if (w.console) w.console[k] = () => {};
    for (let i = 0; i < 200 && !(w.dimsApp && w.dimsApp.config); i++) await new Promise(r => setTimeout(r, 5));
    await new Promise(r => setTimeout(r, 20));
    return w;
  } finally { for (const k of QUIET) console[k] = saved[k]; }
}

const CONFIG = {
  videoIDs: ['s1'],
  dataTypes: { s1: ['teacher_lefthandspeed', 'student_lefthandspeed'] },
  include_crosswavelet: [['teacher_lefthandspeed', 'student_lefthandspeed']],
  defaultWindowSize: 5,
};
const ids = w => [...w.document.querySelectorAll('.tab-button')].map(b => b.dataset.tab);

test('the network tab registers in the core like any other', async () => {
  const w = await boot(CONFIG, { 'assets/crosswavelet/s1_crosswavelet_data.json': cwPayload() });
  assert.ok(ids(w).includes('network'), `tabs were ${JSON.stringify(ids(w))}`);
  assert.ok(w.document.getElementById('networkContainer'), 'its pane should be built by the core');
});

test('it is hidden when there is no cross-wavelet analysis', async () => {
  const w = await boot({ ...CONFIG, include_crosswavelet: [] }, {});
  assert.ok(!ids(w).includes('network'));
});

test('it renders into its own container and touches no other pane', async () => {
  const w = await boot(CONFIG, { 'assets/crosswavelet/s1_crosswavelet_data.json': cwPayload() });
  const before = w.document.getElementById('plotContainer').innerHTML;
  w.dimsApp.switchTab('network');
  await new Promise(r => setTimeout(r, 60));
  const pane = w.document.getElementById('networkContainer');
  assert.ok(pane.innerHTML.length > 0, 'the network pane should have been drawn into');
  assert.strictEqual(w.document.getElementById('plotContainer').innerHTML, before,
    'it must not draw into another tab\'s pane');
});

test('the output suffix is gone, and stays gone', async () => {
  // crosswaveletSuffix let a corrected run sit beside the original while the
  // correction was being validated. That comparison is finished; keeping a
  // variant-output mechanism is just a way to end up with two answers again.
  const fs = require('fs');
  const path = require('path');
  const { ROOT } = require('./harness.js');
  for (const rel of ['packages/dims-tabs/crosswavelet.js', 'packages/dims-tabs/network.js']) {
    const src = fs.readFileSync(path.join(ROOT, rel), 'utf8');
    assert.ok(!src.includes('crosswaveletSuffix'), `${rel} still reads crosswaveletSuffix`);
    assert.ok(!src.includes('_wtcfix'), `${rel} still references the variant suffix`);
  }

  // and the plain path is what actually gets fetched
  const w = await boot(CONFIG, { 'assets/crosswavelet/s1_crosswavelet_data.json': cwPayload() });
  w.dimsApp.switchTab('network');
  await new Promise(r => setTimeout(r, 60));
  assert.ok(w.dimsApp.crossWaveletData, 'the unsuffixed file should have been loaded');
});
