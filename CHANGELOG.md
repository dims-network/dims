# Changelog

Releases are tagged `vX.Y.Z` and the whole core moves together: a study pins one
version in its `dims-case.json` and takes a fix by bumping it, never by editing
`vendor/`.

Full notes for each release are on
[GitHub Releases](https://github.com/dims-network/dims/releases).

## v2.0.0

**Every RQA, cross-RQA and cross-wavelet output produced before this release is
unreadable by the new tabs and must be recomputed.** Rebuild with
`python build_assets.py`, then `dims-analysis manifest`.

A study that bumps `dimsCore` without rebuilding does **not** get empty panels:
every tab checks `payload_version` and says which core wrote the file and what
to run. An empty panel is indistinguishable from a study with no data, and that
must not be something anyone discovers by looking at a dashboard.

### Why the major bump

Nine defects were found in these outputs over one session, one at a time, each
by accident. They were not nine unrelated bugs: **nothing stated what an
analysis output was supposed to be**, so every check could only ask "did it
crash?" and every fix was local. This release states it — 
`docs/contracts/analysis-output.md` — and tests it against
`examples/reference/`, a synthetic study whose answers are known before anything
runs, which is now a **gate**: CI runs it, and every study's generated
`core-update.yml` runs it against a candidate release before offering the bump.

### Numbers that move

All three cross-wavelet significance levels were wrong, in the same way. The
cross-wavelet spectrum is the square root of a product of two chi-squares
(Torrence & Compo 1998, eq. 30), not a chi-square, and all three used the
chi-square and evaluated the background at the mean of the two AR(1)
coefficients rather than combining the two series' own spectra.

- the local level was **1.50× too high** with matched coefficients, 2.39× at
  α = (0.95, 0.2). The built-in tab draws a phase arrow only where power beats
  it, so it drew about a third of the arrows it should: on the reference study
  3.13 % of cells became 9.10 %.
- the time-averaged level was **1.32–1.37×** too high, the scale-averaged
  **1.267×**.

`LAM` could exceed 1.0 — a share of points that cannot. The diagonal and
vertical line scans ignore different things, so they cannot share a denominator;
correcting DET's had inflated LAM's. On a pure sine LAM was 0.9681 where pyrqa
gives 0.9548.

A constant signal reported `recurrence_rate = -0.000977517`, a negative share of
cells, on a dashboard caption. It is refused with a sentence now.

The RQA analysis window was silently overridden — 20 s and 1 s requested,
10.24 s and 0.5 s used — and computed in samples, so the reported time axis
moved with the sampling rate. Both are recorded now, asked-for beside used, and
decided in seconds.

### One file format

`.npz` is gone. Large arrays travel inside the JSON as base64 bitmaps and
float32 grids, each naming its encoding so a reader that meets an unknown one
says so rather than drawing an empty panel. Measured on the reference study: RQA
3.8× smaller, cRQA 2.2×, and the cross-wavelet file a page fetches 2.2×. The
full-resolution cross-wavelet file is 1.8× *larger* than the archive it
replaces, which is the stated price of one format with one decoder.

Cross-wavelet writes `{video}_crosswavelet_full.json` in the same schema; the
recurrence analyses carry their full-resolution signal in their single file.

### New

- **The cross-effector network is a built-in tab**, gated by `include_network`,
  with grouping from config. It lived in one private study, where it was the
  only reader of the Monte Carlo coherence null the core computes for everyone.
  **A study that carries its own `tabs/network.js` must delete it when it
  bumps**: two tabs cannot share an id, and the built-in wins.
- **The coherence null runs when something reads it.** Default 100 surrogates
  when `include_network` is set, 0 otherwise, and an explicit
  `analysis.crosswavelet.mcCount` always wins. The step says which it chose.
  `case-demo` and `case-ortho` have no consumer, so their cross-wavelet rebuild
  drops from hours to seconds.
- **`--jobs`** computes cross-wavelet pairs concurrently, byte-identically:
  95.3 s against 37.1 s on the reference study with a cold null cache.
- The cross-wavelet tab reports what share of cells beat chance, or says the
  null was not computed and names the setting that would produce it.
- **The builder is rebuilt around the core it lives beside.** It no longer asks
  where to fetch the dashboard from — there is one scaffold, in this repository.
  It asks who may see the data and installs the guards that answer implies, can
  reopen a study you built earlier, loads a two-session example study in one
  click, and reaches every config key a built-in tab or shared analysis reads.
- **`analysis.rqa` and `analysis.crqa` are read.** The schema has documented
  `window` and `step` for as long as the tuning block has existed and neither
  recurrence step read them; the window was a command-line flag the step adapter
  never passed. `targetRecurrence` joins them.
- **`dims-case check` verifies the study's own assets**, so bumping without
  rebuilding fails in CI rather than in a browser, and warns when a study-owned
  tab shadows a built-in.

### Upgrading

A study bumps with `dims-case sync . --version 2.0.0`, then **rebuilds**:
`python build_assets.py` and `dims-analysis manifest`. `dims-case check` will
tell you if you forgot.

A study carrying its own `tabs/network.js` must delete it — the cross-effector
network is a built-in now, two tabs cannot share an id, and the built-in wins.
Set `include_network` with `groups` to keep the grouping that tab had.

What each of the three studies actually needed, what it cost and what surprised
us is in [`docs/migrations/v2.0.0.md`](docs/migrations/v2.0.0.md).

## v1.5.2

**A reduction cap that is actually a cap.** `factor_for` floor-divided, so
`n // factor` could be twice `max_points`: 999 points against a cap of 500 gave
a factor of 1 and drew all 999. Anything between the cap and twice the cap was
not reduced at all.

Invisible in a series plot — 530 points where 500 was asked for looks fine —
and expensive in a recurrence plot, which is quadratic in it. Measured on an
ORTHO recording whose categorical gaze recurrence rate is 69%: the unreduced
896-point matrix wrote 615,095 sparse index pairs, and that study's RQA
payloads came to 297 MB.

**Any RQA, cross-RQA or categorical output should be recomputed**, as much for
its size as for its correctness.

## v1.5.1

- **`dims-case check` says when a clone has not enabled its guards.** A private
  study's hooks are tracked, but git does not run them until someone sets
  `core.hooksPath` — and forgetting is silent, which is the one thing a guard
  may not be. CI still catches it, but only after a push. A warning, not a
  failure: it is a fact about the clone, not about the study.
- **The contract checks run in `pytest`, not only in CI.** The core's own CI was
  red for four releases over the scaffold's `config.json`, and the local suite
  had nothing to say about it. The schema, the scaffold, and every path the
  README and the contracts point at are now checked where a developer meets
  them.
- The CI syntax check covers `dims-case`, the scaffold, the builder and
  `tools/`, not only `dims-analysis`.

## v1.5.0

CI that can fail, and a regression suite that tests the product rather than a
copy of it.

- **The Python syntax check could not fail.** It ended in `|| true`, and every
  study passed `python_paths: ""` besides — so `build_assets.py`, every `opt/`
  and `tools/` script, and a 1245-line study-owned tab were never parsed by CI.
  Studies now check their own code and leave the vendored core alone, which is
  verified byte-for-byte against the release anyway.
- **The coherence regression tests re-implemented coherence.** The suite
  guarding the defect that prompted this whole migration carried its own copy
  of the formula, and the copy had already fallen behind: it omitted the
  masking of cells with too little power to define coherence — itself a fix for
  a variant of the same bug. The measure now lives once, in
  `common/coherence.py`, and the tests import it. Confirmed by breaking the
  real function two ways and watching them fail.
- **Stillness drawn as perfect coupling was untested.** That is the defect a
  collaborator actually reported, and removing its fix left the suite green.
  Three tests now cover it, including one that checks the guard does not eat
  ordinary cells and hide real coupling.
- **A test asserted on source text** — that `crosswavelet.py` contained the
  string `np.clip(WCO, 0.0, 1.0)`. It passed for any file mentioning it and
  failed for a refactor that kept the behaviour. It runs the code now.
- **A from-zero acceptance test**: `dims-case new`, add series, `--check`,
  build, both resolutions present and parsing, write a manifest, verify it, and
  a deleted asset reported. The path a person takes, which no unit test stands
  in for.

## v1.4.1

Documentation. No behaviour changes beyond two error messages, but this is the
release the website renders from, so it is tagged.

- **`docs/getting-started.md`**: the page that did not exist — raw data to a
  running dashboard, with every command run on a clean directory before it was
  written. Writing it is what found the two config errors in v1.4.0's notes, and
  a third: `dataTypes` is an object keyed by recording, not a flat list, and the
  first draft of this page got that wrong.
- **`docs/coherence.md`**: the method, and how to read a coherence value against
  its chance level. It was explained in one place only — an audit inside a
  private study, which also names recordings — and repeated approximately in
  three others. This page carries no study data.
- **READMEs for `dims-core`, `dims-tabs` and `dims-case`**, which had none
  despite being, respectively, what every dashboard runs on, what it draws with,
  and what creates every study.
- **`docs/dashboard-user-guide.md` is gone.** It was a byte-identical copy of a
  June template README, orphaned, describing `js/app.js` and `opt/step_*.py`.

## v1.4.0

Documentation that matches the code, one API corrected, and a version bump that
brings a study's own files forward instead of freezing them.

**Breaking:** `series.load_or_none` returns `None`, not `(None, None)`. The pair
made the obvious guard — `if load_or_none(...) is None` — always false, so a
caller who wrote it met an `AttributeError` several lines later instead of a
skip. Callers that unpack unconditionally must now check first. Only one caller
existed inside the core; a study-owned step that unpacks the result needs the
same one-line change.

### The contracts describe what runs

- **`step.md` was fiction.** Its `ctx` table was wrong on all five rows, two of
  the methods it documented exist nowhere, and its example would not run. It
  now documents both real ways to add an analysis — a study-owned script in
  `opt/`, which is what every shipped example actually is, and a registered
  step — with the true signatures, and says plainly that `ctx` is paths and
  results rather than a data layer.
- **`assets.md`** now names the container key per file (`crosswavelet_pairs`,
  not `crosswavelet_data` — reading the wrong one gets an empty tab, not an
  error), describes `sparse_matrix` and the `reduction` block, lists the `.npz`
  members, and says why the recurrence matrix is not among them.
- **`case.md`** no longer claims a case runs offline. Every dashboard loads
  five libraries from a CDN, so a study opened without a network is a blank
  page (dims#12). It also documents which files a bump regenerates and which it
  will not touch.

### Analyses

- **`reduce.block_mode`**, for categorical series. The mean of two
  area-of-interest codes is a third area nobody looked at; the mode is a value
  that was actually true.

### Studies keep up with the scaffold

`build_assets.py`, `requirements.txt` and `data.local.json.example` were seeded
once and never touched again, so a study that had not modified them was frozen
at whatever the scaffold looked like the day it was created — the same drift
the vendored core exists to prevent, reappearing in the files vendoring does not
cover. Their hashes are now recorded in `dims-case.json`: a file still matching
its record is brought forward, a file the study has edited is kept, and `sync`
says which happened for each.

## v1.3.2

The guards `docs/contracts/data-visibility.md` promises a private study. Three
of the four did not exist as described. **A private study should bump to this
release**: `dims-case sync` refreshes the hooks, which it previously never did.

- **The pre-push hook does something.** It was a byte-for-byte copy of
  pre-commit, so it inspected the staging area — empty at push time — and
  passed every push. It now reads the refs being pushed and inspects every
  commit in the range, so data that a later commit deleted is still caught: it
  is in the history the push would publish.
- **A missing `restricted` key no longer disables the hooks.** The contract's
  own example omitted the key, so a `dims-case.json` written by hand from the
  documentation declared a study private and blocked nothing. Both hooks now
  fall back to the core's list, as the CI guard already did.
- **`assets/MANIFEST.json` exists.** Both hooks and the CI guard already
  exempted it by name — an exemption for a file nothing wrote. `dims-analysis
  manifest` records names, sizes and checksums, never content, which is what
  makes that exemption safe; `--check` says whether a rebuild produced
  everything, which on a study whose data lives outside git nothing else could
  answer. `build_assets.py` reports it, and `--write-manifest` records it.
- **`dims-case sync` refreshes the hooks**, which are generated code like
  `index.html` and the workflows. Without it a fix to a guard never reached the
  study holding the data.
- **`AGENTS.md`** is written; the issue template had linked to a 404.

## v1.3.1

Tooling only. No study's `vendor/` bytes change between 1.3.0 and 1.3.1, so a
bump is a one-line edit to `dimsCore` — but CI needs the bump, because it runs
the pinned release's own copy of `dims-case`.

- **The vendored-core check compares against the release.** `dims-case check`
  compared `vendor/` with the hashes recorded in the study's own
  `dims-case.json`; both sides live in the study, so a copy taken from a
  modified core agrees with itself and passes. `dims-case check --release`
  rebuilds `vendor/` from this checkout and compares against that, which is
  what CI now runs from a checkout of the pinned tag. The org's reusable
  workflow, which did this with a `diff -r` that would have failed on every
  study and had no callers, is wired into all three studies.
- **`dims-case sync` seeds a rebuild path into studies that predate it.**
  `build_assets.py`, `requirements.txt` and `data.local.json.example` are
  copied in when absent and never overwritten afterwards, so a study that was
  created before the scaffold had them can receive them by bumping the core.
- **`dims-case` has tests.** It generates every study repository and had none.

## v1.3.0

The analyses stopped failing quietly, and the builder started working on the
projects it generates. **Any RQA or cross-RQA output produced before this
release should be recomputed** — see "Corrections" below.

### Corrections to the analyses

- **A run that produced nothing now fails.** Every step caught its own
  unreadable-input case, printed a warning and returned, so `dims-analysis run`
  exited 0 having written no files and `build_assets.py` reported success. The
  runner now checks each enabled step actually wrote something, and reports a
  step that could not be imported rather than skipping it silently.
- **RQA and cross-RQA read the directory they said they resolved.** Both
  resolved only their *output* through `data.local.json` and read input from a
  relative path — so on a private study, whose data lives outside the
  repository, they were unrunnable while printing "assets resolved".
- **A step no longer deletes an analysis it did not produce.** The output file
  is keyed by video, so a study-owned analysis writing into the same file (as
  ORTHO's categorical gaze RQA does) was erased by a re-run of the shared step.
- **Recurrence plots keep both their structure and their rate.** The reduction
  for the browser was plain striding, which deletes a recurrent line one cell
  off the main diagonal — precisely what a lagged coupling looks like. It is now
  a density-preserving block reduction: structure survives, and the drawn
  density matches the recurrence rate printed beside it. The payload records
  `reduction`, including the rate actually drawn.
- **DET and LAM were deflated.** Line lengths excluded the line of identity and
  the denominator did not, understating both by roughly `14/W` at a 7% target —
  2% over a 600-point window, 24% over a 60-point one.
- **One recurrence rule and one series reader.** The two steps had their own
  copies of both; only one of the readers sorted by time, and the length floor
  differed. Consolidated into `common/recurrence.py` and `common/series.py`.
- **`pycwt` is pinned.** Every one of its releases is a pre-release, so an
  unpinned dependency resolved to whatever beta was newest — for the package
  that computes the coherence and its Monte Carlo null.

### Outputs

- RQA and cross-RQA now write a full-resolution `.npz` beside the JSON, as
  cross-wavelet already did. It holds the windowed metrics, the prepared
  signals and the threshold — not the recurrence matrix, which is quadratic in
  the recording and reaches 3.4 billion cells on a twenty-minute one.
- The cross-wavelet Monte Carlo null uses 300 surrogate pairs, `pycwt`'s own
  default, rather than 100.

### The builder

- Now in the monorepo at `apps/builder/`, and its precompute step works on the
  projects it generates: it runs `dims-analysis run` instead of looking for the
  pre-migration template's `opt/step_*.py`, which no generated project has ever
  had. Before this it failed for every project with a `FileNotFoundError`.

### Studies

- `dims-case new` produces a study that can rebuild itself: a generic
  `build_assets.py`, a `requirements.txt`, a `data.local.json.example` and a
  README explaining how to run it and what each tab draws.
- `dims-case sync` refreshes `serve.py`, which it never did — so a study kept
  whatever server it was created with, including one with no external-assets
  support.

### Dashboard

- Figures are re-measured when their tab is shown. A plot drawn while its pane
  was hidden had no width to measure and came back at the wrong size until
  something forced a relayout.
