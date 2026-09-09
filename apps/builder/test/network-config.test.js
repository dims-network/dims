// What the wizard does with an existing network config.
//
// The property under test is a round trip: read a config into the diagram, then
// collect it back, and get the same thing. It is the one assertion that catches
// a key the page cannot display -- which is what `layout` was, and what an
// effector's x/y still is.
const test = require('node:test');
const assert = require('node:assert');
const { boot } = require('./harness.js');

// Objects come back from the page's own realm, where Object.prototype is a
// different object, so deepStrictEqual refuses them on identity alone. What
// these tests are about is the data, so compare the data.
const plain = (v) => JSON.parse(JSON.stringify(v));

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
  w.document.getElementById('t_cw').checked = true;
  page.renderDiagram();
}

test('a config with people survives being read and collected again', async () => {
  const { window: w, page } = boot();
  withStudy(page, w, {
    groups: [{ label: 'Teacher', color: '#e84393' }],
    effectors: [{ series: 'alpha', group: 'Teacher', part: 'righthand' }],
    band: [0.5, 8],
  });
  const out = page.collectNetwork();
  assert.deepStrictEqual(plain(out.groups), [{ label: 'Teacher', color: '#e84393' }]);
  assert.deepStrictEqual(plain(out.band), [0.5, 8]);
});

test('the figure layout is implied by placing anything', async () => {
  // It used to be a <select> nobody set and collectNetwork silently dropped. A
  // body diagram that configured a column chart would be a lie, so placing a
  // node is what says "figure".
  const { window: w, page } = boot();
  withStudy(page, w, {
    groups: [{ label: 'Teacher' }],
    effectors: [{ series: 'alpha', group: 'Teacher', part: 'head' }],
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
  };
  withStudy(page, w, original);
  const out = page.collectNetwork();

  assert.deepStrictEqual(plain(out.effectors), original.effectors,
    'x and y have no handle on the diagram, so they have to be carried through');
});

test('a study that declares nothing still writes the old shape', async () => {
  // Back-compat: an untouched diagram must not turn `include_network: true`
  // into an object full of empty entries.
  const { window: w, page } = boot();
  withStudy(page, w, true);
  assert.strictEqual(page.collectNetwork(), true);
});

test('the toggle still decides whether anything is written at all', async () => {
  const { window: w, page } = boot();
  withStudy(page, w, { groups: [{ label: 'Teacher' }] });
  w.document.getElementById('t_network').checked = false;
  assert.strictEqual(page.collectNetwork(), false);
});
