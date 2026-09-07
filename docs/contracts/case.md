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
  dims-case.json        visibility, pinned core, publishable paths, hashes
  config.json           the study (see config.schema.json)
  data.local.json       untracked; where the data really lives
  data.local.json.example   tracked; what to copy it from
  assets/               data, or empty but for MANIFEST.json on a private study
  build_assets.py       rebuild every asset from this study's raw data
  requirements.txt      what that rebuild needs
  serve.py              the local server; generated, refreshed by a bump
  index.html            loads vendor/; generated
  vendor/dims-core/     the pinned core, written by tooling, never by hand
  vendor/dims-tabs/     likewise
  tabs/                 optional: tabs that belong to this study alone
  opt/                  optional: this study's own analysis steps
  tools/                optional: this study's own data preparation
  .githooks/            private studies: the commit and push guards
  .github/workflows/    generated; thin callers into the shared workflows
```

Three of these are **generated and refreshed by a core bump** — `serve.py`,
`index.html`, `.github/workflows/`, and on a private study `.githooks/`. Editing
one is pointless: the next `dims-case sync` overwrites it.

`build_assets.py`, `requirements.txt` and `data.local.json.example` are
**seeded once and then the study's own**. A bump brings them forward only while
they are still byte-identical to what was seeded (their hashes are recorded in
`dims-case.json`); the moment a study edits one, it keeps it and `sync` says so.
Karnatak's `build_assets.py` drives motion capture, and losing that to a version
bump would not be a bump.

## The pin

`dims-case.json` names a core version. A bot opens a pull request when a newer
core is released; the PR changes the version and refreshes `vendor/`. CI then
checks that `vendor/` matches that release exactly.

CI does this by fetching the pinned tag and rebuilding `vendor/` from it, not
by comparing against the study's own record of what it should be — a study
whose `vendor/` came from a modified core agrees with itself. `dims-case check`
is the offline version, and `dims-case check --release` is what CI runs.

This is why case repos never drift: editing vendored code by hand is a red X,
not a silent fork. It is also why a case can be archived as it stands — the
analysis code that produced its results is inside it, at the version that
produced them.

It is **not** self-contained in the browser. `index.html` loads React, Plotly,
PapaParse and lodash from a CDN, so a dashboard opened without a network shows
an empty page. Vendoring those too is
[dims#12](https://github.com/dims-network/dims/issues/12); until then, "runs
locally" means `serve.py` on a machine with a network, not on a plane.

**Never edit `vendor/`.** Fix it in the monorepo and bump the pin.

## Creating one

```sh
tools/dims-case new ortho --visibility public                  # -> ./case-ortho
tools/dims-case new ortho --visibility public --dir path/to/it # somewhere else
tools/dims-case adopt path/ --name ortho --visibility public   # an existing one
```

`new` takes a **name**, not a path; `--dir` is how you choose where it lands.

`adopt` is deliberately a separate verb: `new` refuses a non-empty directory so
it can never write over someone's data, while `adopt` keeps `config.json` and
`assets/` exactly as they are and only adds what a case needs.

The visibility question is asked once, answered by the researcher, and written
down. See `data-visibility.md` — for a private case this also installs the
commit and push hooks, and the privacy workflow. The assets manifest is written
by the study when its assets are right, with `build_assets.py --write-manifest`;
it is not something creation can invent.

## Acceptance

- `python serve.py` renders every tab the config enables.
- `python build_assets.py --check` names this study's inputs and the analyses
  it would run, without installing anything.
- Touching one byte in `vendor/` fails CI, and `dims-case check --release`
  locally.
- A public case deploys to Pages; a private one has no Pages workflow at all,
  and `git add -f` of a restricted path is refused by the commit hook and by
  the push hook independently.
