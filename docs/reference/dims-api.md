# `window.DIMS` — the browser API

Everything a tab is allowed to use from the dashboard host, and the only stable
surface the frontend exposes. A study's own tab file may rely on what is on this
page; anything else it finds on the page is private and may move.

The contract a tab must satisfy — and its acceptance checks — is
[`contracts/tab.md`](../contracts/tab.md). This page is the reference for the
functions that contract refers to.

`window.DIMS` is created by `dims-core.js` before any tab file runs. It is created
with `window.DIMS || {…}`, so a page that defines it earlier keeps its own object.

## Constants

### `DIMS.PAYLOAD_VERSION`

`2`. The analysis payload format this build of the dashboard reads. It is
deliberately **not** the release number — release numbering has already changed
once, and the payload format has its own life.

The Python side declares the same number independently, in
`dims_analysis/common/arrays.py`. **Nothing checks that the two agree**: no test in
the repository compares them, so the constant that decides whether a dashboard can
read a payload is duplicated across two languages on trust. Filed as a defect.

## Reading a payload

### `DIMS.payloadProblem(payload, what) → string | null`

Returns `null` when the payload is readable, and otherwise a complete sentence
naming the fix. `what` is a noun phrase for the message — `'RQA output'`,
`'cross-wavelet output'`.

Call it immediately after loading, before touching any field:

```js
const problem = window.DIMS.payloadProblem(data, 'RQA output');
if (problem) { this.showError(problem); return; }
```

Three cases, three different messages:

| payload version | message says |
|---|---|
| missing entirely | written by an older core; rebuild with `python build_assets.py` |
| greater than `PAYLOAD_VERSION` | written by a newer core; update the vendored core, or rebuild against the pinned one |
| lower | states both numbers and says to rebuild |

The failure this exists to prevent is specific: a study bumps `dimsCore` without
rebuilding its assets, every analysis panel comes up blank, and **an empty panel
is indistinguishable from having no data at all**. Saying which it is costs one
call.

### `DIMS.decodeArray(field) → field | number[] | number[][]`

Large arrays travel base64-encoded so that a study ships one file format rather
than a JSON for the browser and an `.npz` beside it. Two encodings, each naming
itself in the object:

| shape in the payload | means |
|---|---|
| `{encoding: 'bitmap-b64', rows, cols, data}` | a recurrence matrix, one bit per cell |
| `{encoding: 'f32-b64', shape, data}` | a coherence, power or phase grid |

**Anything else passes through untouched.** A field that is already a plain array,
a scalar, or an object with no `encoding` comes back as it went in — so a tab can
call `decodeArray` on a field without first knowing whether it grew large enough
to have been encoded.

An encoding this build does not recognise **throws**, with the name in the
message. That is deliberate: silence here is how a panel ends up empty with
nothing in the console.

Two decoding details a tab author does not have to care about but a payload author
does:

- **Bitmaps** are most-significant-bit first, and each row starts on a byte
  boundary — so a row of `cols` bits occupies `(cols + 7) >> 3` bytes. Returned
  dense, because that is what Plotly wants.
- **float32 is little-endian, stated rather than inherited.** `DataView` defaults
  to big-endian and numpy follows the platform, so neither default was safe to
  rely on. **`NaN` decodes to `null`**, which Plotly reads as a gap — and a gap is
  what these grids mean by it: outside the cone of influence, or a band where
  neither signal has power.

Both decoders check the byte count against the declared shape and throw naming
both numbers if they disagree. A grid of more than two dimensions throws rather
than being flattened, on the grounds that it is not something a tab draws.

## Registering a tab

### `DIMS.registerTab(def)`

Adds a tab. Call it at the top level of your tab file, inside its IIFE, after
`dims-core.js` has loaded and before `DOMContentLoaded` — **once the app has been
constructed it is too late and the call is ignored.**

```js
window.DIMS.registerTab({
  id: 'trajectory',            // required, unique
  label: 'Trajectory',         // shown on the button; falls back to id
  order: 25,                   // sort position; missing or null sorts as 100
  containerId: 'myPane',       // optional; default is `${id}Container`
  gate: cfg => cfg.include_trajectory === true,
  async onActivate(app, container) { /* … */ },
  onUpdate(app, container) { /* … */ },
  onTimeUpdate(app, time, windowSize) { /* … */ },
  onVideoChange(app, videoID) { /* … */ },
  onDeactivate(app) { /* … */ },
});
```

It **refuses two things, loudly on the console and without throwing**: a `def`
with no `id`, and an `id` that is already registered. The second matters more than
it looks. A study that owns a tab file whose id later becomes a built-in keeps a
file that registers nothing and does nothing, with no symptom on the page — which
is why `dims-case sync` and `dims-case check` report shadowed tabs. See
[the `dims-case` reference](cli/dims-case.md).

### The hooks, and when each fires

| hook | when |
|---|---|
| `gate(config)` | once, during setup. A gate that **throws** hides that tab and is logged; it does not break the others |
| `onActivate(app, container)` | the first time the tab is shown. May be `async`. Load your data here, not at registration |
| `onUpdate(app, container)` | every later time it is shown |
| `onTimeUpdate(app, time, windowSize)` | the playhead moved — **visible tab only** |
| `onVideoChange(app, videoID)` | the recording changed. Fires on every tab **the gate let through**, visible or not — a gated-out tab never receives it. Drop your cached payload here |
| `onDeactivate(app)` | you are being switched away from |

Every hook is called inside a `try`/`catch`: one tab throwing is logged with its
id and cannot take down the bus or the other tabs. Do not rely on that — a tab
that throws out of a hook is a bug — but it is why one broken tab does not blank
the dashboard.

**`onTimeUpdate` reaching only the visible tab is the important asymmetry.** A tab
that must follow the playhead while hidden subscribes instead, with
`app.onTimeChange(fn)`.

## Extending the host

### `DIMS.extendHost(methods)`

`Object.assign` onto the host's prototype. This is how a tab whose rendering lives
in its own file attaches that rendering to the app so other code can call it by
name — `plotTimeseries`, `updateCrossWaveletWindow`.

```js
window.DIMS.extendHost({
  loadMyData(videoID) { /* `this` is the app */ },
});
```

It is explicit rather than magic **so that it can be grepped for**. Called before
`dims-core.js` has defined the host, it logs an error and does nothing.

Two consequences worth stating: the methods share one namespace, so a name
collision silently overwrites; and a method added this way becomes part of the
host for every tab, not just yours. The network tab depends on exactly that — it
calls `createCrossWaveletPlot` and `updateCrossWaveletWindow`, which the
cross-wavelet tab installed.

## Theming

### `DIMS.theme() → object`

The current theme's concrete colour values, read at call time.

**This is for plotting libraries only.** Tabs style their own DOM with the CSS
custom properties in `css/theme.css`, which follow a theme switch on their own.
Plotly needs a literal colour in a layout object and cannot take a `var(--…)`
reference, which is the entire reason this exists.

Because it is read at call time, a layout rebuilt during a re-render picks up the
current theme. A colour captured once into a variable at file scope does not —
that is the mistake the accessor exists to make avoidable.

Keys in use across the shipped tabs: `font`, `paper`, `plot`, `grid`, `text`,
`muted`, `trace`, `highlight`, `highlightFill`.

## What a tab may use from `app`

The allowlist, from [`contracts/tab.md`](../contracts/tab.md):

| member | is |
|---|---|
| `app.config` | the study's `config.json`, parsed |
| `app.currentVideoID` | the recording on screen |
| `app.lastClickedPoint` | the playhead in seconds, or `null` |
| `app.loadJSON(url)` | fetch + parse. **Use this, not `fetch`** |
| `app.loadCSV(url)` | fetch + PapaParse, with the `Time` column normalised |
| `app.onTimeChange(fn)` | follow the playhead even while your tab is hidden; returns an unsubscribe function |
| `window.DIMS.extendHost({…})` | attach rendering methods to the host |

Treat anything else on `app` as private. If you need something not on the list,
that is a request to extend the contract — open an issue rather than reaching
into internals.

**Two things every built-in tab uses are missing from that list**, and you should
know it before you copy one:

- **`app.currentData`** — the loaded time series, as `[{name, data}]`. Read
  directly by the RQA, cross-RQA and cross-wavelet tabs, to match a measure to
  its colour. The time series tab does not read it: the host passes it in as an
  argument instead, and the network tab does not read it at all.
- **`app.handleTimeClick(time)`** — how a tab moves the playhead. The time series,
  ELAN and cross-wavelet tabs call it from their own click handlers; the two
  recurrence tabs reach it through the host's shared figure builder, and the
  network tab does not move the playhead at all.

Neither is private in practice and neither is going to move, but the contract has
not been updated to say so. Treat them as usable and expect the contract to catch
up.

For the machinery behind `handleTimeClick` and `onTimeChange` — the order things
happen in, and why the video is never a source of time — see
[the host runtime](host-runtime.md).
