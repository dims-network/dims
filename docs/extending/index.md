# Extending DIMS

DIMS is open source. Adding a tab, an analysis, or a feature doesn't require
a fork of the dashboard shell — a tab is one self-registering file and an
analysis is one Python class, both discovered rather than listed, so adding
either changes no existing file. This page is the map for doing either: the
contracts a tab, an analysis, or a study must satisfy; the APIs available to
code you add; the CLI and how to test a change; and how the pieces fit
together.

## Contracts

| | |
|---|---|
| [Writing a tab](../contracts/tab.md) | one self-registering file |
| [Writing an analysis](../contracts/step.md) | one Python class |
| [A study repository](../contracts/case.md) | what a study is |
| [config.json](../reference/config.md) | every key |
| [Asset layout](../contracts/assets.md) | the directory layout and the CSV rules |
| [Analysis output](../contracts/analysis-output.md) | what a payload must contain, and why |
| [Public and private data](../contracts/data-visibility.md) | what `private` turns on, and how to keep recordings out of git |

## APIs

| | |
|---|---|
| [window.DIMS](../reference/dims-api.md) | the browser API a tab may use |
| [The host runtime](../reference/host-runtime.md) | the shared time axis, the tab lifecycle, the video |
| [figure-geometry.js](../reference/figure-geometry.md) | the body the network is drawn on |
| [dims_analysis.common](../reference/analysis-common.md) | the machinery the analysis steps share |
| [The builder's HTTP API](../builder/api.md) | if you are working on the wizard itself |

## CLI & testing

| | |
|---|---|
| [dims-analysis](../reference/cli/dims-analysis.md) | run the analyses, list steps, check the manifest |
| [dims-case](../reference/cli/dims-case.md) | create a study, vendor the core, verify the pin |
| [dims-builder](../reference/cli/dims-builder.md) | start the wizard |
| [Testing](../reference/testing.md) | the suites and the CI jobs |

## Explanation

| | |
|---|---|
| [Architecture](../architecture.md) | why a monorepo, why no build step, why everything self-registers |
| [Versions, vendoring and the pin](../versioning.md) | how one fix reaches every study, and why a study can be archived |

If a study needs a different parameter, it belongs in `config.json` under
`analysis` — never in a copied script. Studies keep their data and their
`config.json`; the code lives here, once, and a study takes a fix by bumping
the version it pins.

## Where things live

```
packages/dims-core/          the page: config, video, the time bus, the tab registry
packages/dims-tabs/          every tab, one self-registering file each
packages/dims-analysis/      the analyses, a pip package
packages/dims-case/          creating a study and keeping its core honest
packages/dims-case-scaffold/ what a new study starts from
packages/dims-notebooks/     notebooks that check a study's data is sound
apps/builder/                the no-code wizard
tests/reference/             the analyses, checked against known answers
```
