// Cross-wavelet used to have no controls of its own: the pairs were whatever
// lines were on the network diagram, and switching the analysis on seeded the
// set with *every* pair. Ten measures make 45 of them, each one of the slowest
// analysis in the pipeline, all queued before the user had chosen anything.
//
// It now has chips of its own, starts empty, and the diagram is a second view
// of the same set rather than the only way in.
const test = require('node:test');
const assert = require('node:assert');
const { boot } = require('./harness.js');

const TYPES = ['alpha', 'beta', 'gamma', 'delta'];

function withTypes(page, w) {
  page.state.files = TYPES.map((dt, i) => ({
    id: String(i), name: `s1_${dt}.csv`, role: 'timeseries', videoID: 's1', dataType: dt,
  }));
  page.applyOpenedConfig({ videoIDs: ['s1'], dataTypes: { s1: TYPES } });
  return w.document.getElementById('t_cw');
}

const chips = (w) => [...w.document.querySelectorAll('#cw_types .chip')];
const on = (w) => chips(w).filter((c) => c.classList.contains('on')).map((c) => c.textContent);

test('switching cross-wavelet on selects nothing', async () => {
  const { window: w, page } = boot();
  const toggle = withTypes(page, w);

  toggle.checked = true;
  page.syncAnalysisDefaults();
  page.renderAnalysisTypes();

  assert.strictEqual(page.allPairs().length, 6, 'four measures make six pairs');
  assert.strictEqual(chips(w).length, 6, 'one chip per pair');
  assert.deepStrictEqual(on(w), [], 'the expensive analysis chose its own workload');
  assert.strictEqual(page.pairKeysToList(page.state.cw).length, 0);
});

test('switching it off clears what was picked', async () => {
  const { window: w, page } = boot();
  const toggle = withTypes(page, w);
  toggle.checked = true;
  page.state.cw.add(page.pairKey('alpha', 'beta'));

  toggle.checked = false;
  page.syncAnalysisDefaults();
  assert.strictEqual(page.pairKeysToList(page.state.cw).length, 0);
});

test('a chip and a line are two views of one list', async () => {
  const { window: w, page } = boot();
  const toggle = withTypes(page, w);
  toggle.checked = true;
  page.syncAnalysisDefaults();
  page.renderAnalysisTypes();

  // Picked on the diagram, shown in the chips.
  page.toggleEdge('alpha', 'beta');
  assert.deepStrictEqual(on(w), ['alpha × beta']);

  // Picked in the chips, and it is the same set the diagram draws from.
  chips(w).find((c) => c.textContent === 'gamma × delta').dispatchEvent(
    new w.MouseEvent('click', { bubbles: true }));
  assert.deepStrictEqual(plainPairs(page), [['alpha', 'beta'], ['gamma', 'delta']]);

  // And taken off again from either side.
  page.toggleEdge('alpha', 'beta');
  assert.deepStrictEqual(plainPairs(page), [['gamma', 'delta']]);
});

function plainPairs(page) {
  return JSON.parse(JSON.stringify(page.pairKeysToList(page.state.cw)));
}

// The bug this file's sibling behaviour was hiding: a study reopened from disk
// lists its measures alphabetically, whatever order its config was written in.
// `applyOpenedConfig` joined each stored pair verbatim into a key, so a pair
// written the other way round became a key nothing else in the wizard
// generates. It rendered unselected, drew no line, and was written back out as
// nothing at all — and a network built on it reported, in the dashboard, that
// no cross-wavelet output existed for the recording.
test('a pair written the other way round survives reopening', async () => {
  const { window: w, page } = boot();
  withTypes(page, w);

  page.applyOpenedConfig({
    videoIDs: ['s1'], dataTypes: { s1: TYPES },
    // 'delta' precedes 'alpha' here and follows it in the type order.
    include_crosswavelet: [['delta', 'alpha']],
    include_cRQA: [['gamma', 'beta']],
  });
  page.renderAnalysisTypes();

  assert.deepStrictEqual(plainPairs(page), [['alpha', 'delta']],
    'the pair was dropped because of the order its key was in');
  assert.deepStrictEqual(on(w), ['alpha × delta'], 'and the chip showed it unselected');
  assert.strictEqual(w.document.getElementById('t_cw').checked, true);
  assert.deepStrictEqual(
    JSON.parse(JSON.stringify(page.pairKeysToList(page.state.crqa))), [['beta', 'gamma']],
    'cross-recurrence had the same line and the same bug');
});

test('a pair whose measure is gone is dropped, and that one is right', async () => {
  const { window: w, page } = boot();
  withTypes(page, w);
  page.applyOpenedConfig({
    videoIDs: ['s1'], dataTypes: { s1: TYPES },
    include_crosswavelet: [['alpha', 'beta'], ['alpha', 'vanished']],
  });
  assert.deepStrictEqual(plainPairs(page), [['alpha', 'beta']]);
});
