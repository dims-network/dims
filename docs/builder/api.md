# The builder's HTTP API

The wizard is a Flask app serving one page, one shared script and fifteen `/api/`
routes, all under `127.0.0.1`. Most return JSON; two do not — `/api/staged` returns
a file and `/api/precompute` returns a text stream. This page is for someone working on the wizard itself; if you only
want to *use* it, [the builder](index.md) is the page you want.

**There is no authentication and no multi-user state.** It is a local single-user
tool holding one project at a time in the server process.

## Page and assets

| route | |
|---|---|
| `GET /` | the wizard page — `static/index.html` |
| `GET /static/<path:fname>` | `builder.js`, `style.css` |
| `GET /vendor/figure-geometry.js` | **the body the step 4 diagram is drawn on**, served straight from the DIMS checkout's `packages/dims-tabs/` |

That last route is the mechanism that keeps the wizard's diagram and the
dashboard's network tab identical. The wizard is not given a copy — it is served
the same file the dashboard vendors, so the two cannot drift. See
[`figure-geometry.md`](../reference/figure-geometry.md).

## Opening or creating a project

| route | |
|---|---|
| `POST /api/project` | create a new study at a path, with a visibility. Delegates the skeleton to `dims_case.core` |
| `POST /api/open` | reopen a study the builder made earlier, with every step filled in from its `config.json` |

`POST /api/project` is what the CI smoke test drives: it asserts the result
contains `config.json`, `index.html`, `serve.py`, `dims-case.json`,
`vendor/dims-core` and `vendor/dims-tabs` — i.e. that the wizard produces a
complete study and not a directory that merely looks like one.

## Staging files (step 2)

Uploads go to a staging directory inside the package and are only placed into the
study at build time.

| route | |
|---|---|
| `POST /api/upload` | stage a file. Returns a **list** of rows — an id, inferred role, guessed session id and measure name each — because a multi-column CSV is split into one staged file per measure |
| `POST /api/assign` | correct the role, session or measure of a staged file |
| `DELETE /api/upload/<fid>` | drop a staged file |
| `GET /api/staged/<fid>` | serve a staged file back, **range-enabled** so the align step can scrub a video that is not in the study yet |
| `GET /api/sessions` | the sessions and measures implied by what is currently staged |
| `POST /api/samples` | stage the example study, generating it on first use |

The role is inferred from the extension, then shown for correction rather than
assumed — the wizard guesses and says it guessed.

## Alignment (step 3)

| route | |
|---|---|
| `POST /api/trim_video` | record a trim for a session's video |
| `POST /api/pad_timeseries` | record zero-padding for a time series |

**Both routes only record a spec.** Nothing is trimmed or padded here; the work
happens in `/api/build`, applied to the copies placed in the study. `/api/trim_video`
does check that an `ffmpeg` is available before accepting one.

When the work does run, only trimming shells out — `media.pad_timeseries` is
pure-Python CSV rewriting. The ffmpeg comes from `imageio-ffmpeg` rather than a
system install.

## Config, validation and build (steps 4–5)

| route | |
|---|---|
| `GET \| POST /api/config` | read the assembled config, or **merge** keys into it. POST updates the server's in-memory state only — it does not write `config.json`; that happens at build |
| `POST /api/validate` | the problem list, split into errors and warnings |
| `POST /api/build` | write the study: place staged files, apply the align specs, then write `config.json` |

`validate.py` holds the per-file and per-config checks: `validate_csv`,
`validate_transcript` and `validate_eaf` per file, then `validate_config` and
`validate_network`.

The **schema** check lives elsewhere, in `project.schema_problems()`, and runs
inside `write_config` against
[`docs/contracts/config.schema.json`](../contracts/config.schema.json) — the same
schema the repository tests treat as authoritative. Two things to know about it:
it runs **after** the staged assets have been copied into the study, so a schema
failure leaves files already placed; and it **passes silently** when `jsonschema`
is not installed or the schema cannot be read.

## Running and previewing (steps 6–7)

| route | |
|---|---|
| `POST /api/precompute` | run the analyses, **streaming** the log back as chunked text |
| `POST /api/preview` | start `serve.py` in the study and return its URL |

`precompute` creates a virtualenv inside the study and installs the analysis
requirements into it, so the run does not inherit however the builder itself was
installed. It streams with `PYTHONUNBUFFERED` set, because a progress log that
arrives all at once at the end is not a progress log.

It carries three repairs for requirement files written by older studies: a
`scipy==1.26.4` pin that never existed is **rewritten to an unpinned `scipy`**,
`json` listed as though it were a package is **dropped**, and `numpy` is
**appended** in case the study never named it. Without these an old study's
requirements simply fail to install.

## Where it lives

`apps/builder/dims_builder/` — `server.py` has the routes; `project.py` creates
and reads a study and holds the schema check; `validate.py` the file and config
checks; `media.py` the trimming and padding;
`precompute.py` the analysis run; `example_study.py` generates ConvoConnect-Mini.

Tests are split by language: `apps/builder/tests/` is the Python,
`apps/builder/test/` is the JavaScript. See [testing](../reference/testing.md).
