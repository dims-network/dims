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
than 15 % of its tested cells beat the 95 % chance level. Not 5 % plus a
whisker: the fraction is itself an estimate, and a threshold sitting on the
chance level turns half of the at-chance edges solid.

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

## Where the nodes go

Two layouts, chosen with `layout`:

- **`columns`** (the default) — one column per group, members spread down it.
- **`figure`** — one human figure per group, with each measure on the body part
  it belongs to: `head`, `nose`, `lefthand`, `righthand`, `hand`, `torso`, `hip`,
  `foot`. Anything with no part is stacked beside the figure rather than dropped.

Neither layout is force-directed, deliberately: a force layout moves nodes
between frames, and this picture is read by comparing one moment with another.

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

## The rest of the config

| key | what it does |
|---|---|
| `groups` | how the measures divide. `label`, an optional `color`, and a `match` regex when you are not declaring effectors |
| `band` | period band in seconds, `[low, high]`, to average each edge over. **This changes the answer**, not its presentation — it selects which periods enter both the mean and the significance fraction |
| `layout` | `columns` or `figure` |

`include_network: true` means "on, with everything inferred".

The full shape, with every constraint, is in
[`docs/contracts/config.schema.json`](../contracts/config.schema.json).
