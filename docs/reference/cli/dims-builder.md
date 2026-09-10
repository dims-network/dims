# `dims-builder`

Starts the no-code wizard and opens a browser at it. There are no subcommands and
no flags — everything is decided in the page.

```sh
pip install -e './dims[builder]'
dims-builder
```

What it needs beyond the base install is the `builder` extra: `flask`,
`imageio-ffmpeg` and `jsonschema`.

## Three ways to start it

| | |
|---|---|
| `dims-builder` | the console script. It is always installed; the `builder` extra is what supplies the Flask it needs to run |
| `python -m dims_builder` | the same thing from a checkout |
| `run.sh` / `run.command` / `run.bat` | one-click launchers in `apps/builder/`. `run.sh` and `run.bat` create `apps/builder/.venv` and `pip install -e "../..[builder]"` into it, so someone can start from a downloaded folder without knowing what a virtualenv is |

`run.command` is the macOS double-clickable; it just executes `run.sh`.

## Environment

| variable | |
|---|---|
| `BUILDER_PORT` | the port to serve on. Otherwise it takes **5000** if free, and an OS-assigned free port if not |
| `DIMS_BUILDER_NO_BROWSER` | set it and no browser opens. The end-to-end test sets this — a test run should not take over the screen of whoever is running it |
| `WERKZEUG_RUN_MAIN` | set by Flask's reloader; also suppresses the browser, so a reload does not open a second tab |

It binds **`127.0.0.1` only** and runs with `debug=False`, threaded. It is a
local single-user tool: there is no authentication, and it is not meant to be
exposed to a network.

The browser is opened a second after the server starts, and the URL is printed
either way, so you can open it yourself if nothing appears.

## What it does

Seven steps, ending in a working study directory. See
[the builder](../../builder/index.md) for what each step asks, and
[its HTTP API](../../builder/api.md) if you are working on the wizard itself.

The wizard delegates the study skeleton to the same `dims_case.core` that
[`dims-case`](dims-case.md) uses, so the two produce **the same study** rather
than two slightly different ones.
