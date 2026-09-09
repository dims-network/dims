# Changelog

Releases are tagged `vX.Y.Z` and the whole core moves together: a study pins one
version in its `dims-case.json` and takes a fix by bumping it, never by editing
`vendor/`.

## v1.1.0

One change to what an analysis writes, one to how the core is packaged, and a
cleanup pass behind both. A study takes this by bumping its pin and rebuilding;
cross-RQA payloads gain fields, and nothing else moves.

**Cross-RQA records the rate it aimed at.** It writes `target_recurrence`,
`achieved_recurrence` and `recurrence_rate_warning` for the first time, and the
rate under `recurrence_rate` as well as `global_recurrence_rate`. Contract A6
required this everywhere; only RQA did it, so a cross-RQA threshold that landed
on a plateau went unreported. No existing number changed.

**One distribution.** `packages/dims-analysis` no longer has its own
`pyproject.toml` declaring the same version, dependencies, console script and
three entry points as the root, so installing both no longer registers every
step twice. `dims_checks` is installable at last, three redundant
`requirements.txt` files are gone, and the one-click launchers install the
`builder` extra rather than a list that had drifted to no version floors.

**`dims-case` works when installed.** Its 253 lines lived in `tools/`, outside
any package, reached by a console script that ran the file by path — so `pip
install dims-network` gave a command that could only say it needed a checkout.
It is `dims_case.cli` now, with `tools/dims-case` kept as a shim.

**Faster, on the same numbers.** The windowed recurrence metrics no longer build
a run-length histogram in order to sum it: 23x faster at a 1000-sample window,
on the phase that dominated a recurrence analysis. The distance-triangle
percentile stopped spending two int64 index arrays to reach half a matrix. Every
value is bit-identical, which the reference baseline checks.

**Fixes you can see.** Four dashboard headings were white on the default white
background. Three tabs set a plot background that did not follow a theme switch.
A theme change and a video change cleared different tab caches.

**Fixes you cannot.** The recurrence steps rewrote a module-level input path, so
a second study analysed in one process would have read the first study's data;
they take parameters now, and no `global` survives in either. The privacy hooks'
fallback list of restricted directories was a second copy that nothing kept in
step with the first. `dims-case new` copied `__pycache__` into every new study.
A study's `scipy==` pin was silently unpinned by a repair meant for a template
that no longer exists. `.gitignore`'s `assets/` was unanchored and hid anything
new under the scaffold.

**The tests.** 382 to 446, and three that could not fail now can: the reference
baseline could not be regenerated at all (`make_baseline.py` pointed at the
wrong directory), a JS test looped over two absolute paths in one contributor's
home directory and passed everywhere else having asserted nothing, and `pytest`
at the repository root was a collection error rather than a skip without the
builder's extra. CI runs `packages/dims-case/tests` — the vendored-core check
and the privacy hooks — which no job had ever run.

## v1.0.2

Documentation only. No analysis or payload change: a study takes this by
re-vendoring, with no rebuild.

- The three analyses are documented. `docs/analyses/` covers cross-wavelet and
  coherence, RQA and cross-RQA — the algorithm, every parameter and its real
  default, every output field with its shape and units, and what each one does
  not do. The figures are produced by running the analyses over synthetic
  signals, not drawn.
- Stated for the first time: the recurrence steps apply **no time-delay
  embedding**, threshold on a recurrence rate rather than a radius, use no
  Theiler window, fix the minimum line length at 2, report `L_MAX` in seconds,
  and compute none of L, ENTR or TT.
- `docs/coherence.md` is now a section of the cross-wavelet page, beside the
  transform it comes from and the three other significance levels it is easy to
  confuse it with.
- The coherence page said 300 Monte Carlo surrogates was the default. It is 100
  when `include_network` is set and 0 otherwise; 300 is the number to publish
  with.
- Two gaps named rather than papered over: `crqa` records no achieved
  recurrence rate to compare with its target (contract A6), and
  `include_cRQA` silently ignores the flat list of data types that
  `include_crosswavelet` accepts.
- The step contract's example named a class that does not exist.

## v1.0.1

Documentation and wording only. No analysis or payload change: a study takes
this by re-vendoring, with no rebuild.

- The README's install and `dims-case new` commands work as written — the
  checkout install, `--visibility`, and `case-<name>` as the directory created.
- Python 3.10 is the floor everywhere. Three pages said 3.9, which pip refuses.
- The cross-effector network is documented where it was missing: the built-in
  tab list, the scaffold's tab table and config example, and what
  `include_network` needs to draw anything useful.
- A dashboard reading an old asset no longer names a release the renumbering
  removed; it says the payload is older and how to rebuild.
- The `agent-ready` issue label is now `ready`.

## v1.0.0

The first public release.

**The dashboard.** A study's recordings, time series, transcripts and ELAN
annotations on one timeline, with tabs that appear only when the study's
`config.json` asks for them: recurrence, cross-recurrence, cross-wavelet and
coherence, and a cross-effector network.

**The analyses**, as the `dims-analysis` package: recurrence quantification,
cross-recurrence, and the cross-wavelet transform with an AR(1) coherence null,
following Torrence & Compo (1998). Every constant taken from that paper is
transcribed in `examples/reference/`, and `tests/reference/` checks the results
against it, against `pyrqa`, and against an independently computed null.

**One study, one small repository.** `dims-case` creates a study, pins a
released core into `vendor/`, and verifies it byte for byte; studies with data
about identifiable people declare themselves private and get commit, push and CI
guards that keep that data out of git.

**A no-code builder.** `dims-builder` walks from a folder of recordings to a
working dashboard, including the analyses.

See [`docs/contracts/`](docs/contracts/) for what each part promises.
