# dims-core

The host a dashboard is built on: config loading, the video element, the time
bus every tab shares, and the tab registry.

```
dims-core.js          the host: config, registry, time bus, layout
video-component.js    the video element and its seek/scrub behaviour
css/                  the design tokens tabs style themselves from
branding/             logos
test/                 jsdom tests (`node --test`) — not vendored into studies
```

## What it gives a tab

A tab never touches the DOM outside its own pane, never reads a file directly,
and never talks to another tab. Everything goes through the host:

- **the registry** — a tab self-registers; nothing lists tabs, so adding one
  edits no existing file
- **the time bus** — one current time, published by the video and subscribed to
  by every tab, so a click in one plot moves the video and every other plot
- **the config** — `config.json` as an object, already validated
- **CSS custom properties** — `var(--text)`, `var(--accent)` and the rest

The contract, with its acceptance checks, is
[`docs/contracts/tab.md`](../../docs/contracts/tab.md).

## Two rules that are not obvious

**Style the DOM through custom properties.** A colour written into a `style`
attribute is fixed when it is written and does not follow a theme switch; a
`var(--text)` does. `DIMS.theme()` is for handing concrete colour values to a
plotting library, which cannot read a CSS variable — not for styling elements.

**Plotly figures must be resized when their pane becomes visible.** A plot laid
out in a hidden pane has no width, and stays that size when the pane is shown.
`resizePlotsIn(root)` and `watchViewportSize()` handle both cases; a tab that
draws its own plots outside the standard container calls the former itself.

## Vendoring

This directory is copied into every study as `vendor/dims-core/`, minus
`test/`, `node_modules/` and Markdown. CI rebuilds that copy from the release
tag and compares byte for byte, so a study cannot carry an edited core — see
[`docs/contracts/case.md`](../../docs/contracts/case.md).

Never edit a study's `vendor/`. Fix it here and bump the pin.

## Tests

```sh
cd test && npm install && node --test
```
