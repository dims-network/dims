# DIMS

Open tools for exploring **dynamic interactions and multimodal signals** — time
series, recurrence quantification, wavelet coherence and annotations, aligned to
video.

This is the monorepo: one copy of the code, from which every DIMS dashboard is
built. Individual studies live in their own small *case* repositories carrying
only `config.json`, their data, and a pinned version of this core.

```
packages/dims-core/          the host: config, video, the time bus, the tab registry
packages/dims-tabs/          every tab, one self-registering file each
packages/dims-analysis/      the Python analyses, a pip package
packages/dims-case/          creating a study and keeping its core honest
packages/dims-case-scaffold/ what a new study starts from
packages/dims-notebooks/     sanity checks, as notebooks you can run on a study
apps/builder/                the no-code wizard
docs/contracts/              the contracts — read one, not all of them
```

## Install

```sh
pip install dims-network              # the analyses, and dims-analysis / dims-case
pip install "dims-network[builder]"   # adds the no-code wizard: dims-builder
pip install "dims-network[notebooks]" # adds the sanity-check notebooks
```

One distribution, one version. Flask is behind the `builder` extra, so a machine
that only computes results does not install a web framework to do it.

*(Not on PyPI yet — `pip install -e .` from a checkout for now. The name is
`dims-network` because `dims` is taken by an unrelated project.)*

## Working on DIMS

Find your task, read the **one** file named. The contracts are written to be
read individually; you should not need to read this whole directory to start.

| I want to… | Read |
|---|---|
| Add or change a **tab** | [`docs/contracts/tab.md`](docs/contracts/tab.md) |
| Add or change a **Python analysis** | [`docs/contracts/step.md`](docs/contracts/step.md) |
| Know what goes in `config.json` | [`docs/contracts/config.schema.json`](docs/contracts/config.schema.json) |
| Know where a data file belongs | [`docs/contracts/assets.md`](docs/contracts/assets.md) |
| Work with **human-subject data** | [`docs/contracts/data-visibility.md`](docs/contracts/data-visibility.md) |
| Set up a new study | [`docs/contracts/case.md`](docs/contracts/case.md) |
| Check whether a study's data is sound | [`packages/dims-notebooks/`](packages/dims-notebooks/) |
| Understand how it all fits | [`docs/architecture.md`](docs/architecture.md) |
| Contribute as an **automated agent** | [`AGENTS.md`](AGENTS.md) |

### The five rules

1. **One copy of the code.** It lives here. Case repos hold `config.json`, data
   and a pinned copy of this core — never edited by hand. If you find yourself
   fixing the same bug twice, stop: you are in the wrong repo.
2. **Everything self-registers.** Tabs and analyses are discovered, not listed.
   Adding one must not require editing an existing file. If it does, the
   contract is wrong — fix the contract, not your feature.
3. **Style through CSS custom properties only** (`var(--text)`, `var(--accent)`).
   Never read the host's JS theme object; it is initialised after tabs load.
4. **Assume the data is private** until `dims-case.json` says otherwise. Never
   commit anything under `assets/`, and never move data content into an external
   service — an issue, a prompt, a hosted page.
5. **Verify by running it.** Every contract ends with an acceptance check that
   does not require reading any other file.

### Tuning belongs in config

If a study needs a different parameter, it goes in `config.json` under
`analysis`, not in a copy of the script. One fork previously maintained its own
version of an entire analysis in order to change two numbers — and that copy is
why a correctness fix could not travel for months.

### Picking up work

Issues labelled **`agent-ready`** are self-contained: they name the files, link
the contract, and state the acceptance check. Start there. An issue without
those three things is not ready — ask for them rather than guessing.

Labels: `area:core|tabs|analysis|builder|docs`, `type:bug|feat|chore`.

### House style

- Match the surrounding code. There is no build step and no bundler, by design:
  a researcher must be able to open a dashboard from a plain file server.
- Comment *why*, not *what*. The comments that earn their place here explain a
  decision or a trap, and the best of them carry a measurement.

## Licence & citation

MIT. A `CITATION.cff` will be added once the DIMS methods paper is published.
