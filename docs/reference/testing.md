# Running the tests

Where the tests live, what each root is for, and what CI would catch. If you are
adding a test, the question this answers is *where does it go* — so that the
answer is a rule rather than a precedent.

## The roots

**A package's tests live with the package**, including the two that are not
importable packages.

| root | tests | run it with |
|---|---|---|
| `tests/` | the repository as a whole — the contracts, and that a release is coherent | `pytest tests` |
| `tests/reference/` | **the analyses, against known answers** | `pytest tests/reference` |
| `packages/<pkg>/tests/` | one Python package on its own | `pytest packages/dims-analysis` |
| `packages/dims-core/test/` | the dashboard host and the built-in tabs, headless | `cd packages/dims-core/test && node --test` |
| `apps/builder/tests/` | the wizard's Python | `pytest apps/builder` |
| `apps/builder/test/` | the wizard's page, headless | `cd apps/builder/test && node --test` |

`pytest` with no arguments runs every Python root, because they are listed in
`[tool.pytest.ini_options]` in the root `pyproject.toml`. **A new root belongs in
both places** — that file and `tests/README.md`.

Two roots have no package of their own:

- `packages/dims-case-scaffold/` ships `build_assets.py` and `serve.py` into every
  study, so a test there imports **by path** rather than by package name — its one
  suite does that for `serve.py`. `build_assets.py` is exercised from
  `packages/dims-case/tests/` instead, as part of building a study end to end.
- `packages/dims-tabs/` has no suite at all, because a tab cannot run without the
  host. The tabs are tested from `packages/dims-core/test/`, which loads both.

**`packages/dims-core/test/` is singular on purpose.** It is an npm package with
its own `package.json`; `test/` is the npm convention and `node --test` finds it.
Renaming it to match the Python suites would buy a tidier `find` and nothing else.
`apps/builder` has both spellings for the same reason — `tests/` is its Python,
`test/` is its JavaScript.

> **The counts in the repository are wrong and I have not changed them.**
> `tests/README.md` opens "Seven roots" over a table of six.
> `pyproject.toml`'s comment says "The five roots" over a list of six. Neither
> matches; both are stale rather than describing something I could not find.

## The two JavaScript suites need `npm install` first

They use `jsdom`, the only dependency either has. Both `package.json` files exist
for test tooling only and say so in as many words — one that **the dashboard** has
no build step and no runtime dependencies, the other the same of **the wizard**.

```sh
cd packages/dims-core/test && npm install && node --test
cd apps/builder/test      && npm install && node --test
```

## What CI runs

Eight jobs. Their value is less the coverage than that each one names a failure it
exists to prevent.

| job | runs | catches |
|---|---|---|
| **`syntax-and-config`** | the org's reusable dashboard workflow over `dims-analysis`, `dims-case`, `dims-case-scaffold`, `apps/builder`, `tools`, and the JS globs | a file that does not parse, in either language. **Note `packages/dims-notebooks` is not in that list**, so its Python is not syntax-checked here |
| **`contracts`** | `pytest tests/test_contracts.py tests/test_release.py` | a broken cross-reference, a config schema that is not a valid schema, a version that disagrees with itself |
| **`analysis-package`** | asserts `dims-analysis list` prints `rqa`, `crqa` and `crosswavelet`, then `pytest packages/dims-analysis/tests` | **a step that stopped being discoverable.** An installed package whose entry points are broken still imports fine; only asking the CLI catches it |
| **`case-tooling`** | `pytest packages/dims-case/tests` then `packages/dims-case-scaffold/tests` | vendoring, the pin, and the privacy hooks. Drives real `git` |
| **`reference-study`** | installs `pocl-opencl-icd`, asserts **pyrqa actually imports**, then `pytest tests/reference` | a wrong answer from an analysis, against an independent oracle |
| **`dashboard-host`** | Node 22, `node --test` in `packages/dims-core/test` | the host, the registry, the payload decoders and the built-in tabs |
| **`notebooks`** | `pytest tests/` in `packages/dims-notebooks`, plus an nbformat-4 and non-empty-cells check on the `.ipynb` files in that one directory (the glob does not recurse) | a diagnostic that stopped firing, and a notebook committed broken or blank |
| **`builder`** | `pytest tests` in `apps/builder`; `node --test` in `apps/builder/test`; then a smoke test that `POST /api/project` produces a study containing `config.json`, `index.html`, `serve.py`, `dims-case.json`, `vendor/dims-core` and `vendor/dims-tabs` | the wizard producing something that is not a working study |

### Two of these deserve a closer look

**The pyrqa comparison is gated in CI, not in the tests.** `tests/reference` checks
the recurrence analyses against pyrqa, an independent implementation. The tests
themselves use `importorskip`, so a contributor without pyrqa stays green — which
also means that on its own the suite can pass by never running the comparison.

CI closes that: it installs an OpenCL runtime (pyrqa has no CPU fallback) and then
**asserts the import outright** in a separate step before running the suite. So a
missing oracle fails the job rather than quietly hollowing it out. The gate lives
in the workflow; do not assume the suite carries it.

**`tests/reference/` restates its constants rather than importing them.** `DT`,
`PERIOD_S`, `LAG_S` and the target rate are written out again in its `conftest.py`,
with a comment saying so. Importing them from the code under test would make the
test agree with the code by construction, which is the one thing a reference test
may not do. The same applies to the Torrence & Compo figures: the wavelet reference
test restates 2.182 and 3.999 rather than importing the constants that hold them.

## What the release check covers

`tests/test_release.py` asserts that every package declares the same version, that
the source `__version__` agrees with packaging, and that `CHANGELOG.md`'s **newest**
entry is the version this tree declares.

That last one used to ask only whether the declared version had *a* `## v…` heading
somewhere in the file. Every past release leaves one behind, so once v1.0.0 was
written the check could not fail again — and it did not: **v1.4.0 was tagged while
the code still declared 1.3.0**, and the test passed on the v1.3.0 heading four
releases down the page. It now compares against the first heading, which is the
release being shipped, because the changelog is strictly newest-first.

One part is still weaker than it reads: "every package declares the same version"
walks the tree for `pyproject.toml` files, and the repository has exactly one, so a
set of one cannot disagree. The `__version__` check beside it does compare two real
files.

`tests/test_contracts.py` covers the other version that can drift silently — the
payload format, declared independently in `common/arrays.py` and `dims-core.js`.
Nothing compared those until v1.4.2. A bump on one side alone does not fail a test;
it fails in a browser, as every analysis panel going blank behind a message naming
the wrong fix.

## Before opening a pull request

```sh
python -m pip install -e ".[dev]"
python -m pytest -q                                   # every Python root
cd packages/dims-core/test && npm install && node --test
cd apps/builder/test       && npm install && node --test
```

`tests/reference` needs pyrqa and an OpenCL runtime, so it is the one suite most
contributors will let CI run.
