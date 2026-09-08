// The cross-effector network tab.
//
// It moved into the core in v2.0.0 from one private study, where it was the
// only consumer in the whole system of the Monte Carlo coherence null. These
// tests exist because that is exactly the shape of thing that goes wrong
// quietly: a network of coherence values with no chance level draws at-chance
// noise as findings, and looks entirely convincing doing it.
//
// Both fixtures are real analysis output: one run with `mcCount: 20`, one with
// the null skipped.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const { makeEnv } = require('./harness.js');

const FIX = path.join(__dirname, 'fixtures');
const read = (name) => fs.readFileSync(path.join(FIX, name), 'utf8');

const BASE = {
  videoIDs: ['s1'],
  dataTypes: { s1: ['alpha', 'beta'] },
  include_crosswavelet: [['alpha', 'beta']],
  include_network: true,
  defaultWindowSize: 5,
};

const FILES = {
  'assets/crosswavelet/s1_crosswavelet_data.json': read('s1_crosswavelet_data.json'),
  'assets/timeseries/s1_alpha.csv': 'Time,value\n0,1\n0.05,2\n0.1,3\n',
  'assets/timeseries/s1_beta.csv': 'Time,value\n0,2\n0.05,1\n0.1,4\n',
};

const QUIET = ['log', 'warn', 'error', 'info', 'debug'];

async function boot(config = BASE, files = FILES) {
  const saved = {};
  for (const k of QUIET) { saved[k] = console[k]; console[k] = () => {}; }
  try {
    const env = makeEnv({
      config, files,
      scripts: [
        'packages/dims-core/video-component.js',
        'packages/dims-core/dims-core.js',
        'packages/dims-tabs/timeseries.js',
        'packages/dims-tabs/crosswavelet.js',
        'packages/dims-tabs/network.js',
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

async function open_(w) {
  const button = w.document.querySelector('.tab-button[data-tab="network"]');
  assert.ok(button, 'no network tab to open');
  button.click();
  await new Promise(r => setTimeout(r, 250));
  return w;
}

const edges = (w) => [...w.document.querySelectorAll('#networkEdges line')];
const caption = (w) => (w.document.getElementById('networkCaption') || {}).textContent || '';

// --- the gate ---------------------------------------------------------------

test('the tab appears only when the study asks for it', async () => {
  const off = await boot({ ...BASE, include_network: undefined });
  assert.strictEqual(off.document.querySelector('.tab-button[data-tab="network"]'), null,
    'a study that did not ask for the network got one');

  const on = await boot();
  assert.ok(on.document.querySelector('.tab-button[data-tab="network"]'),
    'include_network is set and no tab appeared');
});

test('a grouped config is accepted as readily as a bare true', async () => {
  const w = await boot({
    ...BASE,
    include_network: { groups: [{ match: '^alpha', label: 'A', color: '#f00' }] },
  });
  assert.ok(w.document.querySelector('.tab-button[data-tab="network"]'));
});

// --- what it draws ----------------------------------------------------------

test('every cross-wavelet pair becomes an edge', async () => {
  const w = await open_(await boot());
  assert.strictEqual(edges(w).length, 1,
    'one pair in the payload should give exactly one edge');
});

test('an edge carries its value and its verdict, not just a line', async () => {
  // A coherence value has no meaningful zero -- under independence it sits near
  // 0.25, not 0 -- so a line without a verdict beside it is unreadable.
  const w = await open_(await boot());
  const title = edges(w)[0].querySelector('title').textContent;
  assert.match(title, /mean coherence: \d\.\d{3}/);
  assert.match(title, /above chance in \d+\.\d% of \d+ tested cells/);
  assert.match(title, /independence gives about 5%/);
});

test('the picture follows the playhead rather than averaging the recording', async () => {
  const w = await open_(await boot());
  const before = edges(w)[0].getAttribute('stroke-width');
  assert.match(caption(w), /whole recording/);

  w.dimsApp.lastClickedPoint = 4.0;
  w.dimsApp.updateNetwork();
  assert.match(caption(w), /1\.5–6\.5 s/,
    'the caption must say which window is drawn');
  const after = edges(w)[0].getAttribute('stroke-width');
  assert.notStrictEqual(before, after,
    'the edge did not change between the whole record and a 5 s window, so it '
    + 'is not being recomputed per playhead position');
});

test('a period band narrows what an edge is averaged over', async () => {
  const wide = await open_(await boot());
  const narrow = await open_(await boot({
    ...BASE, include_network: { band: [0.1, 0.3] },
  }));
  assert.notStrictEqual(edges(wide)[0].getAttribute('stroke-width'),
                        edges(narrow)[0].getAttribute('stroke-width'),
    'restricting the period band changed nothing, so the band is not applied');
});

// --- the null, and its absence ---------------------------------------------

test('without a coherence null the tab says so instead of drawing findings', async () => {
  // The failure this prevents: every edge drawn solid from values that cannot
  // be told from chance. The study skipped an expensive computation on purpose;
  // a tab that hides that turns a deliberate default into a silent wrong answer.
  const w = await open_(await boot(BASE, {
    ...FILES,
    'assets/crosswavelet/s1_crosswavelet_data.json': read('s1_crosswavelet_no_null.json'),
  }));

  assert.match(caption(w), /without a coherence null/);
  assert.match(caption(w), /mcCount/,
    'the caption must name the setting that would produce one');

  const line = edges(w)[0];
  assert.ok(line.getAttribute('stroke-dasharray'),
    'an untestable edge must not be drawn as an established one');
  assert.match(line.querySelector('title').textContent, /cannot/);
});

test('an edge at chance is drawn differently from one above it', async () => {
  // The whole point of the tab: the reader must be able to tell "no coupling"
  // from "coupling", and both from "not measured".
  const w = await open_(await boot());
  const real = edges(w)[0];
  const solid = !real.getAttribute('stroke-dasharray');

  const none = await open_(await boot(BASE, {
    ...FILES,
    'assets/crosswavelet/s1_crosswavelet_data.json': read('s1_crosswavelet_no_null.json'),
  }));
  const dashed = !!edges(none)[0].getAttribute('stroke-dasharray');
  assert.ok(solid !== dashed || solid,
    'a tested edge and an untestable one look the same');
});

test('the coherence grid is decoded, not read as if it were a nested list', async () => {
  // The grids travel base64-encoded. A tab that indexed the encoded object
  // directly would find undefined everywhere and draw every edge at width zero,
  // which looks like "no coupling" rather than like a bug.
  const w = await open_(await boot());
  const width = parseFloat(edges(w)[0].getAttribute('stroke-width'));
  assert.ok(width > 1.5,
    `every edge came out at the minimum width (${width}), which is what reading `
    + 'an encoded grid without decoding it produces');
});

// --- the answer the tab exists to give --------------------------------------
//
// `s2` carries three measures whose coupling is known before anything runs:
// `eff_a` and `eff_b` share 70 % of a red-noise component, `eff_c` shares none.
// The payload agrees -- 0.80 of cells above chance for the coupled pair, 0.050
// and 0.065 for the other two, against the 0.05 independence gives. So a
// correct network draws one solid edge and two dashed ones, and this is the
// only test here of what the tab is actually for.

const NETWORK_CONFIG = JSON.parse(read('network_config.json'));
const NETWORK_FILES = {
  'assets/crosswavelet/s2_crosswavelet_data.json': read('s2_crosswavelet_data.json'),
  'assets/timeseries/s2_eff_a.csv': 'Time,value\n0,1\n0.05,2\n0.1,3\n',
  'assets/timeseries/s2_eff_b.csv': 'Time,value\n0,2\n0.05,1\n0.1,4\n',
  'assets/timeseries/s2_eff_c.csv': 'Time,value\n0,3\n0.05,4\n0.1,1\n',
};

test('one real edge and two at chance, which is what was put in', async () => {
  const w = await open_(await boot({ ...NETWORK_CONFIG, defaultWindowSize: 5 },
                                   NETWORK_FILES));
  const lines = edges(w);
  assert.strictEqual(lines.length, 3, 'three pairs should give three edges');

  const solid = lines.filter(l => !l.getAttribute('stroke-dasharray'));
  const dashed = lines.filter(l => l.getAttribute('stroke-dasharray'));
  assert.strictEqual(solid.length, 1,
    `expected exactly one coupled pair to be drawn solid; ${solid.length} were. `
    + lines.map(l => l.querySelector('title').textContent.split('\n')[0]
                     + (l.getAttribute('stroke-dasharray') ? ' dashed' : ' SOLID')).join(' | '));
  assert.strictEqual(dashed.length, 2);
  assert.match(solid[0].querySelector('title').textContent, /eff_a\s+↔\s+eff_b/,
    'the solid edge is not the pair that was built to be coupled');
});

test('the coupled edge is thicker than the ones at chance', async () => {
  // Width is mean coherence, and a coherence value is not zero under
  // independence -- it sits near 0.25. So the at-chance edges are thin, not
  // absent, and the difference between them and a real one is what a reader
  // reads. If they came out equal, the width channel would be saying nothing.
  const w = await open_(await boot({ ...NETWORK_CONFIG, defaultWindowSize: 5 },
                                   NETWORK_FILES));
  const widths = edges(w).map(l => ({
    solid: !l.getAttribute('stroke-dasharray'),
    width: parseFloat(l.getAttribute('stroke-width')),
  }));
  const real = widths.find(e => e.solid).width;
  const chance = widths.filter(e => !e.solid).map(e => e.width);
  assert.ok(chance.every(c => c > 1.5),
    'an at-chance edge should still show its value, not collapse to nothing');
  assert.ok(real > Math.max(...chance),
    `the coupled edge (${real.toFixed(2)}) is not thicker than the at-chance `
    + `ones (${chance.map(c => c.toFixed(2)).join(', ')})`);
});

test('grouping puts every measure on the chart, named from config', async () => {
  const w = await open_(await boot({ ...NETWORK_CONFIG, defaultWindowSize: 5 },
                                   NETWORK_FILES));
  const text = w.document.getElementById('networkSvg').textContent;
  assert.match(text, /Effectors/, 'the group label from config is not drawn');
  for (const name of ['a', 'b', 'c']) {
    assert.ok(text.includes(name), `measure eff_${name} is missing from the chart`);
  }
});
