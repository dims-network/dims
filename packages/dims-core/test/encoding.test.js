// The browser half of the payload encoding, against vectors the Python half
// produced.
//
// A decoder tested against fixtures written by the same language agrees with
// itself. `fixtures/encodings.json` is packed by `common/arrays.py`, so these
// check the two implementations against each other -- which is the only thing
// worth checking, because a disagreement here is a dashboard drawing the wrong
// picture with nothing in the log.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const { makeEnv } = require('./harness.js');

const CASES = JSON.parse(
  fs.readFileSync(path.join(__dirname, 'fixtures', 'encodings.json'), 'utf8'));

// The decoder builds its arrays inside the JSDOM realm, whose Array has a
// different prototype, and deepStrictEqual compares prototypes. Compare the
// values, which is what is actually being asserted.
const plain = (v) => JSON.parse(JSON.stringify(v === undefined ? null : v));

function core() {
  const env = makeEnv({
    config: { videoIDs: ['s1'], dataTypes: { s1: ['a'] }, defaultWindowSize: 5 },
    files: {},
    scripts: ['packages/dims-core/dims-core.js'],
  });
  return env.window.DIMS;
}

test('every packed vector decodes to what Python packed', () => {
  const DIMS = core();
  CASES.forEach((c, i) => {
    const got = plain(DIMS.decodeArray(c.packed));
    assert.deepStrictEqual(got, c.expected,
      `case ${i} (${c.kind}, ${JSON.stringify(c.packed.shape || [c.packed.rows, c.packed.cols])}) ` +
      `decoded to something else`);
  });
});

test('a row whose width is not a multiple of eight keeps no padding bits', () => {
  // 13 and 129 columns both end mid-byte. Reading the padding back as
  // recurrent cells would inflate every rate on the plot and look plausible.
  const DIMS = core();
  const odd = CASES.filter(c => c.kind === 'bitmap' && c.packed.cols % 8 !== 0);
  assert.ok(odd.length >= 2, 'the fixtures must include awkward widths');
  for (const c of odd) {
    const got = plain(DIMS.decodeArray(c.packed));
    assert.strictEqual(got[0].length, c.packed.cols);
    assert.deepStrictEqual(got, c.expected);
  }
});

test('an undefined cell becomes null, which is what Plotly draws as a gap', () => {
  const DIMS = core();
  const withGaps = CASES.find(c => JSON.stringify(c.expected).includes('null'));
  assert.ok(withGaps, 'no fixture carries a NaN');
  const got = DIMS.decodeArray(withGaps.packed);
  assert.ok(JSON.stringify(got).includes('null'));
  assert.ok(!JSON.stringify(got).includes('NaN'));
});

test('anything that is not an encoded array passes through untouched', () => {
  // So a tab can call decodeArray on a field without knowing whether it grew
  // large enough to be encoded.
  const DIMS = core();
  for (const v of [[1, 2, 3], null, undefined, 7, 'text', { a: 1 }]) {
    assert.deepStrictEqual(plain(DIMS.decodeArray(v)), plain(v));
  }
});

test('an encoding this build does not know is refused by name', () => {
  // The whole reason the encoding names itself. Silence here is how a study
  // built by a newer core draws an empty panel with nothing in the console.
  const DIMS = core();
  assert.throws(
    () => DIMS.decodeArray({ encoding: 'bitmap-b128', rows: 1, cols: 1, data: 'AA==' }),
    /bitmap-b128[\s\S]*newer core/);
});

test('truncated data is caught rather than drawn short', () => {
  const DIMS = core();
  assert.throws(
    () => DIMS.decodeArray({ encoding: 'bitmap-b64', rows: 9, cols: 8, data: 'AAAA' }),
    /needs 9 bytes/);
  assert.throws(
    () => DIMS.decodeArray({ encoding: 'f32-b64', shape: [4], data: 'AAAA' }),
    /needs 16 bytes/);
});
