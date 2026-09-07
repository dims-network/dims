// Multi-perspective video: a core capability, because it is a property of video
// rather than of any one tab. Ortho had it wired into its own copy of the
// dashboard, where no other study could reach it.
const test = require('node:test');
const assert = require('node:assert');
const { makeEnv } = require('./harness.js');

const SCRIPTS = [
  'packages/dims-core/video-component.js',
  'packages/dims-core/dims-core.js',
  'packages/dims-tabs/timeseries.js',
];
const QUIET = ['log', 'warn', 'error', 'info', 'debug'];

async function boot(config) {
  const saved = {};
  for (const k of QUIET) { saved[k] = console[k]; console[k] = () => {}; }
  try {
    const env = makeEnv({ config, scripts: SCRIPTS });
    const w = env.window;
    for (const k of QUIET) if (w.console) w.console[k] = () => {};
    for (let i = 0; i < 200 && !(w.dimsApp && w.dimsApp.config); i++) await new Promise(r => setTimeout(r, 5));
    await new Promise(r => setTimeout(r, 20));
    return w;
  } finally { for (const k of QUIET) console[k] = saved[k]; }
}

const BASE = { videoIDs: ['s1'], dataTypes: { s1: ['a'] }, defaultWindowSize: 5 };

test('a study with no perspectives is completely unaffected', async () => {
  const w = await boot({ ...BASE });
  assert.strictEqual(w.dimsApp.buildVideoSrc(), 'assets/videos/s1.mp4');
  assert.strictEqual(w.document.getElementById('perspectiveSelect'), null,
    'no dead control should be added');
});

test('the selector is built from config, not from index.html', async () => {
  const w = await boot({ ...BASE, perspectives: ['wide', 'parent', 'child'],
    videoSrcTemplate: 'assets/videos/{videoID}_{persp}.mp4' });
  const sel = w.document.getElementById('perspectiveSelect');
  assert.ok(sel, 'the selector should exist');
  assert.deepStrictEqual([...sel.options].map(o => o.value), ['', 'wide', 'parent', 'child']);
});

test('auto picks the first angle that exists for this video', async () => {
  // Not every session has every angle — recordings fail.
  const w = await boot({ ...BASE, perspectives: ['wide', 'parent', 'child'],
    videoSrcTemplate: 'assets/videos/{videoID}_{persp}.mp4',
    videoPerspectives: { s1: ['parent', 'child'] } });
  assert.strictEqual(w.dimsApp.buildVideoSrc(), 'assets/videos/s1_parent.mp4',
    'wide is not available for s1, so auto should skip it');
});

test('choosing an angle overrides auto', async () => {
  const w = await boot({ ...BASE, perspectives: ['wide', 'parent'],
    videoSrcTemplate: 'assets/videos/{videoID}_{persp}.mp4' });
  w.dimsApp.currentPerspective = 'parent';
  assert.strictEqual(w.dimsApp.buildVideoSrc(), 'assets/videos/s1_parent.mp4');
});

test('the fallback template is used when no angle can be resolved', async () => {
  const w = await boot({ ...BASE,
    videoSrcTemplate: 'assets/videos/{videoID}_{persp}.mp4',
    fallbackVideoSrcTemplate: 'assets/videos/{videoID}_wide.mp4' });
  assert.strictEqual(w.dimsApp.buildVideoSrc(), 'assets/videos/s1_wide.mp4');
});
