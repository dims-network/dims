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
    status: 'Click a point to seek.',  // optional: the one-line hint shown
                                       // above the panes while your tab is
                                       // visible. The host writes it on every
                                       // switch, so it survives return visits
                                       // and cannot leak to another tab.

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

**The status line is the host's, not yours.** It is one element shared by every
tab. Declare `status` and the host shows it whenever your tab is the visible one;
call `app.showTabStatus()` to return to it after your own transient message, such
as one shown while loading. Writing `app.showStatus(...)` directly is for those
transient messages only — anything you leave there is what the reader sees on
whatever tab they open next.

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
3. **Style the DOM with CSS custom properties** — `var(--text)`, `var(--muted)`,
   `var(--panel)`, `var(--accent)`. A colour written into an element's `style`
   attribute is fixed at the moment it is written and does not follow a theme
   switch; a custom property does, with no host support at all.

   `DIMS.theme()` exists for the one case a custom property cannot serve: a
   plotting library that needs a concrete colour value rather than a CSS
   reference — a Plotly `layout.paper_bgcolor`, a `gridcolor`, a trace colour.
   Use it there and nowhere else. (An earlier version of this rule said the
   theme object was "initialised after your file runs, so it is not there when
   you need it". That was not true — it is a module-level variable set when
   `dims-core.js` loads, which is before any tab file — and a rule with a wrong
   reason is one people work around rather than follow.)
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
