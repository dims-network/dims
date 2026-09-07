# Contract: a case repository

A *case* is one study. It holds its configuration, its data, and a pinned copy
of the core — and no code of its own. If you are writing code in a case repo,
it belongs in this monorepo instead.

```
case-ortho/
  dims-case.json        visibility, pinned core version, publishable paths
  config.json           the study (see config.schema.json)
  data.local.json       untracked; where the data really lives (private cases)
  assets/               data, or empty with a MANIFEST for private cases
  vendor/dims-core/     the pinned core, written by a bot, never by hand
  index.html            loads vendor/, generated
  .github/workflows/    thin callers into the shared reusable workflows
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
dims case new ortho --visibility public
```

The visibility question is asked once, answered by the researcher, and written
down. See `data-visibility.md` — for a private case this also installs the
hooks and the manifest.

## Acceptance

- `python serve.py` renders every tab the config enables.
- Touching one byte in `vendor/` fails CI.
- A public case deploys to Pages; a private one has no Pages workflow at all.
