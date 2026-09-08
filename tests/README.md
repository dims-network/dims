# Where the tests are, and why

Five roots, and each of them belongs to something. The question this file
answers is "where does my test go", so that the answer is a rule rather than a
precedent.

| root | what it tests | run it with |
|---|---|---|
| `tests/` | the repository as a whole — the contracts, and that a release is coherent | `pytest tests` |
| `tests/reference/` | **the analyses, against known answers** | `pytest tests/reference` |
| `packages/<pkg>/tests/` | one Python package, on its own | `pytest packages/dims-analysis` |
| `packages/dims-core/test/` | the dashboard host and the built-in tabs, headless | `cd packages/dims-core/test && node --test` |
| `apps/builder/tests/` | the wizard | `pytest apps/builder` |

**A package's tests live with the package.** A package is a shippable unit, and
`pip install -e packages/dims-analysis && pytest` has to work on its own. That
is why `dims-case/tests` is not a stray.

**`packages/dims-core/test/` stays singular.** It is an npm package with its own
`package.json` and `node_modules`; `test/` is the npm convention and
`node --test` finds it. Renaming it to match the Python suites would buy a
tidier `find` and nothing else.

## `tests/reference/` is the gate

It reads [`examples/reference/`](../examples/reference/README.md), a synthetic
study whose answers are known before anything runs: a 2 s sine recurs at 2 s, a
0.4 s lag sits 0.4 s off the diagonal, two independent red noises beat a 95 %
level 5 % of the time, and the wavelet constants are Torrence & Compo's
published ones. Every claim is checked against `pyrqa`, against that paper, or
against an independently computed null — never against this project's own
previous output.

Any change to `steps/rqa.py`, `steps/crqa.py`, `steps/crosswavelet.py` or
anything under `common/` runs it before being committed. CI runs it, and so does
every study's generated `core-update.yml`, against a candidate release before it
will offer the bump. See [`AGENTS.md`](../AGENTS.md).

The study and the suite used to be one directory. They are not, because
`conftest.build()` copies the study into a temporary folder to run it — and so
copied the tests into every temporary study it made.
