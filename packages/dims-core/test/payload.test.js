// The seam between the Python analyses and the tabs, in both directions.
//
// Nothing tested it. Every other JS test here builds its own small object and
// hands it to a tab, which means the tests agree with the tests: a tab reading
// the wrong key passes, because the fixture was written to match the tab. That
// is not hypothetical -- the container key for cross-wavelet output is
// `crosswavelet_pairs` and not `crosswavelet_data`, and reading the wrong one
// returns nothing and raises nothing. The result is an empty panel and a green
// suite.
//
// These fixtures are the real thing: produced by running dims-analysis over
// short synthetic series. Regenerate with
//     python fixtures/generate.py
// after any change to what a step writes. If a tab then fails here, the tab
// and the analysis have disagreed, which is exactly what this file is for.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const { makeEnv } = require('./harness.js');

const FIX = path.join(__dirname, 'fixtures');
const read = (name) => fs.readFileSync(path.join(FIX, name), 'utf8');

const CONFIG = JSON.parse(read('config.json'));
const FILES = {
  'assets/rqa/s1_rqa_data.json': read('s1_rqa_data.json'),
  'assets/crqa/s1_crqa_data.json': read('s1_crqa_data.json'),
  'assets/crosswavelet/s1_crosswavelet_data.json': read('s1_crosswavelet_data.json'),
  'assets/timeseries/s1_alpha.csv': 'Time,value\n0,1\n0.05,2\n0.1,3\n',
  'assets/timeseries/s1_beta.csv': 'Time,value\n0,2\n0.05,1\n0.1,4\n',
};

const QUIET = ['log', 'warn', 'error', 'info', 'debug'];

async function boot(config = CONFIG, files = FILES) {
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
    await new Promise(r => setTimeout(r, 60));
    return w;
  } finally {
    for (const k of QUIET) console[k] = saved[k];
  }
}

// --- what the analyses actually wrote ---------------------------------------

test('the fixtures are what the analyses write, not what a test wished for', () => {
  const rqa = JSON.parse(read('s1_rqa_data.json'));
  const crqa = JSON.parse(read('s1_crqa_data.json'));
  const cwt = JSON.parse(read('s1_crosswavelet_data.json'));

  // The three container keys, which are not uniform and are the easiest thing
  // in this system to get wrong.
  assert.ok(rqa.rqa_data, 'rqa payload has no rqa_data');
  assert.ok(crqa.crqa_data, 'crqa payload has no crqa_data');
  assert.ok(cwt.crosswavelet_pairs,
    'cross-wavelet output is keyed crosswavelet_pairs — not crosswavelet_data');
  assert.strictEqual(cwt.crosswavelet_data, undefined,
    'if this ever exists, a tab reading it would silently show nothing');
});

test('a recurrence payload carries the picture and what it is a reduction of', () => {
  const rqa = JSON.parse(read('s1_rqa_data.json'));
  const entry = rqa.rqa_data.alpha;
  assert.ok(entry, 'no entry for the data type the config asked for');

  const v = entry.visualization;
  assert.strictEqual(v.matrix.encoding, 'bitmap-b64',
    'the recurrence plot must arrive as a bitmap the core knows how to read');
  assert.ok(v.matrix_size > 0);
  assert.strictEqual(v.time.length, v.matrix_size,
    'the drawn time axis and the drawn matrix must be the same length');

  // The bitmap describes the REDUCED grid. A tab drawing it against the full
  // axis would draw the wrong picture at the wrong times.
  assert.strictEqual(v.matrix.rows, v.matrix_size);
  assert.strictEqual(v.matrix.cols, v.matrix_size);

  assert.ok(v.reduction, 'no reduction block: a reader cannot tell what the axis means');
  assert.ok(v.reduction.factor >= 1);
  assert.ok(Math.abs(v.reduction.rate_drawn - v.reduction.rate_full) < 0.02,
    'the drawn density must match the rate reported beside it');
});

test('a cross-wavelet payload carries a chance level, not just coherence', () => {
  const cwt = JSON.parse(read('s1_crosswavelet_data.json'));
  const pair = Object.values(cwt.crosswavelet_pairs)[0];
  const v = pair.visualization;

  assert.ok(v.coherence, 'no coherence');
  assert.strictEqual(v.coherence.encoding, 'f32-b64');
  assert.deepStrictEqual(v.coherence.shape, [v.period.length, v.time.length],
    'the coherence grid must match the axes it is drawn against');
  // The per-scale power level, from which a tab derives the ratio it
  // thresholds. Storing that ratio as a third full grid held nothing these
  // two do not.
  assert.strictEqual((v.signif_xwt || []).length, v.period.length);
  assert.strictEqual(v.sig95_xwt, undefined,
    'a derived grid is back in the payload');
  // Without this a coherence value is unreadable: unrelated signals do not
  // score zero, they score about 0.25-0.6.
  assert.ok(v.sig95_wtc, 'no sig95_wtc — there is nothing to read coherence against');
  assert.strictEqual(v.sig95_wtc.length, v.period.length);
  assert.ok(v.coi, 'no cone of influence');
});

test('undefined coherence travels as null, never as NaN', () => {
  // json.dump writes a bare NaN token, which JSON.parse rejects outright, so a
  // single undefined cell would make a study's whole payload unreadable.
  const raw = read('s1_crosswavelet_data.json');
  assert.ok(!/\bNaN\b/.test(raw), 'a bare NaN token would break JSON.parse in the browser');
  assert.doesNotThrow(() => JSON.parse(raw));
});

// --- and what the tabs do with it -------------------------------------------

test('every enabled tab appears for a real payload', async () => {
  const w = await boot();
  const ids = [...w.document.querySelectorAll('.tab-button')].map(b => b.dataset.tab);
  for (const want of ['rqa', 'crqa', 'crosswavelet']) {
    assert.ok(ids.includes(want), `no ${want} tab: ids were ${JSON.stringify(ids)}`);
  }
});

// Only the visible tab draws. Asserting that "something was plotted" therefore
// only ever checked the time-series tab, which is the one shown first -- so
// pointing the cross-wavelet tab at the wrong container key left this file
// green. Each tab is opened, and its own figure is what is asserted on.
const OWN_FIGURE = {
  rqa: 'rqa-plot-',
  crqa: 'crqa-plot-',
  crosswavelet: 'cw-plot-',
};

async function open_(w, id) {
  const before = w.__plotted.length;
  w.document.querySelector(`.tab-button[data-tab="${id}"]`).click();
  await new Promise(r => setTimeout(r, 250));
  return w.__plotted.slice(before);
}

for (const [id, prefix] of Object.entries(OWN_FIGURE)) {
  test(`the ${id} tab draws from a real payload`, async () => {
    const w = await boot();
    const made = await open_(w, id);
    const mine = made.filter(p => String(p.el).startsWith(prefix));
    assert.ok(mine.length > 0,
      `the ${id} tab plotted nothing of its own from output the analyses ` +
      `produced; it drew ${JSON.stringify(made.map(m => m.el))}`);
    assert.ok(mine.every(p => p.n > 0), `${id} drew a figure with no traces`);
  });
}

test('no tab reports missing data while holding a real payload', async () => {
  const w = await boot();
  for (const id of Object.keys(OWN_FIGURE)) await open_(w, id);
  const text = w.document.body.textContent;
  for (const excuse of ['No data available', 'Failed to load', 'not found']) {
    assert.ok(!text.includes(excuse),
      `a tab said "${excuse}" while holding output the analyses actually produced`);
  }
});

test('a payload for a video the config does not list is not drawn', async () => {
  // The other direction: the tabs must not draw whatever they happen to find.
  const w = await boot(CONFIG, {
    ...FILES,
    'assets/rqa/s99_rqa_data.json': read('s1_rqa_data.json'),
  });
  const options = [...w.document.querySelectorAll('#videoSelect option')].map(o => o.value);
  assert.ok(!options.includes('s99'), 'a stray asset added a recording to the study');
});

// --- what is computed is shown, or it is not computed ------------------------
//
// The Monte Carlo coherence null costs hours on a real study -- ORTHO's whole
// cross-wavelet run was ~2.8 h and this is the bottleneck -- and for three
// releases exactly one tab in one private study read it. Skipping it when
// nothing reads it is now the default and is right; a tab that quietly draws
// nothing either way is what turns that deliberate choice into a missing
// feature nobody can diagnose.
//
// Both fixtures are real analysis output: one run with `mcCount: 20`, one with
// the null skipped, which is what a config with no consumer gets.

const cwTitle = (made) => {
  const fig = made.find(p => String(p.el).startsWith('cw-plot-'));
  assert.ok(fig, 'the cross-wavelet tab drew no figure at all');
  return String(((fig.layout || {}).title || {}).text || '');
};

test('the coherence chance level is reported when it was computed', async () => {
  const w = await boot();
  const title = cwTitle(await open_(w, 'crosswavelet'));
  assert.match(title, /Coherence above chance/,
    'a study paid for a Monte Carlo null and the tab said nothing about it');
  assert.match(title, /\d+\.\d% of cells/, 'no fraction in the caption');
  assert.match(title, /20 surrogates/,
    'the caption does not say how many surrogates the number rests on');
});

test('a missing coherence null is named, not silently skipped', async () => {
  const w = await boot(CONFIG, {
    ...FILES,
    'assets/crosswavelet/s1_crosswavelet_data.json': read('s1_crosswavelet_no_null.json'),
  });
  const title = cwTitle(await open_(w, 'crosswavelet'));
  assert.match(title, /not computed/,
    'the null was skipped and the tab drew as if nothing were missing');
  assert.match(title, /mcCount/,
    'the caption must name the setting that would produce it');
  assert.doesNotMatch(title, /Coherence above chance/,
    'a fraction was reported for an output that has none');
});

test('the two averaged significance levels are drawn beside what they judge', async () => {
  // Panel C plots the time-averaged spectrum and panel D the scale-averaged
  // power. Both had a 95 % level computed for every study and read by nothing,
  // which is how both spent three releases applying a single-spectrum
  // chi-square to a cross-wavelet quantity with nobody noticing.
  const w = await boot();
  const made = await open_(w, 'crosswavelet');
  const fig = made.find(p => String(p.el).startsWith('cw-plot-'));
  const levels = (fig.data || []).filter(t => t.name === '95% level');
  assert.strictEqual(levels.length, 2,
    `expected the global and scale-averaged levels to be drawn; found ` +
    `${levels.length} traces named "95% level"`);
  assert.ok(levels.some(t => t.yaxis === 'y2'), 'no level beside the global spectrum');
  assert.ok(levels.some(t => t.yaxis === 'y3'), 'no level beside the scale-averaged power');
});

// --- a study that bumped without rebuilding ---------------------------------
//
// The one failure v2.0.0 most wants nobody to find by looking at a dashboard.
// The payload format changed, so an asset built by an older core has no field
// the new tabs read, and a tab that simply draws nothing is indistinguishable
// from a study with no data at all.

const withVersion = (name, version) => {
  const payload = JSON.parse(read(name));
  if (version === null) delete payload.payload_version;
  else payload.payload_version = version;
  return JSON.stringify(payload);
};

for (const [tab, asset, container] of [
  ['rqa', 'assets/rqa/s1_rqa_data.json', 's1_rqa_data.json'],
  ['crqa', 'assets/crqa/s1_crqa_data.json', 's1_crqa_data.json'],
  ['crosswavelet', 'assets/crosswavelet/s1_crosswavelet_data.json',
   's1_crosswavelet_data.json'],
]) {
  test(`the ${tab} tab names an asset from an older core instead of drawing nothing`,
    async () => {
      const w = await boot(CONFIG, { ...FILES, [asset]: withVersion(container, null) });
      await open_(w, tab);
      const text = w.document.body.textContent;
      assert.match(text, /older than 2\.0\.0/,
        `the ${tab} tab drew a pre-2.0.0 asset without saying it could not read it`);
      assert.match(text, /build_assets\.py/,
        'the message must say how to fix it');
    });

  test(`the ${tab} tab names an asset from a newer core`, async () => {
    const w = await boot(CONFIG, { ...FILES, [asset]: withVersion(container, 99) });
    await open_(w, tab);
    const text = w.document.body.textContent;
    assert.match(text, /newer core/);
    assert.match(text, /payload version 99/);
  });
}

test('a payload at the current version is drawn without complaint', async () => {
  // The other direction, so the check cannot pass by refusing everything.
  const w = await boot();
  for (const tab of ['rqa', 'crqa', 'crosswavelet']) await open_(w, tab);
  const text = w.document.body.textContent;
  assert.ok(!/older than|newer core|payload version/.test(text),
    'a current payload was reported as unreadable');
});
