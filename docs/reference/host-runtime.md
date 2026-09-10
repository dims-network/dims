# The host runtime

How the video, the time slider and every tab stay on one time axis, and what the
host does around them. This is the page for someone writing a tab or debugging why
a panel is out of step; the API a tab calls is
[`dims-api.md`](dims-api.md), and the rules it must follow are
[`contracts/tab.md`](../contracts/tab.md).

There is no framework and no bundler. Two globals do all of it:

| global | is |
|---|---|
| `window.DIMS` | the registry and the payload helpers — see [`dims-api.md`](dims-api.md) |
| `window.dimsApp` | the single `DIMSApp` instance, created on `DOMContentLoaded` |

`DIMS._appProto` points at `DIMSApp.prototype`, which is how `extendHost` reaches
the class from a tab file that never sees it.

## The shared time axis

**One function moves everything: `handleTimeClick(time)`.** Every click handler in
every tab calls it, the slider calls it, and nothing else sets the playhead.

It does six things, in this order:

1. Stores `time` on `app.lastClickedPoint`.
2. Reads the window width from `#windowSize`, defaulting to 5 seconds.
3. **Calls `plotTimeseries` directly.**
4. Calls `updateVideos(time, windowSize)`.
5. Calls `updateTranscript(time, windowSize)`.
6. **Calls `emitTimeChange(time, windowSize)`** — the bus.
7. Writes the selected time and window into the page's `#status` line.

Step 3 is why [the time series tab](../tabs/timeseries.md) registers no
`onTimeUpdate` hook: it is redrawn by name, before the bus runs at all. It is the
one tab the host knows about by name, and it is a leftover rather than a design —
every other tab is reached only through step 6.

### The bus

```js
emitTimeChange(time, windowSize)
```

Two audiences, in order:

1. **The visible tab's `onTimeUpdate`**, if it has one. First refusal, because it
   is the one on screen.
2. **Every subscriber registered through `onTimeChange(fn)`**, tab or not.

Each call is wrapped in its own `try`/`catch` and logged with the tab's id, so one
tab throwing cannot stop the tabs after it or break the bus.

This replaced an `if`/`else` chain that named every tab. That chain meant adding a
tab required editing the host, which was the single biggest obstacle to tabs being
separable at all.

### `onTimeChange(fn) → unsubscribe`

Subscribe to the playhead. Returns a function that removes the subscription;
calling it with a non-function returns a no-op unsubscribe rather than throwing.

**This is the only way for a hidden tab to follow the playhead**, since
`onTimeUpdate` reaches the visible tab alone.

## The slider

`createTimeSlider(minTime, maxTime, onChange)` builds a plain
`<input type="range">` into `#timeSlider` with a step of **0.1 s** and a readout
underneath reading `Time: 12.3s / 240.0s`.

Its bounds are the minimum and maximum `Time` across every dataset loaded for the
recording — not the video's duration. **A time series shorter than its video
therefore produces a slider that cannot reach the end of the recording**, which is
one of the ways a duration mismatch shows itself.

Its `input` event calls `handleTimeClick`, so dragging goes through exactly the
same path as clicking a plot.

## The video is a sink, never a source

`updateVideos(clickTime, windowSize)` renders two React components into
`#fullVideoContainer` and `#segmentVideoContainer`. The second is given
`startTime = max(0, t - windowSize/2)` and `endTime = t + windowSize/2`;
`video-component.js` seeks to `startTime` once metadata has loaded, and on reaching
`endTime` it **pauses and rewinds** to `startTime` — it does not loop on playing.

**Nothing wires the video's own `timeupdate` back into the bus.** Playing the
video does not move the playhead, and the other tabs do not follow it. Time flows
one way: from a click or the slider, out to the video. If you expected scrubbing
the video to drive the dashboard, it does not, and that is deliberate rather than
missing.

Should the React render fail, the **full** video falls back to a plain `<video
controls>` element with the same source. The segment video has no such fallback —
its failure is logged and its container is left empty.

### Choosing the file

`buildVideoSrc()` resolves `videoSrcTemplate`, replacing `{videoID}` and
`{persp}`. With no template configured the result is exactly
`assets/videos/{videoID}.mp4`.

With a template and no perspective chosen, it picks the first angle that exists
**for that recording** — `videoPerspectives[videoID]` — before falling back to the
first entry in `perspectives`. Not every session has every angle, because
recordings fail.

If neither resolves an angle, control falls through to
`fallbackVideoSrcTemplate` — so **the configured `videoSrcTemplate` is dropped
entirely** rather than being filled with an empty `{persp}`. That is usually what
you want and is worth knowing when a video silently resolves to the wrong path.

## Tab lifecycle

- **`setupTabs()`** filters `DIMS._tabs` by each tab's `gate(config)`, sorts by
  `order` (a missing or null `order` sorts as **100**), and creates one
  `.plot-pane` per tab with a minimum height of 800 px. A gate that throws hides
  only its own tab.
  - The slider and the tab bar are wrapped in a single `#stickyBar` so they pin to
    the top together while scrolling.
  - **With only one tab the bar is hidden entirely**, on the grounds that a single
    tab is no choice.
- **`paneIdFor(tab)`** returns the tab's own `containerId` when it sets one, and
  otherwise `{id}Container`. Two built-ins set it explicitly to keep ids that other
  code already depends on: `plotContainer` and `crossWaveletContainer`.
- **`switchTab(name)`** calls the previous tab's `onDeactivate`, then this tab's
  `onActivate` **once** — guarded by an internal `_activated` flag — and
  `onUpdate` on every later switch, then resizes the figures in the new pane.
- **`loadVideoData(videoID)`** clears every `_activated` flag, calls
  `onVideoChange` on every tab **the gate let through** (not on tabs the config
  excluded), reloads the CSVs and transcript,
  resets the payload caches, rebuilds the slider, and re-enters the visible tab.

### What a video switch clears, and what it does not

`_resetTabCaches()` nulls `rqaData`, `crossWaveletData`, `crqaData` and
`elanData`. **`elanSelectedTiers` is deliberately not in it**, and a comment there
explains why: which tiers someone asked to see is a choice they made, not data
fetched from a payload, so a re-render for a theme change must not discard it.

**That intent is not achieved.** `loadVideoData` clears `elanSelectedTiers`
unconditionally, a couple of lines after calling `_resetTabCaches`, and a theme
change reaches it — `applyTheme` calls `rerenderAll`, which calls `loadVideoData`
for the *same* recording. So the selection is lost on a theme switch, exactly as
the comment says it must not be. The unit test that covers this asserts
synchronously immediately after `rerenderAll()`, before the `await` inside
`loadVideoData` resolves, so it passes without exercising the behaviour. Filed as
a defect; documented from the user's side on
[the ELAN tab page](../tabs/elan.md).

## Figures in hidden panes

Two functions exist for one Plotly behaviour: **a figure drawn while its pane was
`display:none` has no width to measure, so it keeps whatever size it had and never
notices the pane reappearing.** The symptom is a plot that comes back the wrong
size and stays wrong until something forces a relayout — which is why dragging the
slider used to "repair" it. The redraw was the fix, not the slider.

- **`resizePlotsIn(root)`** resizes every Plotly figure under `root`, on the next
  animation frame because `display:block` has only just been set and there is no
  layout yet this frame. It checks **the root itself** as well as its descendants:
  `querySelectorAll` walks descendants only, and the time series tab draws straight
  into `#plotContainer`, which *is* its pane — the first version of this shipped
  with that hole and fixed every tab except the one people noticed. Figures that
  have been removed, or never finished drawing, are skipped rather than failing a
  tab switch.
- **`watchViewportSize()`** resizes the visible pane 150 ms after the window stops
  changing size. Debounced because a relayout is not cheap and a drag fires
  continuously.

## Themes

Two themes, `aurora` and `midnight`, chosen from `#themeSelect` and remembered in
`localStorage` under `dims-theme`. `readTheme()` reads the concrete values out of
the CSS custom properties on `:root`, so the palette is defined in
`css/theme.css` and not in JavaScript.

A theme change swaps the logo and calls `rerenderAll()`, which resets the payload
caches and re-enters the current tab — which is why a tab must build its colours
at draw time through `DIMS.theme()` rather than capturing them once.

## Boot

On `DOMContentLoaded`, before constructing anything, the host checks two lists and
**stops** if either is short — logging to the console *and* raising a browser
`alert` that names exactly what is missing, rather than throwing somewhere later
where the cause is unrecoverable:

| checked | must exist |
|---|---|
| DOM ids | `status`, `videoSelect`, `windowSize`, `plotContainer`, `fullVideoContainer`, `segmentVideoContainer` |
| globals | `React`, `ReactDOM`, `Plotly`, `Papa` (PapaParse), `TimeRangeVideo` |

If you are staring at an alert listing a missing dependency, the cause is almost
always script order or a CDN that did not load — see the order below.

Script order in a built study is the configuration, and it is set by the scaffold's
`index.html`: `video-component.js`, then `dims-core.js`, then
`figure-geometry.js` — **which must precede `network.js`** — then the tab files,
then the study's own tabs between the `study-owned tabs` markers.

## Where it lives

[`packages/dims-core/dims-core.js`](../../packages/dims-core/dims-core.js) and
[`video-component.js`](../../packages/dims-core/video-component.js) beside it.
Both are vendored into every study as `vendor/dims-core/`.
