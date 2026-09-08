# DIMS

**Explore how people move, speak and act together.** DIMS turns recordings and
the time series taken from them — motion tracking, physiology, gaze codes,
anything sampled over time — into a dashboard you open in a browser: every
signal on one timeline, beside the video it came from, with the analyses that
say how two signals relate.

### See one

**<https://dims-network.github.io/case-demo/>** — a working dashboard with a
recording, its signals, and the analyses running on them. Click the timeline;
the video and every chart follow.

<sub>DIMS = Dynamic Interaction and Multimodal Signals.</sub>

## What you get

| tab | answers |
|---|---|
| **Time series** | what each signal did, next to the video at that moment |
| **Recurrence (RQA)** | where one signal returns to states it was in before |
| **Cross-recurrence** | where two signals repeat *each other*, and after how long |
| **Cross-wavelet & coherence** | which timescales two signals share, how strongly, and which leads |
| **Cross-effector network** | one picture of who is coupled with whom, moving with the playhead |
| **ELAN** | your own annotations, on the same timeline |

Coherence is measured against a chance level estimated by simulation, not read
off raw — two unrelated signals score about 0.25, not 0, so a number without
that comparison cannot be interpreted. The analyses follow Torrence & Compo
(1998) for the wavelet work; the constants taken from that paper are transcribed
in [`examples/reference/`](examples/reference/) and checked on synthetic signals
whose answers are known in advance.

## Build your own

You need Python 3.9 or newer. Nothing else — no build step, no bundler, no
account.

```sh
pip install "dims-network[builder]"
dims-builder
```

Your browser opens on a wizard. Point it at a folder, drop your files in — or
press **Load the example study** to see the whole path first — choose the
analyses, and it builds a dashboard, runs the analyses, and opens the result.

Prefer the command line?

```sh
pip install dims-network
dims-case new my-study            # a study, with its guards and a pinned core
cd my-study
# put your files in assets/, list them in config.json
python build_assets.py            # run the analyses
python serve.py                   # http://localhost:8000
```

Working with recordings of identifiable people? Say so when the study is
created. A private study keeps its data out of git through a commit hook, a push
hook and a CI check, and points at wherever the recordings actually live —
[`docs/contracts/data-visibility.md`](docs/contracts/data-visibility.md).

> Not on PyPI yet: `pip install -e .` from a checkout, or
> `pip install -e '.[builder]'` for the wizard. The distribution is called
> `dims-network` because `dims` is taken by an unrelated project.

## Documentation

Read the one page for the thing you are doing.

| | |
|---|---|
| From data to a running dashboard | [`docs/getting-started.md`](docs/getting-started.md) |
| What goes in `config.json` | [`docs/contracts/config.schema.json`](docs/contracts/config.schema.json) |
| Where each file belongs | [`docs/contracts/assets.md`](docs/contracts/assets.md) |
| How to read a coherence value | [`docs/coherence.md`](docs/coherence.md) |
| Working with human-subject data | [`docs/contracts/data-visibility.md`](docs/contracts/data-visibility.md) |
| Setting up a study | [`docs/contracts/case.md`](docs/contracts/case.md) |

Everything is also at **<https://dims-network.github.io/>**.

## Extending it

A tab is one self-registering file and an analysis is one Python class; both are
discovered rather than listed, so adding either changes no existing file.

| | |
|---|---|
| Add or change a **tab** | [`docs/contracts/tab.md`](docs/contracts/tab.md) |
| Add or change an **analysis** | [`docs/contracts/step.md`](docs/contracts/step.md) |
| What an analysis result must contain | [`docs/contracts/analysis-output.md`](docs/contracts/analysis-output.md) |
| How the pieces fit | [`docs/architecture.md`](docs/architecture.md) |
| Check a study's data is sound | [`packages/dims-notebooks/`](packages/dims-notebooks/) |

If a study needs a different parameter, it belongs in `config.json` under
`analysis` — never in a copied script. Studies keep their data and their
`config.json`; the code lives here, once, and a study takes a fix by bumping the
version it pins.

```
packages/dims-core/          the page: config, video, the time bus, the tab registry
packages/dims-tabs/          every tab, one self-registering file each
packages/dims-analysis/      the analyses, a pip package
packages/dims-case/          creating a study and keeping its core honest
packages/dims-case-scaffold/ what a new study starts from
apps/builder/                the no-code wizard
tests/reference/             the analyses, checked against known answers
```

## Licence & citation

MIT. A `CITATION.cff` will be added once the DIMS methods paper is published.
