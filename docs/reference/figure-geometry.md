# `figure-geometry.js` — the body, and the lines between

One definition of the human figure the [cross-effector network](../tabs/network.md)
is drawn on, and of the arcs that join its nodes. A plain script that hangs a
single object off `window`; no build step and no module system.

**Two things draw this body and they must agree to the pixel**, because what you
arrange in the wizard is what the dashboard draws:

| consumer | gets the file from |
|---|---|
| the dashboard's network tab (`network.js`, beside it) | `vendor/dims-tabs/`, copied wholesale by `dims-case` |
| the wizard's step 4 diagram (`builder.js`) | the DIMS checkout, served at `/vendor/figure-geometry.js` |

**The two figures on this page are drawn by this file**, published into the site
from `packages/dims-tabs/` and run in your browser — so they are the geometry
this release ships, not a drawing of it.

**To move a body part, change it here.** The number you change moves the node in
the wizard immediately, and in a built study at its next
[`dims-case sync`](cli/dims-case.md) — a study keeps its own vendored copy until
then, which is what vendoring is for.

## The coordinate space

Everything is in **viewBox units**, so it scales with the picture rather than with
the window. The network tab's viewBox is `0 0 1000 560`.

| constant | value | is |
|---|---|---|
| `VIEW_W` | 1000 | the diagram's viewBox width |
| `NODE_R` | 26 | node radius **in the wizard** |
| `TAB_NODE_R` | 12 | node radius **on the dashboard** |
| `HEAD_Y`, `HEAD_R` | 85, 30 | head centre and radius |
| `SHOULDER_Y`, `SHOULDER_DX` | 150, 60 | shoulder line |
| `TORSO_Y` | 235 | torso node |
| `HIP_Y`, `HIP_DX` | 330, 32 | hip line |
| `HAND_Y`, `HAND_DX` | 300, 100 | hand height and offset from the centre line |
| `FOOT_Y`, `FOOT_DX` | 545, 35 | foot height and offset |

**The two node radii are not an inconsistency.** The circle does two different
jobs. In the wizard it is a drop target: it has to be comfortably clickable, and
an empty one has to read as a place where something could go. On the dashboard it
is a dot at the end of a line, and *the line is the measurement* — the heaviest
edge the tab draws is 16 px, which a 52 px circle would swallow whole.

## Places

`SPOTS` — six places something can sit. `dx` is measured from the figure's centre
line, so a spot is positioned relative to whichever person it belongs to.

<div class="figure" id="fig-body"></div>

| `part` | label | `dx` | `y` |
|---|---|---|---|
| `head` | head | 0 | 85 |
| `righthand` | right hand | −100 | 300 |
| `lefthand` | left hand | +100 | 300 |
| `torso` | torso | 0 | 235 |
| `hip` | hip | 0 | 330 |
| `foot` | foot | 0 | 545 |

`ALIASES` — `{ nose: 'head', hand: 'lefthand' }`. Eight accepted names, six
places: two are older spellings for a place that already exists. Written once here
rather than inline in one consumer and mapped in the other.

`BODY_TOKENS` — the eight names ordered so that **a compound name is tested before
any name it contains**: `lefthand` and `righthand` come before `hand`, and `nose`
before `head` is irrelevant but harmless. (It is not strictly longest-first —
`righthand` follows the shorter `lefthand` — and it does not need to be; what
matters is that no token is swallowed by a substring of itself.) This is how a
study written before `effectors` existed still lands its
measures on a body: the part is read out of what is left of a measure's name once
the group prefix is stripped, so `teacher_righthandspeed` becomes
`righthandspeed` and matches `righthand`.

## Functions

| | |
|---|---|
| `spotOf(part)` | the real place a part name refers to, following the aliases |
| `bodyPart(name)` | the part a measure's name mentions, or `null`. Case-insensitive substring match against `BODY_TOKENS` |
| `spot(part)` | the `SPOTS` record for a part name, following aliases, or `null` |
| `positions(cx)` | every part name — **aliases included** — as `{x, y}` on a figure centred at `cx` |
| `personCx(index, total)` | where the nth of `total` figures is centred: `VIEW_W × (index+1) / (total+1)`, so people are evenly spaced with margins at both ends |
| `appendFigure(svg, {cx, color, el, opacity})` | draws one translucent body. `opacity` defaults to `0.3` |

<div class="figure" id="fig-people"></div>

`positions` derives the alias entries from `SPOTS` rather than listing them, so an
alias and the place it points at cannot drift apart.

`appendFigure` takes **`el`, the caller's element-maker** — `(name, attrs) → SVG
element` — because the tab and the wizard each already have one and neither should
have to adopt the other's.

### Each arm stays on its own side — check the numbers, not the names

The code pairs the **right** shoulder with `lefthand`, and the left shoulder with
`righthand`. That reads as though the arms cross. **They do not.**

The figure faces the viewer, so the person's left side is drawn on the viewer's
right. Both the spot names and the shoulder offsets follow that convention, and the
coordinates settle it — on a figure centred at 500:

| segment | from | to |
|---|---|---|
| right shoulder → `lefthand` | x = 560 | x = 600 |
| left shoulder → `righthand` | x = 440 | x = 400 |

Each segment stays on its own side of the centre line. Nothing crosses.

**What would cross is pairing them by name** — left shoulder to `lefthand` — which
reaches across the chest and draws the two arms as an X. That is a mistake the file
made once and now avoids; the pairing you see is the fix, not the bug.

## The fan

Every edge is drawn as a quadratic curve bowed perpendicular to its chord, and no
two edges by the same amount.

Straight lines between collinear nodes **are the same line**: three within-body
edges drew one thick bar with no way to tell one from three. Lines that merely
share an endpoint are nearly as bad — every cross-body edge crosses the middle and
they arrive at a node as a single smear. Fanning the whole set is what separates
them.

| constant | value | is |
|---|---|---|
| `BOW_FLOOR` | 22 | even a lone edge curves this much |
| `BOW_STEP` | 30 | spacing between neighbours in the fan |
| `BOW_MAX` | 240 | the widest arc, so a large fan stays in frame |

| | |
|---|---|
| `bowRanks(count)` | one rank per edge, symmetrical about zero — `[-1, 0, 1]` for three, `[-1.5, -0.5, 0.5, 1.5]` for four |
| `bowStep(count)` | `BOW_STEP` until the outermost arc would leave the picture, then whatever fits |
| `edgePath(p1, p2, rank, step)` | the SVG path: `M … Q …`, offset along the unit perpendicular |

`bowStep` is why a study with twenty edges gets a *tighter* fan rather than arcs
sweeping off the top of the viewBox. The floor is signed with the rank so the fan
stays symmetrical about the chord, and it exists so that **even rank 0 curves** —
two nodes joined by a single straight line read as structure rather than as a
measurement.

The fan lives here rather than in the tab because the wizard draws the same lines,
and a request for an analysis should be the same shape as the result that comes
back.

## Where it lives

[`packages/dims-tabs/figure-geometry.js`](../../packages/dims-tabs/figure-geometry.js).

It must be loaded **before `network.js`** — the scaffold's `index.html` sets that
order. When it is missing the network tab reports it rather than throwing, so the
tab still registers and says what is wrong.
