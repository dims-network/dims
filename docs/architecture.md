# How DIMS fits together

```
                dims-network/dims          all the code, released as vX.Y.Z
                       │
        ┌──────────────┴──────────────┐
  vendor/ , pinned            dims-analysis, installed
  what the browser loads      what rebuilds the assets
  (bot PR; CI rebuilds it     (pip install -e ./dims —
   from the release tag)       not on PyPI yet)
        │                              │
   ┌────┴─────┬──────────────┐         └── used by every study, and by the builder
case-demo  case-ortho  case-karnatak
 (public)   (public)     (PRIVATE — data lives outside the repository)
```

Both halves move together and carry the same version number. A study's
`dims-case.json` names it once: it is the tag CI fetches to verify `vendor/`,
and it is the version of `dims-analysis` that produced the study's assets.

## Why a monorepo

Because the alternative was tried and failed measurably. The code lived in five
repositories that were supposed to stay in step by hand. They did not: three
disjoint git lineages, four different copies of the frontend ranging from 2136
to 2500 lines, and **no repository containing every feature**. One fork carried
the only correct wavelet coherence for months while the other four shipped a
version that tracked signal power instead — because there was no mechanism for a
fix to travel.

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

## Why everything self-registers

Adding a tab or an analysis must not require editing a file that already works.
Before this, adding one analysis to the builder meant edits in four separate
files, and adding a tab meant editing three regions of a 2000-line class — which
is exactly how two forks came to have features that could never be shared.

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
