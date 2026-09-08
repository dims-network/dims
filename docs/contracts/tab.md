# Contract: a dashboard tab

A tab is one JavaScript file. It registers itself. The host never lists tabs,
and adding one must not require editing any other file.

Tabs live in one of two places:

- **`packages/dims-tabs/`** — tabs that make sense for more than one study, and
  ship with the core.
- **`tabs/` inside a case repo** — tabs that belong to *that study*. ORTHO's
  trajectory view is the example: it draws a background image of the physical
  play space and this study's own path geometry, which mean nothing anywhere
  else. `dims-case` lists them in `index.html` and preserves that list when the
  core is refreshed.

The contract is identical either way, which is the point: a study can add a
view without touching, or waiting for, the core.

Built-in tabs use this same API — timeseries, RQA, cross-RQA, cross-wavelet and
ELAN are not special. That is deliberate: if this contract breaks, ELAN breaks
in the same commit, so it cannot rot unnoticed.

## The shape

```js
(function () {
  'use strict';

  window.DIMS.registerTab({
    id:    'trajectory',               // also names the pane: #trajectoryContainer
    label: 'Trajectories',             // the button text
    order: 50,                         // sort order; built-ins use 10..50

    // Shown only when this returns true. Read config, nothing else.
    gate(config) {
      return Array.isArray(config.include_crosswavelet)
          && config.include_crosswavelet.length >= 1;
    },

    // First time the tab is shown. May be async. `container` is your pane;
    // you own everything inside it and nothing outside it.
    async onActivate(app, container) { … },

    // Shown again, already activated. Cheap redraw.
    onUpdate(app) { … },

    // The playhead moved. Called for whichever tab is visible.
    onTimeUpdate(app, time, windowSize) { … },

    // A different video was selected. Drop cached data here.
    onVideoChange(app, videoID) { … },

    // Another tab was selected. Release anything expensive.
    onDeactivate(app) { … }
  });
})();
```

Only `id`, `label` and `onActivate` are required.

## What you may use from `app`

| | |
|---|---|
| `app.config` | the parsed `config.json` |
| `app.currentVideoID` | selected video |
| `app.lastClickedPoint` | current playhead time, seconds |
| `app.loadJSON(url)` / `app.loadCSV(url)` | fetch helpers; use these, not `fetch` |
| `app.onTimeChange(fn)` | follow the playhead even when your tab is not visible; returns an unsubscribe function |
| `window.DIMS.extendHost({...})` | attach rendering methods to the host, as the built-in tabs do |

Treat anything else on `app` as private. If you need something that is not here,
that is a request to extend this contract — say so in an issue rather than
reaching into internals.

## Rules

1. **Load after `dims-core.js`, before `DOMContentLoaded`.** The host defines
   the registry; your file registers into it. Registering after the app has
   been constructed is too late and is ignored.
2. **A duplicate `id` is refused**, so you cannot shadow a built-in tab by
   registering over it. Pick a distinct one.
3. **Style only with CSS custom properties** — `var(--text)`, `var(--muted)`,
   `var(--panel)`, `var(--accent)`. Never read the host's JS theme object: it is
   a module-level variable initialised after your file runs, so it is not there
   when you need it. Tabs that follow this rule survive theme switches with no
   host support at all.
4. **Stay inside your container.** Do not touch other panes, and do not add
   controls to the header directly — declare them and let the host place them.
5. **Load data lazily,** in `onActivate`, not at registration.
6. **Fail visibly, not fatally.** A gate that throws hides only your tab;
   the others carry on. If your data is missing, render a short
   explanation into your container. Never throw out of a hook.

## Acceptance

- Your tab appears when `gate()` passes and is absent when it does not.
- Deleting your file removes the tab and breaks nothing else.
- Switching theme leaves it readable, with no code of yours running.
- Moving the playhead updates it while it is the visible tab.
