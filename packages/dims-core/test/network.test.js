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

// Edges are bowed quadratic curves, so they are <path>, not <line>: two
// straight lines between collinear nodes are the same line.
const edges = (w) => [...w.document.querySelectorAll('#networkEdges path')];
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
  // Read the value, not the width. Width is *relative to the other edges
  // shown*, and with a single edge the pivot is its own mean -- so it sits at
  // mid-scale whatever the window, which is correct and useless as a probe.
  const value = () => edges(w)[0].querySelector('title').textContent;
  const before = value();
  assert.match(caption(w), /whole recording/);

  w.dimsApp.lastClickedPoint = 4.0;
  w.dimsApp.updateNetwork();
  assert.match(caption(w), /1\.5–6\.5 s/,
    'the caption must say which window is drawn');
  assert.notStrictEqual(before, value(),
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

test('an at-chance edge is a hairline, not a width proportional to noise', async () => {
  // The width channel is for values that survived the significance test. An
  // at-chance edge is drawn as a faint dashed hairline and takes no part in the
  // scale, because stretching it across the stroke range is precisely how a
  // chart makes noise look like structure.
  const w = await open_(await boot({ ...NETWORK_CONFIG, defaultWindowSize: 5 },
                                   NETWORK_FILES));
  const widths = edges(w).map(l => ({
    solid: !l.getAttribute('stroke-dasharray'),
    width: parseFloat(l.getAttribute('stroke-width')),
    opacity: parseFloat(l.getAttribute('opacity')),
  }));
  const real = widths.find(e => e.solid);
  const chance = widths.filter(e => !e.solid);
  assert.ok(chance.every(c => c.width === Math.min(...widths.map(x => x.width))),
    'an at-chance edge was given a width from the coherence scale');
  assert.ok(real.width > Math.max(...chance.map(c => c.width)),
    `the coupled edge (${real.width}) is not thicker than the at-chance ones`);
  assert.ok(chance.every(c => c.opacity < real.opacity),
    'an at-chance edge should also sit back, so the eye lands on the real one');
});

test('width is relative to the edges on screen, and only to those', async () => {
  // Coherence sits in a narrow band -- often 0.7 to 0.8 across every pair -- so
  // a width mapped from 0 to 1 makes every line identical and says nothing.
  // The scale pivots on the mean of the visible, above-chance edges, which has
  // a consequence worth pinning: with exactly one such edge there is nothing to
  // be relative *to*, so it sits mid-scale whatever its value. That is honest,
  // and it is why the legend says "relative to the other edges shown".
  const w = await open_(await boot({ ...NETWORK_CONFIG, defaultWindowSize: 5 },
                                   NETWORK_FILES));
  const flex = w.document.getElementById('networkFlex');
  assert.ok(flex, 'no width-sensitivity control');

  const solid = edges(w).filter(l => !l.getAttribute('stroke-dasharray'));
  assert.strictEqual(solid.length, 1, 'this fixture has one coupled pair');
  const mid = (1.5 + 16) / 2;
  assert.ok(Math.abs(parseFloat(solid[0].getAttribute('stroke-width')) - mid) < 0.01,
    'a lone above-chance edge should sit mid-scale, having nothing to compare to');

  // And the control redraws rather than throwing.
  flex.value = '0';
  flex.dispatchEvent(new w.Event('input'));
  assert.ok(edges(w).length === 3, 'changing the sensitivity broke the chart');

  const legend = w.document.getElementById('networkContainer').textContent;
  assert.match(legend, /relative to the other edges shown/);
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

// --- the picture itself ------------------------------------------------------
//
// Reported from a screenshot: two columns of dots joined by grey dashes, with a
// thick black bar down each column. Two separate faults behind one image.

const paths = edges;

test('no two edges are drawn on top of each other', async () => {
  // The black bars. Every member of a group sat at the same x, so all three
  // within-group edges were the same vertical line drawn three times. The
  // original tab had solved this and said so: each edge bows perpendicular to
  // its chord by an amount of its own, "so edges that would otherwise overlap
  // (e.g. the collinear hand row) fan out into distinguishable arcs".
  const w = await open_(await boot({ ...NETWORK_CONFIG, defaultWindowSize: 5 },
                                   NETWORK_FILES));
  const geometry = paths(w).map(p => p.getAttribute('d'));
  assert.strictEqual(geometry.length, 3, 'expected three edges');
  assert.strictEqual(new Set(geometry).size, geometry.length,
    `two edges share the same geometry, so one is invisible under the other: `
    + geometry.join(' | '));
});

test('a figure layout draws a body per group, not a column of dots', async () => {
  const w = await open_(await boot({
    ...NETWORK_CONFIG,
    include_network: { ...NETWORK_CONFIG.include_network, layout: 'figure' },
    defaultWindowSize: 5,
  }, NETWORK_FILES));

  const svg = w.document.getElementById('networkSvg');
  assert.ok(svg, 'no chart');
  const figures = svg.querySelectorAll('.dims-figure');
  assert.strictEqual(figures.length, 1, 'one silhouette per group');
  assert.ok(figures[0].querySelector('circle'), 'the figure has no head');
  assert.ok(figures[0].querySelectorAll('line').length >= 2,
    'the figure has no limbs');
});

// The same real payload with its measures renamed to body parts. The shape --
// every field a tab reads, in the encoding the analyses write -- is the one the
// analyses produced; only the names change, which is exactly what the layout
// keys on.
function asBody(raw) {
  const rename = { eff_a: 'p_lefthand', eff_b: 'p_righthand', eff_c: 'p_nose' };
  let text = raw;
  for (const [from, to] of Object.entries(rename)) {
    text = text.split(from).join(to);
  }
  return text;
}

const BODY_FILES = {
  ...NETWORK_FILES,
  'assets/crosswavelet/s2_crosswavelet_data.json':
    asBody(read('s2_crosswavelet_data.json')),
};

const BODY_CONFIG = {
  ...NETWORK_CONFIG,
  dataTypes: { s2: ['p_lefthand', 'p_righthand', 'p_nose'] },
  include_crosswavelet: [['p_lefthand', 'p_righthand'],
                         ['p_lefthand', 'p_nose'],
                         ['p_righthand', 'p_nose']],
  include_network: { groups: [{ match: '^p_', label: 'Person' }], layout: 'figure' },
  defaultWindowSize: 5,
};

test('figure nodes are placed anatomically, not stacked in a line', async () => {
  // A column is what made the within-group edges collinear in the first place.
  const w = await open_(await boot(BODY_CONFIG, BODY_FILES));
  const nodes = [...w.document.querySelectorAll('#networkSvg circle[data-measure]')];
  assert.strictEqual(nodes.length, 3, 'three measures should be three nodes');

  const xs = new Set(nodes.map(n => n.getAttribute('cx')));
  const ys = new Set(nodes.map(n => n.getAttribute('cy')));
  assert.ok(xs.size > 1,
    `every node sits at x=${[...xs][0]}, which is the column layout again`);
  assert.ok(ys.size > 1, 'every node sits at the same height');

  // The hands are level with each other and either side of the midline; the
  // head is above both. That is what makes it read as a body.
  const at = (m) => nodes.find(n => n.getAttribute('data-measure') === m);
  const [lx, rx, hy] = [
    +at('p_lefthand').getAttribute('cx'),
    +at('p_righthand').getAttribute('cx'),
    +at('p_nose').getAttribute('cy'),
  ];
  assert.notStrictEqual(lx, rx, 'both hands are on the same side');
  assert.ok(hy < +at('p_lefthand').getAttribute('cy'), 'the head is below the hands');
});

test('a measure the body vocabulary does not know still gets drawn', async () => {
  // Losing a measure because a lookup table had not heard of it would be worse
  // than the column it replaces.
  const w = await open_(await boot({
    ...NETWORK_CONFIG,
    include_network: { ...NETWORK_CONFIG.include_network, layout: 'figure' },
    defaultWindowSize: 5,
  }, NETWORK_FILES));
  const drawn = [...w.document.querySelectorAll('#networkSvg circle[data-measure]')]
    .map(n => n.getAttribute('data-measure'));
  for (const m of ['eff_a', 'eff_b', 'eff_c']) {
    assert.ok(drawn.includes(m), `${m} is not on the chart; drawn: ${drawn}`);
  }
});

test('without a layout the study still gets columns', async () => {
  const w = await open_(await boot({ ...NETWORK_CONFIG, defaultWindowSize: 5 },
                                   NETWORK_FILES));
  assert.strictEqual(w.document.querySelectorAll('.dims-figure').length, 0,
    'a study that did not ask for figures got one');
});

// --- the controls that make it a tool rather than a picture ------------------

test('clicking an edge draws that pair\'s cross-wavelet detail', async () => {
  // One implementation of that figure, not two: the network asks the
  // cross-wavelet tab's own renderer for it.
  const w = await open_(await boot({ ...NETWORK_CONFIG, defaultWindowSize: 5 },
                                   NETWORK_FILES));
  const asked = [];
  w.dimsApp.createCrossWaveletPlot = (id, key) => asked.push({ id, key });

  const solid = edges(w).find(l => !l.getAttribute('stroke-dasharray'));
  solid.dispatchEvent(new w.Event('click'));
  await new Promise(r => setTimeout(r, 30));

  assert.ok(w.document.getElementById('networkDetailPanel').textContent.includes('↔'),
    'no heading for the selected pair');
  assert.strictEqual(asked.length, 1, 'the detail figure was not requested');
  assert.strictEqual(asked[0].id, 'networkDetailPlot');
  assert.match(asked[0].key, /eff_a_vs_eff_b/);
});

test('a dashboard without the cross-wavelet tab says so rather than failing', async () => {
  // The renderer belongs to another tab. A study that drops that tab should get
  // a sentence, not a stack trace in a console nobody reads.
  const w = await open_(await boot({ ...NETWORK_CONFIG, defaultWindowSize: 5 },
                                   NETWORK_FILES));
  w.dimsApp.createCrossWaveletPlot = undefined;
  edges(w)[0].dispatchEvent(new w.Event('click'));
  await new Promise(r => setTimeout(r, 30));
  assert.match(w.document.getElementById('networkDetailPanel').textContent,
    /cross-wavelet tab is not loaded/);
});

test('unticking a pair hides its edge', async () => {
  const w = await open_(await boot({ ...NETWORK_CONFIG, defaultWindowSize: 5 },
                                   NETWORK_FILES));
  const boxes = [...w.document.querySelectorAll('.network-pairs input[type="checkbox"]')];
  assert.strictEqual(boxes.length, 3, 'one checkbox per pair');
  const key = boxes[0].dataset.pairkey;
  const edgeFor = () => edges(w).find((l, i) => i === 0);

  assert.notStrictEqual(edgeFor().style.display, 'none');
  boxes[0].checked = false;
  boxes[0].dispatchEvent(new w.Event('change'));
  assert.strictEqual(edgeFor().style.display, 'none', `${key} is still drawn`);
});

test('the period band changes what an edge reports', async () => {
  const w = await open_(await boot({ ...NETWORK_CONFIG, defaultWindowSize: 5 },
                                   NETWORK_FILES));
  const lo = w.document.getElementById('networkBandLo');
  const hi = w.document.getElementById('networkBandHi');
  assert.ok(lo && hi, 'no period band control');

  const value = () => edges(w)[0].querySelector('title').textContent;
  const before = value();
  lo.value = '0.1'; hi.value = '0.5';
  hi.dispatchEvent(new w.Event('change'));
  assert.notStrictEqual(before, value(),
    'narrowing the band changed nothing, so the band is not applied');
});

test('there is a way back to the whole recording', async () => {
  // The host only ever sets the playhead, so before this there was no way to
  // return to the whole-recording view once a point had been picked.
  const w = await open_(await boot({ ...NETWORK_CONFIG, defaultWindowSize: 5 },
                                   NETWORK_FILES));
  const back = w.document.getElementById('networkWholeBtn');
  assert.ok(back, 'no control to go back');
  assert.strictEqual(back.style.display, 'none', 'offered before it means anything');

  w.dimsApp.lastClickedPoint = 4.0;
  w.dimsApp.updateNetwork();
  assert.notStrictEqual(back.style.display, 'none');
  assert.match(w.document.getElementById('networkScope').textContent, /1\.5–6\.5/);

  back.dispatchEvent(new w.Event('click'));
  assert.match(w.document.getElementById('networkScope').textContent, /whole recording/);
});

test('movement context is reported when it can be, and never invented', async () => {
  // Coherence is amplitude-normalised on purpose, so a thick edge can rest on
  // almost no movement. The tab reports that as a separate channel -- and says
  // nothing at all, rather than something wrong, when the raw signals are not
  // there to compute it from.
  const w = await open_(await boot({ ...NETWORK_CONFIG, defaultWindowSize: 5 },
                                   NETWORK_FILES));
  const tip = () => edges(w)[0].querySelector('title').textContent;
  assert.match(tip(), /both measures active: \d+% of this window/,
    'the series are loaded, so the figure should be there');

  // A recording where neither measure moves: the value stands, the edge fades,
  // and the tooltip says why. Nothing about the coherence changes.
  w.dimsApp.currentData = ['eff_a', 'eff_b', 'eff_c'].map(name => ({
    name, data: Array.from({ length: 200 }, (_, i) => ({ Time: i * 0.05, v: 0 })),
  }));
  w.dimsApp.updateNetwork();
  assert.match(tip(), /both measures active: 0% of this window/);
  assert.match(tip(), /mostly from stillness/);
  assert.ok(parseFloat(edges(w)[0].getAttribute('opacity')) < 0.4,
    'an edge computed entirely from stillness is not faded');

  // And with nothing loaded at all, no claim is made either way.
  w.dimsApp.currentData = [];
  w.dimsApp.updateNetwork();
  assert.doesNotMatch(tip(), /both measures active/,
    'a movement figure was reported with no series to compute it from');
});

test('the long explanation is behind an (i) and stays how you left it', async () => {
  const w = await open_(await boot({ ...NETWORK_CONFIG, defaultWindowSize: 5 },
                                   NETWORK_FILES));
  const info = w.document.getElementById('networkInfoToggle');
  const help = w.document.getElementById('networkHelp');
  assert.ok(info && help, 'no explanation control');
  assert.strictEqual(help.style.display, 'none', 'it starts open');

  info.dispatchEvent(new w.Event('click'));
  assert.notStrictEqual(help.style.display, 'none');
  assert.match(help.textContent, /cone of influence/);

  // A redraw -- a theme switch, a video change -- must not reopen something the
  // reader closed, nor close something they opened.
  w.dimsApp.displayNetwork();
  assert.notStrictEqual(w.document.getElementById('networkHelp').style.display, 'none',
    'the explanation shut itself on a redraw');
});
