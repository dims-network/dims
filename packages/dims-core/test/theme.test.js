// Themes come with the core, so every study inherits them by vendoring it.
// DIMS_Dashboard and Ortho never had them: they carried an older stylesheet and
// no theme machinery at all, which is the kind of divergence that a single
// vendored core is meant to end.
const test = require('node:test');
const assert = require('node:assert');
const { makeEnv } = require('./harness.js');

const SCRIPTS = [
  'packages/dims-core/video-component.js',
  'packages/dims-core/dims-core.js',
  'packages/dims-tabs/timeseries.js',
  'packages/dims-tabs/rqa.js',
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

const CFG = { videoIDs: ['s1'], dataTypes: { s1: ['a'] }, include_RQA: ['a'], defaultWindowSize: 5 };

test('the core offers more than one theme', async () => {
  const w = await boot(CFG);
  const sel = w.document.getElementById('themeSelect');
  assert.ok(sel, 'the theme control should exist');
  assert.ok(sel.options.length >= 2, `only ${sel.options.length} theme(s) offered`);
});

test('choosing a theme sets it on the document', async () => {
  const w = await boot(CFG);
  w.dimsApp.applyTheme('midnight', false);
  assert.strictEqual(w.document.documentElement.dataset.theme, 'midnight');
  w.dimsApp.applyTheme('aurora', false);
  assert.strictEqual(w.document.documentElement.dataset.theme, 'aurora');
});

test('the choice survives a reload', async () => {
  const w = await boot(CFG);
  w.dimsApp.applyTheme('midnight', false);
  assert.strictEqual(w.localStorage.getItem('dims-theme'), 'midnight',
    'the theme should be remembered per viewer');
});

// Which case repositories to check, as a colon-separated list of paths:
//
//     DIMS_CASE_REPOS=../../case-demo:../../case-ortho node --test
//
// This used to be two absolute paths into one contributor's home directory,
// guarded by `if (!fs.existsSync(c)) continue`. On every other machine, and on
// CI, the loop body never ran and the test reported success having asserted
// nothing -- the same failure ci.yml guards pyrqa against: a gate that can pass
// without checking anything is not a gate. Unset, it now skips and says so.
const CASE_REPOS = (process.env.DIMS_CASE_REPOS || '')
  .split(':').map(s => s.trim()).filter(Boolean);

test('a study inherits themes without owning any theme code', { skip:
  CASE_REPOS.length ? false : 'set DIMS_CASE_REPOS to a colon-separated list of case repos'
}, async () => {
  // The point of vendoring: a case repo has no stylesheet of its own.
  const fs = require('fs');
  const path = require('path');
  let checked = 0;
  for (const c of CASE_REPOS) {
    assert.ok(fs.existsSync(c), `DIMS_CASE_REPOS names ${c}, which does not exist`);
    assert.ok(fs.existsSync(path.join(c, 'vendor/dims-core/css/theme.css')),
      `${path.basename(c)} should vendor theme.css`);
    assert.ok(!fs.existsSync(path.join(c, 'css')),
      `${path.basename(c)} must not keep a stylesheet of its own`);
    const html = fs.readFileSync(path.join(c, 'index.html'), 'utf8');
    assert.ok(html.includes('themeSelect'), `${path.basename(c)} should offer the theme control`);
    checked++;
  }
  assert.ok(checked > 0, 'DIMS_CASE_REPOS was set but named no repository');
});


test('core assets resolve wherever the core was vendored', async () => {
  // The logo belongs to DIMS, not to a study, so it must not be looked for
  // under the study's own assets/. Two studies never carried a copy and simply
  // showed a broken image.
  const fs = require('fs');
  const path = require('path');
  const { ROOT } = require('./harness.js');
  const src = fs.readFileSync(path.join(ROOT, 'packages/dims-core/dims-core.js'), 'utf8');

  // match a real reference, not the comment that explains why there is none
  const codeRefs = src.split('\n').filter(l =>
    l.includes('assets/branding') && !l.trimStart().startsWith('//'));
  assert.deepStrictEqual(codeRefs, [],
    'the core must not look for its own logo under a study\'s assets/');
  assert.ok(src.includes('${CORE_BASE}branding/'),
    'the logo path should be built from where the core was loaded');

  // and the derivation itself: given a script URL, strip back to its directory
  const derive = (url) => url.replace(/[^/]*$/, '');
  assert.strictEqual(derive('http://x/vendor/dims-core/dims-core.js'), 'http://x/vendor/dims-core/');
  assert.strictEqual(derive('http://x/js/dims-core.js'), 'http://x/js/');

  // the files really are part of the core, so vendoring carries them
  for (const f of ['dims-logo-light.png', 'dims-logo-dark.png', 'dims-mark.png']) {
    assert.ok(fs.existsSync(path.join(ROOT, 'packages/dims-core/branding', f)),
      `${f} should ship with the core`);
  }
});
