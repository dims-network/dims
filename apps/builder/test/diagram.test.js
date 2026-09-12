// The network diagram: the wizard's way of saying which series is which node.
//
// It replaced a table of dropdowns whose meaning only became visible after the
// analyses had run. These tests are about the two things the table could not
// do -- put a measure on a named person's body part, and ask for the pair
// between two of them -- plus the one migration that has to be lossless.
const test = require('node:test');
const assert = require('node:assert');
const { boot } = require('./harness.js');

const plain = (v) => JSON.parse(JSON.stringify(v));

const KARNATAK_TYPES = [
  'teacher_lefthandspeed', 'teacher_righthandspeed', 'teacher_nosespeed',
  'student_lefthandspeed', 'student_righthandspeed', 'student_nosespeed',
];

function files(types) {
  return types.map((dt, i) => ({
    id: String(i), name: `s1_${dt}.csv`, role: 'timeseries', videoID: 's1', dataType: dt,
  }));
}

function withTypes(page, w, types, include_network) {
  page.state.files = files(types);
  page.state.network = true;
  page.applyOpenedConfig({
    videoIDs: ['s1'], dataTypes: { s1: types }, include_network,
  });
  w.document.getElementById('t_network').checked = true;
  w.document.getElementById('t_cw').checked = true;
  page.renderDiagram();
}

const spots = (w) => [...w.document.querySelectorAll('#network-diagram [data-spot]')];
const filled = (w) => spots(w).filter((g) => g.dataset.dt);
const edges = (w) => [...w.document.querySelectorAll('#network-diagram [data-edge]')];
const figures = (w) =>
  [...w.document.querySelectorAll('#network-diagram > g')].filter((g) => !g.dataset.spot);

// --- people ------------------------------------------------------------------

test('a person gets a figure, and six places to put something', async () => {
  const { window: w, page } = boot();
  withTypes(page, w, ['alpha'], true);
  assert.strictEqual(figures(w).length, 0, 'no people, no bodies');

  page.addPerson('Teacher', '#e84393');
  page.renderDiagram();
  assert.strictEqual(figures(w).length, 1);
  assert.strictEqual(spots(w).length, 6,
    'head, both hands, torso, hip, foot — the positions the tab actually draws');
});

test('removing a person takes their measures off the diagram', async () => {
  const { window: w, page } = boot();
  withTypes(page, w, ['alpha', 'beta'], true);
  const id = page.addPerson('Teacher');
  page.place('alpha', id, 'head');
  page.renderDiagram();
  assert.strictEqual(filled(w).length, 1);

  page.removePerson(id);
  page.renderDiagram();
  assert.strictEqual(filled(w).length, 0, 'a node outlived the body it was on');
  assert.deepStrictEqual(plain(page.unplacedTypes()), ['alpha', 'beta']);
});

// --- placing -----------------------------------------------------------------

test('a placed measure fills its spot and leaves the unplaced list', async () => {
  const { window: w, page } = boot();
  withTypes(page, w, ['alpha', 'beta'], true);
  const id = page.addPerson('Teacher');
  page.place('alpha', id, 'righthand');
  page.renderDiagram();

  const node = filled(w);
  assert.strictEqual(node.length, 1);
  assert.strictEqual(node[0].dataset.spot, 'righthand');
  assert.strictEqual(node[0].dataset.dt, 'alpha');
  assert.deepStrictEqual(plain(page.unplacedTypes()), ['beta']);
});

test('placing a measure somewhere new moves it rather than cloning it', async () => {
  const { window: w, page } = boot();
  withTypes(page, w, ['alpha'], true);
  const id = page.addPerson('Teacher');
  page.place('alpha', id, 'head');
  page.place('alpha', id, 'foot');
  page.renderDiagram();

  assert.strictEqual(filled(w).length, 1, 'one measure is one node');
  assert.strictEqual(filled(w)[0].dataset.spot, 'foot');
});

test('renaming a person carries their measures with them', async () => {
  // A rename that did not reach the measures would strand every node that
  // person was carrying. Asserted on the config rather than on the internal
  // field: an effector names its person by id now, so the label appears only
  // where the config format asks for one -- and that is the thing that has to
  // be right.
  const { window: w, page } = boot();
  withTypes(page, w, ['alpha'], true);
  const id = page.addPerson('Teacher');
  page.place('alpha', id, 'head');
  page.renderDiagram();

  const input = w.document.querySelector(`[data-person-label="${id}"]`);
  input.value = 'Tutor';
  input.dispatchEvent(new w.Event('input', { bubbles: true }));

  const out = page.collectNetwork();
  assert.deepStrictEqual(plain(out.groups).map((g) => g.label), ['Tutor']);
  assert.strictEqual(plain(out.effectors)[0].group, 'Tutor');
  assert.strictEqual(filled(w).length, 1, 'the node came off the diagram');
});

// --- linking -----------------------------------------------------------------

test('linking two nodes asks for the pair, and draws it', async () => {
  const { window: w, page } = boot();
  withTypes(page, w, ['alpha', 'beta'], true);
  const t = page.addPerson('Teacher');
  page.place('alpha', t, 'head');
  page.place('beta', t, 'righthand');
  page.state.cw.clear();
  page.renderDiagram();
  assert.strictEqual(edges(w).length, 0);

  page.toggleEdge('alpha', 'beta');
  page.renderDiagram();
  assert.strictEqual(edges(w).length, 1);
  assert.deepStrictEqual(plain(page.pairKeysToList(page.state.cw)), [['alpha', 'beta']]);

  page.toggleEdge('alpha', 'beta');
  page.renderDiagram();
  assert.strictEqual(edges(w).length, 0, 'clicking the same pair again removes it');
});

test('a line drawn from the second node to the first still counts', async () => {
  // state.cw keys are order-sensitive: pairKeysToList filters against
  // allPairs(), which emits them in allDataTypes() order, so an edge drawn
  // backwards is dropped in silence unless it is normalised.
  const { window: w, page } = boot();
  withTypes(page, w, ['alpha', 'beta'], true);
  const t = page.addPerson('Teacher');
  page.place('alpha', t, 'head');
  page.place('beta', t, 'righthand');
  page.state.cw.clear();

  page.toggleEdge('beta', 'alpha');           // backwards
  assert.deepStrictEqual(plain(page.pairKeysToList(page.state.cw)), [['alpha', 'beta']],
    'the pair was written in an order allPairs() never produces');
});

test('unplacing a measure takes its lines with it', async () => {
  const { window: w, page } = boot();
  withTypes(page, w, ['alpha', 'beta'], true);
  const t = page.addPerson('Teacher');
  page.place('alpha', t, 'head');
  page.place('beta', t, 'righthand');
  page.state.cw.clear();
  page.toggleEdge('alpha', 'beta');

  page.unplace('alpha');
  page.renderDiagram();
  assert.strictEqual(edges(w).length, 0, 'an edge survived one of its own endpoints');
  // The line goes because a line needs two placed endpoints. The analysis
  // stays: where a measure sat on a body is not whether to compute it, and
  // deleting the pair here cancelled work that may have been picked in the
  // chips, with nothing on screen saying so.
  assert.deepStrictEqual(plain(page.pairKeysToList(page.state.cw)), [['alpha', 'beta']],
    'taking a node off the diagram cancelled the analysis as well');
});

// --- the migration -----------------------------------------------------------

test("a study that says it all in its names opens with its nodes placed", async () => {
  // Every study that exists predates `effectors` and encodes person, part and
  // quantity in one string. Opening with an empty diagram would ask a
  // researcher to place six nodes they had already described.
  const { window: w, page } = boot();
  withTypes(page, w, KARNATAK_TYPES, {
    groups: [
      { label: 'Teacher', match: '^teacher', color: '#e84393' },
      { label: 'Student', match: '^student', color: '#00b894' },
    ],
    band: [0.0, 12.0],
    layout: 'figure',
  });

  assert.strictEqual(figures(w).length, 2);
  assert.strictEqual(filled(w).length, 6, 'all six measures should be on a body');
  assert.ok(page.state.placedByName, 'and the diagram should say they were guessed');

  const placed = page.state.effectors;
  assert.strictEqual(placed.teacher_righthandspeed.part, 'righthand');
  assert.strictEqual(placed.student_nosespeed.part, 'head', 'nose sits on head');
  // The label loses the group prefix, exactly as the tab's nodeLabel does.
  assert.strictEqual(placed.student_nosespeed.label, 'nosespeed');
  // Whose they are, read off the config rather than the internal field: the
  // guess has to survive the trip out, which is what the dashboard reads.
  const whose = {};
  plain(page.collectNetwork().effectors).forEach((e) => { whose[e.series] = e.group; });
  assert.strictEqual(whose.teacher_righthandspeed, 'Teacher');
  assert.strictEqual(whose.student_nosespeed, 'Student');
});

test('pressing Next on such a study writes the explicit form', async () => {
  const { window: w, page } = boot();
  withTypes(page, w, KARNATAK_TYPES, {
    groups: [
      { label: 'Teacher', match: '^teacher', color: '#e84393' },
      { label: 'Student', match: '^student', color: '#00b894' },
    ],
    band: [0.0, 12.0],
  });
  const out = plain(page.collectNetwork());

  assert.strictEqual(out.effectors.length, 6);
  assert.strictEqual(out.layout, 'figure');
  assert.deepStrictEqual(out.band, [0, 12]);
  // The regex is carried, not invented and not discarded: it is what the study
  // wrote, and dropping it would change how an older core reads the file.
  assert.strictEqual(out.groups[0].match, '^teacher');
  assert.strictEqual(out.groups[0].color, '#e84393');
});

test('a study with explicit effectors is not second-guessed', async () => {
  const { window: w, page } = boot();
  withTypes(page, w, KARNATAK_TYPES, {
    groups: [{ label: 'Teacher', match: '^teacher' }],
    effectors: [{ series: 'teacher_nosespeed', group: 'Teacher', part: 'foot' }],
  });
  assert.strictEqual(page.state.effectors.teacher_nosespeed.part, 'foot',
    'inference overrode a declaration');
  assert.ok(!page.state.placedByName);
  assert.strictEqual(filled(w).length, 1);
});

// --- the clicks themselves ---------------------------------------------------
//
// Everything above drives the model directly. These drive the DOM, because the
// delegated handlers are where a data- attribute typo hides.

function click(w, el) {
  el.dispatchEvent(new w.Event('click', { bubbles: true }));
}

test('clicking an empty spot offers the series that are still free', async () => {
  const { window: w, page } = boot();
  withTypes(page, w, ['alpha', 'beta'], true);
  page.addPerson('Teacher');
  page.renderDiagram();

  click(w, spots(w)[0].querySelector('circle'));
  const menu = w.document.getElementById('spot-menu');
  assert.ok(!menu.hidden, 'no menu opened');
  assert.deepStrictEqual(
    [...menu.querySelectorAll('[data-pick]')].map((b) => b.dataset.pick),
    ['alpha', 'beta']);

  click(w, menu.querySelector('[data-pick="beta"]'));
  assert.ok(menu.hidden, 'the menu stayed open after a pick');
  assert.strictEqual(filled(w).length, 1);
  assert.strictEqual(filled(w)[0].dataset.dt, 'beta');
});

test('clicking two placed nodes draws the line between them', async () => {
  const { window: w, page } = boot();
  withTypes(page, w, ['alpha', 'beta'], true);
  const t = page.addPerson('Teacher');
  page.place('alpha', t, 'head');
  page.place('beta', t, 'foot');
  page.state.cw.clear();
  page.renderDiagram();

  click(w, filled(w)[0].querySelector('circle'));
  assert.ok(page.state.armed, 'the first click should arm a node');
  click(w, filled(w).find((g) => g.dataset.dt !== page.state.armed).querySelector('circle'));

  assert.strictEqual(edges(w).length, 1);
  assert.strictEqual(page.state.armed, null, 'the second click should disarm');
});

test('clicking an armed node again cancels instead of self-linking', async () => {
  const { window: w, page } = boot();
  withTypes(page, w, ['alpha'], true);
  const t = page.addPerson('Teacher');
  page.place('alpha', t, 'head');
  page.state.cw.clear();
  page.renderDiagram();

  click(w, filled(w)[0].querySelector('circle'));
  click(w, filled(w)[0].querySelector('circle'));
  assert.strictEqual(page.state.armed, null);
  assert.strictEqual(edges(w).length, 0, 'a node was linked to itself');
});

test('the × takes a measure back off the diagram', async () => {
  const { window: w, page } = boot();
  withTypes(page, w, ['alpha'], true);
  const t = page.addPerson('Teacher');
  page.place('alpha', t, 'head');
  page.renderDiagram();

  click(w, filled(w)[0].querySelector('[data-clear] circle'));
  assert.strictEqual(filled(w).length, 0);
  assert.deepStrictEqual(plain(page.unplacedTypes()), ['alpha']);
});

test('adding a person from the button draws another figure', async () => {
  const { window: w, page } = boot();
  withTypes(page, w, ['alpha'], true);
  click(w, w.document.getElementById('add-person'));
  assert.strictEqual(figures(w).length, 1);
  click(w, w.document.getElementById('add-person'));
  assert.strictEqual(figures(w).length, 2);
});

// --- the migration is lossless -----------------------------------------------

// The tab's own grouping and layout, loaded headless. This test reaches across
// into packages/dims-tabs on purpose: the claim is precisely a cross-boundary
// one -- what the wizard writes has to render as what it read -- and neither
// side alone can make it.
function tabRenderer() {
  const fs = require('fs');
  const path = require('path');
  const { JSDOM } = require('jsdom');
  const src = fs.readFileSync(path.resolve(
    __dirname, '..', '..', '..', 'packages', 'dims-tabs', 'network.js'), 'utf8');
  const body = src.slice(src.indexOf('const SVG_NS'), src.indexOf('window.DIMS.extendHost'));
  const dom = new JSDOM('<!doctype html><body>', { runScripts: 'outside-only' });
  // The tab draws from the shared figure geometry, exactly as the page does:
  // index.html loads figure-geometry.js before the tabs.
  dom.window.eval(fs.readFileSync(path.resolve(
    __dirname, '..', '..', '..', 'packages', 'dims-tabs', 'figure-geometry.js'), 'utf8'));
  dom.window.eval(`${body}\n;window.__tab = { grouping, layout, measuresIn, drawsBody };`);
  return dom.window.__tab;
}

test('what the wizard writes renders exactly as what it read', async () => {
  // Karnatak's shape, inlined rather than read from the case repo: a test that
  // depends on a directory only one machine has is a test that passes
  // everywhere else having checked nothing.
  const inferred = {
    groups: [
      { label: 'Teacher', match: '^teacher', color: '#e84393' },
      { label: 'Student', match: '^student', color: '#00b894' },
    ],
    band: [0.0, 12.0],
    layout: 'figure',
  };
  const crosswavelet = [];
  for (let i = 0; i < KARNATAK_TYPES.length; i++) {
    for (let j = i + 1; j < KARNATAK_TYPES.length; j++) {
      crosswavelet.push([KARNATAK_TYPES[i], KARNATAK_TYPES[j]]);
    }
  }

  const { window: w, page } = boot();
  withTypes(page, w, KARNATAK_TYPES, inferred);
  const migrated = plain(page.collectNetwork());

  const tab = tabRenderer();
  const pairs = {};
  crosswavelet.forEach(([a, b]) => { pairs[`${a}_vs_${b}`] = { data_type1: a, data_type2: b }; });

  const draw = (net) => {
    const groups = tab.grouping({ include_network: net }, tab.measuresIn(pairs));
    const pos = tab.layout(groups, net.layout || 'columns');
    return Object.fromEntries(Object.entries(pos).map(([k, p]) =>
      [k, { x: Math.round(p.x), y: Math.round(p.y), label: p.label, group: p.group.label }]));
  };

  const before = draw(inferred);
  const after = draw(migrated);
  assert.strictEqual(Object.keys(before).length, 6);
  assert.deepStrictEqual(after, before,
    'opening a study in the wizard and pressing Next moved its nodes');
});

// --- one person is a whole network -------------------------------------------

test('one person with several effectors is a complete network', async () => {
  // Every study that exists is two people, and an issue was filed saying the
  // wizard assumed that. It does not: nothing anywhere requires a second
  // figure, and this is the test that says so rather than leaving it to be
  // rediscovered. What a single-body network *means* -- whether the 0.15
  // above-chance threshold, tuned between people, reads the same within one --
  // is a separate and empirical question.
  const { window: w, page } = boot();
  withTypes(page, w, ['hand_l', 'hand_r', 'head'], true);
  const p = page.addPerson('Player', '#5b8cff');
  page.place('hand_l', p, 'lefthand');
  page.place('hand_r', p, 'righthand');
  page.place('head', p, 'head');
  page.state.cw.clear();
  page.toggleEdge('hand_l', 'hand_r');
  page.toggleEdge('hand_l', 'head');
  page.toggleEdge('hand_r', 'head');
  page.renderDiagram();

  assert.strictEqual(figures(w).length, 1);
  assert.strictEqual(filled(w).length, 3);
  assert.strictEqual(edges(w).length, 3, 'all three within-body pairs should draw');

  const out = plain(page.collectNetwork());
  assert.strictEqual(out.groups.length, 1);
  assert.strictEqual(out.effectors.length, 3);
  assert.strictEqual(out.layout, 'figure');

  // And the tab centres the single figure rather than pushing it to one side.
  const tab = tabRenderer();
  const pairs = {};
  page.pairKeysToList(page.state.cw).forEach(([a, b]) => {
    pairs[`${a}_vs_${b}`] = { data_type1: a, data_type2: b };
  });
  const pos = tab.layout(tab.grouping({ include_network: out }, tab.measuresIn(pairs)), 'figure');
  assert.strictEqual(Math.round(pos.head.x), 500, 'the lone figure should be centred');
  assert.strictEqual(Object.keys(pos).length, 3);
});

// --- the gestures -------------------------------------------------------------
//
// Asking for a pair used to be click one node, click another, with nothing in
// between but a slightly thicker ring. The first click looked like it had done
// nothing, so the gesture read as broken and people concluded the diagram did
// not work. Dragging is the gesture the picture implies; both now draw a line
// that follows the pointer.

function pointer(w, el, type, at = {}) {
  const ev = new w.MouseEvent(type, { bubbles: true, cancelable: true,
                                      clientX: at.x || 0, clientY: at.y || 0 });
  el.dispatchEvent(ev);
  return ev;
}
const nodeFor = (w, dt) => w.document.querySelector(`#network-diagram [data-dt="${dt}"]`);
const rubber = (w) => w.document.getElementById('rubber-band');

test('dragging one node onto another asks for the pair', async () => {
  const { window: w, page } = boot();
  withTypes(page, w, ['alpha', 'beta'], true);
  const t = page.addPerson('Teacher');
  page.place('alpha', t, 'head');
  page.place('beta', t, 'righthand');
  page.state.cw.clear();
  page.renderDiagram();

  const from = nodeFor(w, 'alpha');
  pointer(w, from, 'pointerdown');
  pointer(w, from, 'pointermove', { x: 40, y: 40 });
  assert.ok(rubber(w), 'nothing followed the pointer, so the drag was invisible');

  pointer(w, nodeFor(w, 'beta'), 'pointerup');
  assert.deepStrictEqual(plain(page.pairKeysToList(page.state.cw)), [['alpha', 'beta']]);
  assert.strictEqual(rubber(w), null, 'the line stayed behind after the drop');
  assert.strictEqual(edges(w).length, 1);
});

test('a drag released on nothing asks for nothing', async () => {
  const { window: w, page } = boot();
  withTypes(page, w, ['alpha', 'beta'], true);
  const t = page.addPerson('Teacher');
  page.place('alpha', t, 'head');
  page.place('beta', t, 'righthand');
  page.state.cw.clear();
  page.renderDiagram();

  const from = nodeFor(w, 'alpha');
  pointer(w, from, 'pointerdown');
  pointer(w, from, 'pointermove', { x: 40, y: 40 });
  pointer(w, w.document.querySelector('#network-diagram'), 'pointerup');

  assert.strictEqual(page.pairKeysToList(page.state.cw).length, 0);
  assert.strictEqual(page.state.armed, null, 'the diagram was left half-linked');
  assert.strictEqual(rubber(w), null);
});

test('Escape abandons a half-made link', async () => {
  const { window: w, page } = boot();
  withTypes(page, w, ['alpha', 'beta'], true);
  const t = page.addPerson('Teacher');
  page.place('alpha', t, 'head');
  page.place('beta', t, 'righthand');
  page.state.cw.clear();
  page.renderDiagram();

  nodeFor(w, 'alpha').dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  assert.strictEqual(page.state.armed, 'alpha');

  w.document.dispatchEvent(new w.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  assert.strictEqual(page.state.armed, null);
  assert.strictEqual(page.pairKeysToList(page.state.cw).length, 0);
});

// --- the picker ---------------------------------------------------------------

test('the picker closes without picking anything', async () => {
  const { window: w, page } = boot();
  withTypes(page, w, ['alpha', 'beta'], true);
  const t = page.addPerson('Teacher');
  page.renderDiagram();

  const before = plain(page.state.effectors);
  const empty = [...w.document.querySelectorAll('#network-diagram [data-spot]')]
    .find((g) => !g.dataset.dt);
  empty.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  assert.strictEqual(w.document.getElementById('spot-menu').hidden, false,
    'clicking an empty spot did not offer anything to put there');

  pointer(w, w.document.body, 'pointerdown');
  assert.strictEqual(w.document.getElementById('spot-menu').hidden, true,
    'the menu could only be left by choosing something');
  assert.deepStrictEqual(plain(page.state.effectors), before,
    'dismissing it placed a measure anyway');
});

test('Escape closes the picker too', async () => {
  const { window: w, page } = boot();
  withTypes(page, w, ['alpha'], true);
  page.addPerson('Teacher');
  page.renderDiagram();

  w.document.querySelector('#network-diagram [data-spot="head"]')
   .dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  w.document.dispatchEvent(new w.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  assert.strictEqual(w.document.getElementById('spot-menu').hidden, true);
});

// --- labels -------------------------------------------------------------------

test('a placed node is labelled by where it was put, not by its full name', async () => {
  const { window: w, page } = boot();
  withTypes(page, w, ['personLeftLeftHandSpeed', 'personRightRightHandSpeed'], true);
  const a = page.addPerson('Left partner');
  page.place('personLeftLeftHandSpeed', a, 'lefthand');
  page.renderDiagram();

  assert.strictEqual(page.state.effectors.personLeftLeftHandSpeed.label, 'Left hand');
  const drawn = [...w.document.querySelectorAll('#network-diagram text')].map((t) => t.textContent);
  assert.ok(drawn.includes('Left hand'), `the node drew its data type: ${drawn}`);
  assert.ok(!drawn.includes('personLeftLeftHandSpeed'),
    'the full name is what overlaps its neighbour; it belongs in the tooltip');

  const eff = page.collectNetwork().effectors.find((e) => e.series === 'personLeftLeftHandSpeed');
  assert.strictEqual(eff.label, 'Left hand', 'the label did not reach the study');
  assert.strictEqual(eff.series, 'personLeftLeftHandSpeed', 'series must stay the real name');
});

// --- a measure nobody declared is not a person -------------------------------

// The bug these were written for. A study had three people; `rtpjSync` was
// placed on the third. The person was removed in the wizard, the study was
// rebuilt, and the network tab drew *three* figures: the two people plus a grey
// body with `rtpjSync` floating at its side. The measure was real -- the
// payload still carried pairs for it -- but the third person was not.
//
// The tab's rule is now that a body is drawn for a group only when something of
// that group sits on one, which `figureLayout` answers and `drawsBody` reports.

function undeclaredSetup() {
  // The shape of the study in the screenshot: two people with a head and a
  // right hand each, and one measure no effector mentions.
  const net = {
    groups: [{ label: 'Person 1', color: '#e84393' },
             { label: 'Person 2', color: '#00b894' }],
    effectors: [
      { series: 'p1_head', group: 'Person 1', label: 'Head', part: 'head' },
      { series: 'p1_hand', group: 'Person 1', label: 'Right hand', part: 'righthand' },
      { series: 'p2_head', group: 'Person 2', label: 'Head', part: 'head' },
      { series: 'p2_hand', group: 'Person 2', label: 'Right hand', part: 'righthand' },
    ],
    layout: 'figure',
  };
  const pairs = {};
  [['p1_head', 'p2_head'], ['p1_hand', 'p2_hand'],
   ['p1_head', 'rtpjSync'], ['p1_hand', 'rtpjSync']].forEach(([a, b]) => {
    pairs[`${a}_vs_${b}`] = { data_type1: a, data_type2: b };
  });
  const tab = tabRenderer();
  const groups = tab.grouping({ include_network: net }, tab.measuresIn(pairs));
  const pos = tab.layout(groups, 'figure');
  return { tab, groups, pos };
}

test('a measure no effector declared does not get a body of its own', async () => {
  const { tab, groups, pos } = undeclaredSetup();

  const other = groups.find((g) => g.members.includes('rtpjSync'));
  assert.ok(other, 'the undeclared measure was dropped, which is worse');
  assert.strictEqual(other.members.length, 1, 'only rtpjSync is undeclared');
  assert.strictEqual(tab.drawsBody(other), false,
    'the leftovers bucket was drawn as a person');

  const bodies = groups.filter((g) => tab.drawsBody(g)).map((g) => g.label);
  assert.deepStrictEqual(bodies, ['Person 1', 'Person 2'],
    'the picture drew a figure for somebody the study does not mention');

  // And it is still on the chart, with a position an edge can reach.
  assert.ok(Number.isFinite(pos.rtpjSync.x) && Number.isFinite(pos.rtpjSync.y));
});

test('an undeclared measure stays inside the picture', async () => {
  const { pos } = undeclaredSetup();
  const VIEW_W = 1000;   // network.js's own viewBox width

  // It used to be parked at its column's centre + 150, which for the third of
  // three groups is x = 900 -- hard against the edge, past the body it was
  // meant to sit beside, and clipped once its label was drawn.
  assert.ok(pos.rtpjSync.x > 0 && pos.rtpjSync.x < VIEW_W - 40,
    `rtpjSync sits at x=${pos.rtpjSync.x}, outside the drawable width`);
  assert.strictEqual(pos.rtpjSync.part, null);
  assert.strictEqual(pos.rtpjSync.x, pos.rtpjSync.group.cx,
    'a bodyless group is a column, so its members sit on its centre line');
});

test('a study that declares no groups is still one person', async () => {
  // The other direction, and the reason the rule asks the layout rather than
  // the group's label: with no groups declared, every measure falls into one
  // bucket -- and that bucket IS the person, body parts and all. Flagging the
  // trailing group as "leftovers" by name would have taken its body away.
  const pairs = {
    'a_vs_b': { data_type1: 'righthandspeed', data_type2: 'head_x' },
  };
  const tab = tabRenderer();
  const groups = tab.grouping({ include_network: true }, tab.measuresIn(pairs));
  const pos = tab.layout(groups, 'figure');

  assert.strictEqual(groups.length, 1);
  assert.strictEqual(tab.drawsBody(groups[0]), true,
    'the only group lost its body, so the figure layout drew nothing');
  assert.strictEqual(pos.righthandspeed.part, 'righthand');
});

test('a part-less measure on a real person stays beside that person', async () => {
  // A declared person with one measure the vocabulary cannot place keeps its
  // body -- the other measures are on it -- and the odd one out is stacked at
  // the side rather than dropped or sent to a column of its own.
  const net = {
    groups: [{ label: 'Player', color: '#5b8cff' }],
    effectors: [
      { series: 'head', group: 'Player', label: 'Head', part: 'head' },
      { series: 'breath', group: 'Player', label: 'Breathing', part: null },
    ],
    layout: 'figure',
  };
  const pairs = { 'a_vs_b': { data_type1: 'head', data_type2: 'breath' } };
  const tab = tabRenderer();
  const groups = tab.grouping({ include_network: net }, tab.measuresIn(pairs));
  const pos = tab.layout(groups, 'figure');

  assert.strictEqual(tab.drawsBody(groups[0]), true);
  assert.ok(pos.breath.x > pos.head.x, 'the stray belongs beside its figure');
  assert.ok(pos.breath.x < 1000 - 40, 'and inside the picture');
});

// --- two people, one name ----------------------------------------------------
//
// Reported after the phantom-person bug, from the same flow. `addPerson` named
// by `people.length + 1`, and `state.effectors[dt].group` held the *label*, so:
// remove Person 2 of three, add another, and the study has two people called
// "Person 3" whose measures are indistinguishable. Placing on one drew on the
// other, removing either stripped both, and the config carried two groups with
// one name for the dashboard to collapse.
//
// A person is identified by `id` now. A label is a display name, and the only
// place it identifies anything is the config format -- which is why a
// duplicate is refused on the way out rather than tolerated.

test('the person added after a removal does not take a name already in use', async () => {
  const { window: w, page } = boot();
  withTypes(page, w, ['s_a', 's_b', 's_c'], true);

  page.addPerson(); const p2 = page.addPerson(); page.addPerson();
  assert.deepStrictEqual(plain(page.state.people.map((p) => p.label)),
    ['Person 1', 'Person 2', 'Person 3']);

  page.removePerson(p2);
  page.addPerson();

  const labels = plain(page.state.people.map((p) => p.label));
  assert.strictEqual(new Set(labels).size, labels.length,
    `two people share a label: ${labels.join(', ')}`);
  // The gap is reused, so removing Person 2 and adding one gives a Person 2
  // back rather than a second Person 3.
  assert.deepStrictEqual(labels, ['Person 1', 'Person 3', 'Person 2']);
});

test('removing one namesake leaves the other one their measures', async () => {
  // The destructive half. `removePerson` matched on the label, so removing
  // either of two people called "Person 3" unplaced both of their measures.
  const { window: w, page } = boot();
  withTypes(page, w, ['s_a', 's_b'], true);

  const a = page.addPerson('Twin');
  const b = page.addPerson('Twin');       // typed by hand; the defaults cannot
  page.place('s_a', a, 'head');
  page.place('s_b', b, 'head');

  page.removePerson(b);

  assert.deepStrictEqual(plain(Object.keys(page.state.effectors)), ['s_a'],
    'removing one person took the other one\'s measure with it');
  assert.strictEqual(page.unplacedTypes().includes('s_a'), false,
    'the surviving measure came off the diagram');
});

test('two measures on two namesakes stay on their own figures', async () => {
  // The other half: `placedPositions` matched on the label too, so both
  // measures resolved onto whichever namesake came last and one node was
  // drawn on top of the other.
  const { window: w, page } = boot();
  withTypes(page, w, ['s_a', 's_b'], true);

  const a = page.addPerson('Twin');
  const b = page.addPerson('Twin');
  page.place('s_a', a, 'head');
  page.place('s_b', b, 'head');
  page.renderDiagram();

  const pos = page.placedPositions();
  assert.strictEqual(pos.s_a.person.id, a);
  assert.strictEqual(pos.s_b.person.id, b);
  assert.notStrictEqual(pos.s_a.x, pos.s_b.x,
    'both measures were placed on the same figure');
  assert.strictEqual(filled(w).length, 2, 'one node was drawn over the other');
});

test('a duplicate label is refused rather than written', async () => {
  // The config names a measure's group by label and the dashboard looks one up
  // by it, so a study with two "Twin" groups loses one of them and its
  // measures. Refused with the name in the message; nothing is renamed on the
  // researcher's behalf.
  const { window: w, page } = boot();
  withTypes(page, w, ['s_a', 's_b'], true);
  const a = page.addPerson('Twin');
  page.addPerson('Twin');
  page.place('s_a', a, 'head');
  page.toggleEdge('s_a', 's_b');

  assert.deepStrictEqual(plain(page.duplicatePersonLabels()), ['Twin']);

  w.document.getElementById('next-4').click();
  await new Promise((r) => setTimeout(r, 10));

  const msg = w.document.querySelector('#msg-4, [id^="msg-4"]');
  assert.ok(msg && /Twin/.test(msg.textContent),
    `expected the message to name the duplicate, got: ${msg && msg.textContent}`);
});

test('renaming a person is not renaming everyone who shared their name', async () => {
  // The rename handler rewrote every effector whose group matched the old
  // label, which reached the namesake's measures as well.
  const { window: w, page } = boot();
  withTypes(page, w, ['s_a', 's_b'], true);
  const a = page.addPerson('Twin');
  const b = page.addPerson('Twin');
  page.place('s_a', a, 'head');
  page.place('s_b', b, 'head');
  page.renderDiagram();

  const input = w.document.querySelector(`[data-person-label="${a}"]`);
  input.value = 'First';
  input.dispatchEvent(new w.Event('input', { bubbles: true }));

  assert.deepStrictEqual(plain(page.state.people.map((p) => p.label)), ['First', 'Twin']);
  const whose = {};
  plain(page.collectNetwork().effectors).forEach((e) => { whose[e.series] = e.group; });
  assert.deepStrictEqual(whose, { s_a: 'First', s_b: 'Twin' });
});

test('a group naming nobody in the study is still carried through', async () => {
  // The dashboard draws such a node in a trailing `Other` on purpose, and the
  // wizard must not quietly drop what somebody wrote. It is not "placed",
  // though: there is no figure of that name to draw it on.
  const { window: w, page } = boot();
  withTypes(page, w, ['alpha'], {
    groups: [{ label: 'Teacher' }],
    effectors: [{ series: 'alpha', group: 'Persn 1', part: 'head' }],
  });

  assert.ok(page.unplacedTypes().includes('alpha'),
    'a measure on a figure that does not exist cannot be placed');
  assert.strictEqual(plain(page.collectNetwork().effectors)[0].group, 'Persn 1');
});

test('the person added after a removal does not take a colour in use either', async () => {
  // Not destructive -- nothing is identified by colour -- but the diagram's
  // whole job is telling two bodies apart, and `people.length` picked the
  // colour of the person after the removed one.
  const { window: w, page } = boot();
  withTypes(page, w, ['s_a'], true);

  page.addPerson(); const p2 = page.addPerson(); page.addPerson();
  page.removePerson(p2);
  page.addPerson();

  const colours = plain(page.state.people.map((p) => p.color));
  assert.strictEqual(new Set(colours).size, colours.length,
    `two figures are drawn the same colour: ${colours.join(', ')}`);
});
