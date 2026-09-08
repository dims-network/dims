// The registry has to be honest: a tab must be removable by deleting its file,
// and a third-party tab must reach the same capabilities as a built-in one.
//
// This is the check the whole refactor exists to make possible. If it passes
// only for plugins and not for built-ins, the extension point is decorative.
const test = require('node:test');
const assert = require('node:assert');
const { makeEnv } = require('./harness.js');

const CORE = ['packages/dims-core/video-component.js', 'packages/dims-core/dims-core.js'];
const TABS = ['timeseries', 'rqa', 'crosswavelet', 'crqa', 'elan'].map(t => `packages/dims-tabs/${t}.js`);
const QUIET = ['log', 'warn', 'error', 'info', 'debug'];

async function boot(config, scripts, extra) {
  const saved = {};
  for (const k of QUIET) { saved[k] = console[k]; console[k] = () => {}; }
  try {
    const env = makeEnv({ config, scripts });
    const w = env.window;
    for (const k of QUIET) if (w.console) w.console[k] = () => {};
    if (extra) w.eval(extra);
    for (let i = 0; i < 200 && !(w.dimsApp && w.dimsApp.config); i++) await new Promise(r => setTimeout(r, 5));
    await new Promise(r => setTimeout(r, 20));
    return w;
  } finally { for (const k of QUIET) console[k] = saved[k]; }
}

const ids = w => [...w.document.querySelectorAll('.tab-button')].map(b => b.dataset.tab);
const FULL = {
  videoIDs: ['s1'], dataTypes: { s1: ['a', 'b'] }, defaultWindowSize: 5,
  include_RQA: ['a'], include_cRQA: [['a', 'b']], include_crosswavelet: [['a', 'b']], include_elan: true,
};

test('removing a tab file removes that tab and nothing else', async () => {
  const without = [...CORE, ...TABS.filter(p => !p.endsWith('elan.js'))];
  const w = await boot(FULL, without);
  assert.ok(!ids(w).includes('elan'), 'ELAN should be gone with its file');
  assert.deepStrictEqual(ids(w), ['timeseries', 'rqa', 'crosswavelet', 'crqa'],
    'every other tab must be unaffected');
  assert.ok(!w.document.getElementById('elanContainer'), 'and its pane should not be built');
});

test('built-in tabs go through the same registry as any other', async () => {
  const w = await boot(FULL, [...CORE, ...TABS]);
  // spread into a native array: values from the jsdom realm have a different
  // Array.prototype, which deepStrictEqual rejects even when the contents match
  const registered = [...w.DIMS._tabs].map(t => t.id).sort();
  assert.deepStrictEqual(registered, ['crosswavelet', 'crqa', 'elan', 'rqa', 'timeseries'],
    'the built-ins must be registrations, not special cases');
});

test('a third-party tab needs no change to the core', async () => {
  const plugin = `
    window.DIMS.registerTab({
      id: 'outsider', label: 'From Outside', order: 99,
      gate: cfg => cfg.include_elan === true,
      onActivate(app, container) { container.textContent = 'rendered by a plugin'; },
      onTimeUpdate(app, time) { window.__pluginSawTime = time; }
    });`;
  const w = await boot(FULL, [...CORE, ...TABS], plugin);
  assert.ok(ids(w).includes('outsider'), 'a tab registered from outside should appear');

  w.dimsApp.switchTab('outsider');
  await new Promise(r => setTimeout(r, 10));
  assert.strictEqual(w.document.getElementById('outsiderContainer').textContent, 'rendered by a plugin');

  // and it receives the playhead through the same bus the built-ins use
  w.dimsApp.emitTimeChange(12.5, 5);
  assert.strictEqual(w.__pluginSawTime, 12.5, 'plugin should get onTimeUpdate while visible');
});

test('a tab whose gate throws is hidden, not fatal', async () => {
  const plugin = `
    window.DIMS.registerTab({
      id: 'broken', label: 'Broken', gate() { throw new Error('gate exploded'); },
      onActivate() {}
    });`;
  const w = await boot(FULL, [...CORE, ...TABS], plugin);
  assert.ok(!ids(w).includes('broken'), 'a throwing gate must hide the tab');
  assert.ok(ids(w).includes('rqa'), 'and must not take the other tabs down with it');
});

test('a duplicate tab id is refused rather than shadowing the original', async () => {
  const plugin = `
    window.DIMS.registerTab({ id: 'rqa', label: 'Impostor', onActivate() {} });`;
  const w = await boot(FULL, [...CORE, ...TABS], plugin);
  const rqa = [...w.DIMS._tabs].filter(t => t.id === 'rqa');
  assert.strictEqual(rqa.length, 1);
  assert.strictEqual(rqa[0].label, 'RQA Plots', 'the original must win');
});

test('the time bus reaches subscribers that are not the visible tab', async () => {
  const w = await boot(FULL, [...CORE, ...TABS]);
  const seen = [];
  const unsubscribe = w.dimsApp.onTimeChange((t, win) => seen.push([t, win]));
  w.dimsApp.emitTimeChange(3.25, 4);
  assert.deepStrictEqual(seen, [[3.25, 4]]);
  unsubscribe();
  w.dimsApp.emitTimeChange(9, 4);
  assert.strictEqual(seen.length, 1, 'unsubscribing should stop delivery');
});
