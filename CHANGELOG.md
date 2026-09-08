# Changelog

Releases are tagged `vX.Y.Z` and the whole core moves together: a study pins one
version in its `dims-case.json` and takes a fix by bumping it, never by editing
`vendor/`.

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
