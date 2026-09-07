# Changelog

Releases are tagged `vX.Y.Z` and the whole core moves together: a study pins one
version in its `dims-case.json` and takes a fix by bumping it, never by editing
`vendor/`.

Full notes for each release are on
[GitHub Releases](https://github.com/dims-network/dims/releases).

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
