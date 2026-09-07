# Changelog

Releases are tagged `vX.Y.Z` and the whole core moves together: a study pins one
version in its `dims-case.json` and takes a fix by bumping it, never by editing
`vendor/`.

Full notes for each release are on
[GitHub Releases](https://github.com/dims-network/dims/releases).

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
