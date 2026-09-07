# Contract: a case repository

A *case* is one study. It holds its configuration, its data, and a pinned copy
of the core.

It holds **no dashboard code**. If you are editing a tab, an analysis or the
host inside a case repo, it belongs in this monorepo instead.

It may hold **its own tabs**, in `tabs/`, for views that mean nothing to any
other study — see `tab.md`. And it may hold **study-specific data preparation** — scripts that turn this study's
raw recordings and logs into the assets the dashboard reads. Those are part of
the study, not of DIMS, and belong here. Ortho's `tools/` is the example: it
builds time series and clips from ORTHO datalogs, and means nothing to any
other study.

```
case-ortho/
  dims-case.json        visibility, pinned core version, publishable paths
  config.json           the study (see config.schema.json)
  data.local.json       untracked; where the data really lives (private cases)
  assets/               data, or empty with a MANIFEST for private cases
  vendor/dims-core/     the pinned core, written by tooling, never by hand
  vendor/dims-tabs/     likewise
  index.html            loads vendor/, generated
  tabs/                 optional: tabs that belong to this study alone
  tools/                optional: this study's own data preparation
  .github/workflows/    generated; thin callers into the shared workflows
```

## The pin

`dims-case.json` names a core version. A bot opens a pull request when a newer
core is released; the PR changes the version and refreshes `vendor/`. CI then
checks that `vendor/` matches that release exactly.

This is why case repos never drift: editing vendored code by hand is a red X,
not a silent fork. It is also why each case stays self-contained — it runs
offline and can be archived with a DOI, which a CDN reference could not.

**Never edit `vendor/`.** Fix it in the monorepo and bump the pin.

## Creating one

```sh
tools/dims-case new ortho --visibility public      # a fresh study
tools/dims-case adopt path/ --name ortho --visibility public   # an existing one
```

`adopt` is deliberately a separate verb: `new` refuses a non-empty directory so
it can never write over someone's data, while `adopt` keeps `config.json` and
`assets/` exactly as they are and only adds what a case needs.

The visibility question is asked once, answered by the researcher, and written
down. See `data-visibility.md` — for a private case this also installs the
hooks and the manifest.

## Acceptance

- `python serve.py` renders every tab the config enables.
- Touching one byte in `vendor/` fails CI.
- A public case deploys to Pages; a private one has no Pages workflow at all.
