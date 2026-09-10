# The cross-effector network

One picture of who is coupled with whom, following the playhead. Each **node** is
a measure; each **edge** is the wavelet coherence between two measures over the
window around the current moment. Move the playhead and the picture changes.

It is a view of the cross-wavelet analysis, not a separate one. Everything it
draws comes from `assets/crosswavelet/{video}_crosswavelet_data.json`, so an
edge exists only where [`include_crosswavelet`](../analyses/crosswavelet.md) asked
for that pair. **A pair you did not ask for is a missing edge, and nothing says
so** — the two nodes are still drawn, with nothing between them.

- Tab id `network`, gated by `include_network`.
- Needs the cross-wavelet analysis, and needs its coherence chance level.
- Reads nothing else: no raw signal, no config beyond `include_network` — except
  the raw series for the co-activity figure below, and the **Window Size**
  control, seeded from `defaultWindowSize`, for how wide "the moment" is.

The window is the playhead ± half of the **Window Size** control, which starts
at `defaultWindowSize` (5 s unless the study says otherwise) and follows the
control from then on, and a **whole recording** toggle above the picture
switches to averaging over everything, for when you want the study rather than
the moment.

## Reading an edge

Four things are drawn on one line, and they answer different questions.

| channel | means |
|---|---|
| **thickness** | mean coherence over the window and the period band — but *relative to the other visible edges*, not absolute |
| **solid or dashed** | solid where the coherence is above chance in more than 15 % of tested cells; dashed where it is not |
| **fading** | how much of the window both measures were actually moving for |
| **colour** | nothing, except the one edge you have selected |

**Thickness is relative on purpose.** The width scale pivots on the mean of the
currently visible above-chance edges, so the picture answers "which of these
couplings is strongest here" rather than "what is the absolute number" — which
is what the tooltip is for. It also means the same edge can look different after
you hide another one. The "width sensitivity" slider controls how hard the scale
pushes.

**Dashed means the measurement said nothing.** An edge is called real when more
than 15 % of its tested cells beat the 95 % chance level (`REAL = 0.15` in
`network.js`). Not 5 % plus a whisker: the fraction is itself an estimate, and a
threshold sitting on the chance level turns half of the at-chance edges solid.

There is a third verdict. An edge whose payload carries no chance level at all is
**untestable** — drawn, but its tooltip says the value cannot be tested and names
the fix (`analysis.crosswavelet.mcCount`, then rebuild). The tab counts them and
says how many, rather than letting an untested picture pass for a tested one.

**Every edge's numbers are in its tooltip**: the pair, the mean coherence, the
period band it was averaged over, the share of tested cells above chance and how
many cells that was, and what independence would have given (about 5 %).

The widths themselves run from `MIN_WIDTH = 1.5` px at the bottom of the visible
range to `MAX_WIDTH = 16` px at the top.

### The controls above the picture

| control | what it does |
|---|---|
| **whole recording** | averages every edge over the entire session instead of the window at the playhead |
| **Period band (s)** | the shortest and longest period each edge is averaged over. **This changes the answer**, not its presentation: it selects which cells enter both the mean and the significance fraction |
| **Width sensitivity** | how hard the relative width scale pushes. Presentation only |
| **one checkbox per pair** | hides an edge. Fifteen edges is a lot to read at once, and hiding some also re-pivots the width scale, because it pivots on what is visible |

### It needs a chance level to say anything at all

Coherence does not sit at zero when there is no relationship — two unrelated
signals score around 0.25, not 0. So a network of raw coherence values draws
at-chance noise as findings and looks entirely convincing doing it.

Switching the network on therefore switches on the Monte Carlo null at 100
surrogates, because the network is the only thing that reads it. Without it
every edge is `untestable` and the tab says so rather than guessing. The null,
and what it assumes, is documented under
[cross-wavelet](../analyses/crosswavelet.md).

## Co-activity: the faded edges

Coherence is amplitude-normalised by design. A tiny shared tremor counts exactly
as much as a large shared movement — which is right for "is the timing related"
and a liability for "are these two moving together", especially when both
measures are tracked from the same video and their jitter has shared sources.

So every edge also reports **the share of the window in which both measures were
active**, where a measure counts as active above 10 % of its own 95th percentile.
The 95th rather than the maximum, so one tracking glitch does not set the scale
for a whole recording.

Three things to know about that number:

- **It assumes near-zero means "not moving"** — a speed, or another magnitude.
  On a position channel, or anything centred on zero, it is meaningless. This is
  the one thing to check before trusting it.
- **It fades the edge.** Below a quarter of the window, the edge is drawn faint
  and the tooltip says *computed mostly from stillness; treat with care*. It
  never changes a coherence value, but it does change the picture.
- **Nothing is not zero.** When the raw series are not loaded the figure is
  omitted entirely rather than reported as 0, because "we did not measure this"
  and "they were still" are different statements.

## Clicking an edge: the detail figure

Selecting an edge does two things. It colours that line — the only use of colour
in the picture, so "selected" reads as a state rather than as another
measurement — and it draws **that pair's cross-wavelet figure underneath the
diagram**.

The detail figure is of a moment too, and its window follows the playhead. It is
drawn once, when the edge is selected, and afterwards only the shaded window is
moved: two answers to "which moment am I looking at" on one screen, where the
wrong one has a box drawn round it, is worse than one.

An edge can be selected whose pair has no cross-wavelet payload loaded in the
dashboard — the tab says so in the panel rather than drawing an empty figure.

## Where the nodes go

Two layouts, chosen with `layout`:

- **`columns`** (the default) — one column per group, members spread down it.
- **`figure`** — one human figure per group, with each measure on the body part
  it belongs to: `head`, `nose`, `lefthand`, `righthand`, `hand`, `torso`, `hip`,
  `foot`. Anything with no part is stacked beside the figure rather than dropped.

Neither layout is force-directed, deliberately: a force layout moves nodes
between frames, and this picture is read by comparing one moment with another.

## Building it in the wizard

The no-code builder draws this diagram in step 4 and asks you to fill it in,
which is the same decision as writing the config below by hand.

- **Add a person** for each figure you want, and name it. That is a `group`.
  One is enough: a network of a single body's own effectors — hands with head,
  left with right — is a whole network, and the tab centres the lone figure.
  Be aware that the "above chance in more than 15% of cells" threshold was
  chosen against between-person data; whether it reads the same way within one
  body is an open question rather than a settled one.
- **Click an empty circle** — head, either hand, torso, hip or foot — and pick a
  time series from the list. That is one `effectors` entry, and the node takes
  the spot's own name as its `label`: *Left hand*, *Head*. Real measure names
  are long enough that neighbouring nodes overlap into a smear, here and in the
  dashboard; the full name stays in the node's tooltip. The picker closes on
  Escape or a click outside it, without placing anything.
- **Drag from one placed node to another** to ask for the coupling between them.
  A dashed line follows the pointer; releasing on the second node makes the pair.
  Clicking the two in turn does the same, and draws the same line while you are
  between clicks. Escape, or releasing on empty space, abandons it.
- That line is one `include_crosswavelet` pair, which is what the tab turns into
  an edge; without it two nodes are simply two nodes. **The same pairs are chips
  in the cross-wavelet block above, and the two are one list** — either view
  edits it and both redraw. So a pair can be asked for without ever touching the
  diagram, and a pair whose measures are not both placed is selected but not
  drawn (the summary line under the chips says how many are in each state).
- The `×` on a node takes it back off. Its lines go with it, because a line
  needs two placed endpoints — but the pairs stay selected: where a measure sat
  on a body is not whether to analyse it.

Choosing the figure layout is not a separate step: placing anything on a body
means `layout: "figure"`, because a body diagram that configured a column chart
would be a lie.

**An existing study opens already filled in.** Every study written before
`effectors` existed says all of this by naming its measures
`teacher_righthandspeed`, so the wizard runs the same inference the tab runs —
the group's regular expression for the person, a body-part token in what is left
of the name for the spot — and shows you the result, saying that it guessed.
Pressing Next writes it out in the explicit form. The two render identically;
that is asserted by a test, because a migration that quietly moved a node would
be worse than no migration.

## Saying which series is which node

By default the tab infers everything about a node from its name — the group from
a regular expression, the label by deleting that expression, the body part from a
token found somewhere inside what is left. That works when a study encodes person,
part and quantity in one string:

```jsonc
"include_network": {
  "groups": [
    { "label": "Teacher", "match": "^teacher", "color": "#e84393" },
    { "label": "Student", "match": "^student", "color": "#00b894" }
  ],
  "layout": "figure"
}
```

…with measures called `teacher_righthandspeed` and `student_nosespeed`. It says
nothing useful about a study whose measures are called `bodysync` and
`neuralsync`: they match no group and contain no body part, so every measure
lands in one undifferentiated column.

**`effectors` says it outright instead.**

```jsonc
"include_network": {
  "groups": [
    { "label": "Teacher", "color": "#e84393" },
    { "label": "Student", "color": "#00b894" }
  ],
  "effectors": [
    { "series": "teacher_righthandspeed", "group": "Teacher",
      "label": "Right hand", "part": "righthand" },
    { "series": "teacher_nosespeed", "group": "Teacher",
      "label": "Head", "part": "head" },
    { "series": "bodysync", "group": "Student",
      "label": "Body", "x": 0.72, "y": 0.40 }
  ],
  "layout": "figure",
  "band": [0.0, 12.0]
}
```

| field | what it is |
|---|---|
| `series` | the data type, exactly as in `dataTypes` and in `assets/timeseries/{video}_{series}.csv` |
| `label` | what to draw under the node. Defaults to `series` |
| `group` | the `label` of one of the groups above — no regex involved |
| `part` | where on the figure it sits. Ignored by the `columns` layout |
| `x`, `y` | position as a **fraction of the chart**, 0 to 1, overriding `part` |

When `effectors` is given, a group needs no `match` — it is referenced by label.
When it is absent, nothing changes: the inference above is exactly what it was.

**`series` must stay a real data type name**, not a display name. The tab looks
the raw series up by that name to compute the co-activity figure above; a label
here would cost every edge that line, silently. That is what `label` is for.

**`x` and `y` are fractions, not pixels.** The chart's own dimensions are private
constants of the tab that have been retuned before, and a config written in raw
units would drift the day one of them moves. In the `figure` layout, omitting
`x` keeps the node on its own figure's centre line — which is the only way to say
"on this person, lower down", because an explicit `x` is absolute and does not
follow a figure when a third group is added.

### What happens when a declaration and the data disagree

Both directions are drawn rather than silently resolved, because both are
questions only the study can answer:

- **A declared effector that appears in no cross-wavelet pair** gets a node with
  no edges. You asked for it and the analysis does not cover it.
- **A measure that appears in a pair and that no effector declares** gets a node
  in a trailing `Other` group, exactly as an unmatched name does.
- **An effector naming a group that no group defines** is a typo, not an
  instruction to invent a column, so it also lands in `Other`.

The wizard checks these before it writes a study: a `series` with no CSV and a
duplicated `series` are errors; an unknown `part` and an undefined `group` are
warnings.

## Where the drawing lives

The body — its coordinate space, its six places, the aliases for their names, and
the lines that make a figure — is
[`packages/dims-tabs/figure-geometry.js`](../../packages/dims-tabs/figure-geometry.js).

**To move a body part, change it there.** Two things draw that figure and they
have to agree to the pixel, because what you arrange in the wizard is what the
dashboard draws:

| | reads it from |
|---|---|
| this tab (`network.js`) | `vendor/dims-tabs/figure-geometry.js`, beside it |
| the wizard's step 4 diagram | the DIMS checkout, served at `/vendor/figure-geometry.js` |

They used to be two copies kept identical by hand, with a comment in the wizard
saying so — and a third copy of the body-token list elsewhere again. They agreed
until they did not: both drew each arm to the hand on the *opposite* side, so
every figure had its arms crossed over its chest.

A study keeps the copy under its own `vendor/dims-tabs/` until `dims-case sync`,
which refreshes both the vendored directory and the `index.html` that loads it.
So a change here reaches the wizard at once and a built study when it syncs —
which is what vendoring is for.

The file exports one object, `window.DIMS_FIGURE`: the constants, `SPOTS`,
`ALIASES`, `BODY_TOKENS`, `spotOf`, `bodyPart`, `spot`, `positions(cx)`,
`personCx(index, total)` and `appendFigure(svg, {cx, color, el})` — which takes
the caller's element-maker, because the two consumers each have one already.

## The rest of the config

| key | what it does |
|---|---|
| `groups` | how the measures divide. `label`, an optional `color`, and a `match` regex when you are not declaring effectors. The wizard writes no `match` of its own; it carries one through if a study already had it |
| `band` | period band in seconds, `[low, high]`, to average each edge over. **This changes the answer**, not its presentation — it selects which periods enter both the mean and the significance fraction |
| `layout` | `columns` or `figure` |

`include_network: true` means "on, with everything inferred".

The full shape, with every constraint, is in
[`docs/contracts/config.schema.json`](../contracts/config.schema.json).
