# How DIMS fits together

DIMS is one repository holding a browser frontend and a Python analysis package,
released together, and vendored into each study that uses them. **How that
versioning works — the pin, the vendoring, how a fix reaches a study — is
[its own page](versioning.md).** This one is about why the code is arranged the
way it is.

For how the running dashboard works — the time axis, the tab lifecycle, the
video — see [the host runtime](reference/host-runtime.md).

## Why a monorepo

Because the alternative was tried and failed measurably. The code lived in five
repositories that were supposed to stay in step by hand. They did not: three
disjoint git lineages, four different copies of the frontend ranging from 2136
to 2500 lines, and **no repository containing every feature**.

The wavelet coherence defect is the case that settles the argument. It was not
that one fork had the fix and the others lacked it — **all five shipped the wrong
measure, for months.** It smoothed the magnitude instead of the complex
cross-spectrum, so the field looked plausible and tracked signal power; only a
numerical check could find it, and there was no shared place to put one.

Propagation is now a version bump, not a merge.

## Why no build step

A dashboard has to open from a plain file server, years later, on a machine
nobody has maintained. Plain `<script>` tags and CSS custom properties survive
that; a bundler and a `node_modules` tree do not. This constrains the design and
is worth the constraint.

The constraint is not fully honoured yet: five libraries — React, ReactDOM,
Plotly, PapaParse, lodash — are still loaded from a CDN rather than vendored,
so a dashboard opened without a network is a blank page. That is
[dims#12](https://github.com/dims-network/dims/issues/12), and until it is
closed, "opens from a plain file server" means one with a network behind it.
This is the only place that caveat is stated in full; the pages that depend on
it link here.

## Why everything self-registers

Adding a tab or an analysis must not require editing a file that already works.
The runner this replaced hardcoded a list of three functions, so adding one
analysis meant edits in four separate files; the builder carried its own parallel
set of per-analysis booleans. That is exactly how forks came to have features that
could never be shared.

Built-in tabs use the same registry as third-party ones, so the extension point
cannot quietly rot: break it, and ELAN breaks with it.

## The layers

| | |
|---|---|
| **Producers** | mocap, EnvisionBox modules, any tool that emits a time series |
| **Analyses** | `dims-analysis` steps: RQA, cross-RQA, cross-wavelet, … |
| **Presentation** | `dims-core` + `dims-tabs`, driven by `config.json` |
| **Cases** | one study each: config, data, a pinned core |

The seam between producers and DIMS is a **data contract, not an API**: a CSV
with a time column in seconds. That is why integrating an outside toolbox is a
unit conversion rather than a merge.
