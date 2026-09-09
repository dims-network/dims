// What the wizard does with an existing network config.
//
// The property under test is a round trip: read a config into the controls,
// then collect it back, and get the same thing. It is the one assertion that
// catches a key the page cannot display -- which is what `layout` was, and what
// an effector's x/y still is.
const test = require('node:test');
const assert = require('node:assert');
const { boot } = require('./harness.js');

// Objects come back from the page's own realm, where Object.prototype is a
// different object, so deepStrictEqual refuses them on identity alone. What
// these tests are about is the data, so compare the data.
const plain = (v) => JSON.parse(JSON.stringify(v));

// Two measures, so the effector table has rows to render.
const FILES = [
  { id: '1', name: 's1_alpha.csv', role: 'timeseries', videoID: 's1', dataType: 'alpha' },
  { id: '2', name: 's1_beta.csv', role: 'timeseries', videoID: 's1', dataType: 'beta' },
];

function withStudy(page, w, include_network) {
  page.state.files = FILES.slice();
  page.state.network = true;
  page.applyOpenedConfig({
    videoIDs: ['s1'], dataTypes: { s1: ['alpha', 'beta'] }, include_network,
  });
  w.document.getElementById('t_network').checked = true;
  page.renderEffectors();
}

test('a grouped config survives being read and collected again', async () => {
  const { window: w, page } = boot();
  withStudy(page, w, { groups: [{ match: '^alpha', label: 'A', color: '#f00' }], band: [0.5, 8] });
  const out = page.collectNetwork();
  assert.deepStrictEqual(plain(out.groups), [{ match: '^alpha', label: 'A', color: '#f00' }]);
  assert.deepStrictEqual(plain(out.band), [0.5, 8]);
});

test('the figure layout is not dropped on the way back out', async () => {
  // The bug this suite exists for. `collectNetwork` rebuilt the object from the
  // controls, and there was no control for `layout`, so a study that chose the
  // figure layout lost it the next time anyone opened the wizard.
  const { window: w, page } = boot();
  withStudy(page, w, {
    groups: [{ match: '^teacher', label: 'Teacher' }],
    band: [0, 12], layout: 'figure',
  });
  assert.strictEqual(page.collectNetwork().layout, 'figure');
});

test('declared effectors round-trip, coordinates included', async () => {
  const { window: w, page } = boot();
  const original = {
    groups: [{ label: 'Teacher', color: '#e84393' }],
    effectors: [
      { series: 'alpha', group: 'Teacher', label: 'Right hand', part: 'righthand' },
      { series: 'beta', group: 'Teacher', label: 'Body', x: 0.72, y: 0.4 },
    ],
    layout: 'figure',
  };
  withStudy(page, w, original);
  const out = page.collectNetwork();

  assert.deepStrictEqual(plain(out.effectors), original.effectors,
    'x and y have no column in the table, so they have to be carried through');
  assert.strictEqual(out.layout, 'figure');
});

test('the table offers a row per measure and the groups defined above it', async () => {
  const { window: w, page } = boot();
  withStudy(page, w, { groups: [{ label: 'Teacher' }, { label: 'Student' }] });
  const rows = w.document.querySelectorAll('#network_effectors tr');
  assert.strictEqual(rows.length, 2, 'one row per data type');
  const options = [...w.document.querySelectorAll('[data-eff="group"][data-dt="alpha"] option')]
    .map((o) => o.value);
  assert.deepStrictEqual(plain(options), ['', 'Teacher', 'Student']);
});

test('a study that declares nothing still writes the old shape', async () => {
  // Back-compat: the table is opt-in, and an untouched one must not turn
  // `include_network: true` into an object full of empty entries.
  const { window: w, page } = boot();
  withStudy(page, w, true);
  assert.strictEqual(page.collectNetwork(), true);
});

test('editing a row is what puts an effector in the config', async () => {
  const { window: w, page } = boot();
  withStudy(page, w, { groups: [{ label: 'Teacher' }] });
  assert.strictEqual(page.collectNetwork().effectors, undefined);

  const select = w.document.querySelector('[data-eff="group"][data-dt="alpha"]');
  select.value = 'Teacher';
  select.dispatchEvent(new w.Event('change', { bubbles: true }));

  assert.deepStrictEqual(plain(page.collectNetwork().effectors),
    [{ series: 'alpha', group: 'Teacher' }]);
});
