# DIMS documentation

DIMS puts every signal from a recorded session on one timeline, beside the video
and transcript they came from, with the analyses that say how two signals relate.
Click a peak in a time series and the video jumps to the moment that produced it.

It is for researchers who **already have time-aligned measures** — motion
tracking, physiology, gaze codes, annotation tiers — and want to get from a
statistical pattern back to the raw record that produced it.

**What DIMS is not:** it is not a preprocessing pipeline. It does not clean
signals, estimate synchrony, or align clocks. It displays what you give it, which
means it displays a misaligned signal faithfully as a misaligned signal.

Every page below is written for one kind of reader. If you are new, start at the
tutorial and come back here.

---

## Start here

| | for |
|---|---|
| **[The tutorial](https://dims-network.github.io/tutorial.html)** | your first dashboard, in the no-code builder, with screenshots. Start here if you have never used DIMS |
| [The builder](builder/index.md) | what each of the wizard's seven steps asks and writes |
| [Getting started](getting-started.md) | the same journey from a terminal, with your own data |

## How do I…

| | |
|---|---|
| [Set up a study](contracts/case.md) | what a case repository contains and how it is laid out |
| [Put my files in the right place](contracts/assets.md) | the directory layout and the CSV rules |
| [Write `config.json`](reference/config.md) | every key, what reads it, and what it changes |
| [Work with human-subject data](contracts/data-visibility.md) | what `private` turns on, and how to keep recordings out of git |
| [Add a tab](contracts/tab.md) | one self-registering file |
| [Add an analysis](contracts/step.md) | one Python class |
| [Run the tests](reference/testing.md) | which suite lives where, and what CI checks |
| [Check my data is sound](https://github.com/dims-network/dims/tree/main/packages/dims-notebooks) | notebooks that look for the failures worth catching early |

## The tabs

What each panel shows, what it reads, and what it will not tell you.

| | |
|---|---|
| [Time series](tabs/timeseries.md) | every measure against time. Always present |
| [RQA](tabs/rqa.md) | where one signal returns to states it was in before |
| [Cross-RQA](tabs/crqa.md) | where two signals repeat each other, and after how long |
| [Cross-wavelet](tabs/crosswavelet.md) | which timescales two signals share, how strongly, and which leads |
| [Cross-effector network](tabs/network.md) | who is coupled with whom, following the playhead |
| [ELAN](tabs/elan.md) | your own annotation tiers on the same timeline |

## The analyses

What is computed, on what inputs, with which parameters — and how to read the
numbers without over-reading them.

| | |
|---|---|
| [Overview](analyses/index.md) | the three analyses compared, and the payload format they share |
| [RQA](analyses/rqa.md) | recurrence quantification. **Read the note on time-delay embedding** |
| [Cross-RQA](analyses/crqa.md) | cross-recurrence between a pair |
| [Cross-wavelet](analyses/crosswavelet.md) | the transform, and the four different significance levels |

## Reference

| | |
|---|---|
| [`config.json`](reference/config.md) | every key |
| [`dims-analysis`](reference/cli/dims-analysis.md) | run the analyses, list steps, check the manifest |
| [`dims-case`](reference/cli/dims-case.md) | create a study, vendor the core, verify the pin |
| [`dims-builder`](reference/cli/dims-builder.md) | start the wizard |
| [`window.DIMS`](reference/dims-api.md) | the browser API a tab may use |
| [The host runtime](reference/host-runtime.md) | the shared time axis, the tab lifecycle, the video |
| [`figure-geometry.js`](reference/figure-geometry.md) | the body the network is drawn on |
| [`dims_analysis.common`](reference/analysis-common.md) | the machinery the analysis steps share |
| [The builder's HTTP API](builder/api.md) | if you are working on the wizard itself |
| [Testing](reference/testing.md) | the suites and the CI jobs |
| [`config.schema.json`](contracts/config.schema.json) | the machine-readable config shape |

## Contracts

The rules a study, a tab, an analysis and its output must satisfy — each with the
failure that produced it.

| | |
|---|---|
| [A case](contracts/case.md) · [its assets](contracts/assets.md) · [its visibility](contracts/data-visibility.md) | what a study is |
| [A tab](contracts/tab.md) · [a step](contracts/step.md) | how to extend it |
| [Analysis output](contracts/analysis-output.md) | what a payload must contain, and why |

## Explanation

Read away from the keyboard.

| | |
|---|---|
| [How DIMS fits together](architecture.md) | why a monorepo, why no build step, why everything self-registers |
| [Versions, vendoring and the pin](versioning.md) | how one fix reaches every study, and why a study can be archived |

---

Everything here is also published at **<https://dims-network.github.io/>**, and
generated from this directory — so a page on the site and the file beside the code
are the same text.
