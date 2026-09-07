# Contract: a dashboard tab

A tab is one JavaScript file in `packages/dims-tabs/`. It registers itself. The
host never lists tabs, and adding one must not require editing any other file.

Built-in tabs use this same API — timeseries, RQA, cross-RQA, cross-wavelet and
ELAN are not special. That is deliberate: if this contract breaks, ELAN breaks
in the same commit, so it cannot rot unnoticed.

## The shape

```js
(function () {
  'use strict';

  window.DIMS.registerTab({
    id:    'network',                  // also names the pane: #networkContainer
    label: 'Cross-Effector Network',   // the button text
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
| `app.onTimeChange(fn)` | subscribe to the playhead outside your tab's own hook |

Treat anything else on `app` as private. If you need something that is not here,
that is a request to extend this contract — say so in an issue rather than
reaching into internals.

## Rules

1. **Register before the host loads.** Your `<script>` runs before
   `dims-core.js`. Registering later is silently ignored.
2. **Style only with CSS custom properties** — `var(--text)`, `var(--muted)`,
   `var(--panel)`, `var(--accent)`. Never read the host's JS theme object: it is
   a module-level variable initialised after your file runs, so it is not there
   when you need it. Tabs that follow this rule survive theme switches with no
   host support at all.
3. **Stay inside your container.** Do not touch other panes, and do not add
   controls to the header directly — declare them and let the host place them.
4. **Load data lazily,** in `onActivate`, not at registration.
5. **Fail visibly, not fatally.** If your data is missing, render a short
   explanation into your container. Never throw out of a hook.

## Acceptance

- Your tab appears when `gate()` passes and is absent when it does not.
- Deleting your file removes the tab and breaks nothing else.
- Switching theme leaves it readable, with no code of yours running.
- Moving the playhead updates it while it is the visible tab.
