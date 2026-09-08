# dims-case

Creating a study repository, and keeping its pinned core honest.

This is library code with two callers that must not disagree: the `dims-case`
command, which a person runs, and the no-code builder, which writes the same
thing for someone who will never open a terminal.

```sh
dims-case new mystudy --visibility public|private   # -> ./case-mystudy
dims-case adopt path/ --name mystudy --visibility …  # an existing directory
dims-case sync  path/                                # take a newer core
dims-case check path/ [--release]                    # verify vendor/
```

## What a bump may and may not overwrite

| | |
|---|---|
| **regenerated every sync** | `serve.py`, `index.html`, `.github/workflows/`, and a private study's `.githooks/` |
| **seeded once, then the study's** | `build_assets.py`, `requirements.txt`, `data.local.json.example` |
| **never touched** | `config.json`, `assets/`, `tabs/`, `opt/`, `tools/` |

The middle row is the subtle one. "Never overwritten" left a study that had not
modified its seeded files frozen at whatever the scaffold looked like the day it
was created — the same drift vendoring exists to prevent. So the hash of each
seeded file is recorded in `dims-case.json`: still matching means untouched and
is brought forward; anything else is the study's own and is kept, with a line
saying so.

## The two checks, and why there are two

`check` compares `vendor/` against the hashes recorded in the study's own
`dims-case.json`. That catches a hand edit and needs no network, so it is what a
contributor runs.

`check --release` rebuilds `vendor/` from *this* checkout of the core and
compares against that. Both sides of the offline check live in the study, so a
`vendor/` copied from a modified core agrees with itself and passes; only the
release can settle it. CI runs `--release` from a checkout of the tag the study
pins.

## Private studies

`--visibility private` installs a commit hook and a push hook, and a CI privacy
workflow. They are not the same file: the commit hook reads the staging area,
the push hook reads the range being pushed — including commits whose data a
later commit deleted, because that data is still in the history the push would
publish. See [`docs/contracts/data-visibility.md`](../../docs/contracts/data-visibility.md).

## Tests

```sh
python -m pytest packages/dims-case
```

They exercise the guards against real `git`: a force-added video must be
refused, `--no-verify` must then be caught at push, and a missing `restricted`
key must not silently disable either.
