# Changelog

Releases are tagged `vX.Y.Z` and the whole core moves together: a study pins one
version in its `dims-case.json` and takes a fix by bumping it, never by editing
`vendor/`.

## v1.4.2

**The cross-RQA plot was drawn transposed.** Its axes said x was the first
series; the matrix put it on y. An off-diagonal band names which measure led, so
the tab named the wrong one. **If you read a lead or lag off that tab before this
release, reverse it.** Nothing stored changes — the tab transposes on read, so a
study renders correctly without being rebuilt.

- The ELAN tier selection survives a theme change, as its own comment always said
  it must.
- The ELAN time axis spans the recording rather than the annotated span.
- Clicking the cross-wavelet global spectrum no longer seeks to a power value read
  as seconds.
- The cross-RQA pair heading is readable in the light theme.
- A study with no `defaultWindowSize` no longer labels its segment `NaN`.
- A study with no transcripts no longer logs a 404 per recording change.
- The video is optional, and the docs now say so.

Guards, because in each case one existed and did not fire:

- `reference-study` had failed at its install step since v1.1.0 — four releases
  with no check that the analyses give correct numbers.
- The changelog check accepted *any* heading, which is how v1.4.0 shipped
  declaring 1.3.0. It now requires the newest.
- `PAYLOAD_VERSION` is compared across the two languages that declare it.
- The lag test matched by `|offset|` and was blind to the direction it exists to
  check.
- The ELAN theme test asserted before the code under test had run.

With #18, #19 and #20 from @GAIT-attempt: the builder names the install that fixes
it, the window warning no longer fires on sample-grid rounding, and the time-series
title comes from the study instead of one study's construct.

## v1.4.1

The documentation is re-derived from the code. Every tab, every command, the
browser API, the shared analysis machinery and the test layout now have a page
written from what the source does at this release, and `docs/` has an index
saying which reader each page is for. No code behaviour changes.

Two documented figures were wrong and are corrected: the payload examples said
`core_version: "1.1.0"`, and the README described unrelated signals as scoring
"0.25-0.6 depending on the timescale" -- which merged a mean with a 95th
percentile and generalised one study's measurement into a range. The README no
longer quotes a number; the cross-wavelet page keeps them, labelled as one
measurement on the Karnatak data.

**The version literals are corrected here too.** v1.4.0 was tagged while
`pyproject.toml` and both `__version__` strings still declared 1.3.0, so a study
created against that tag recorded `dimsCore: 1.4.0` while its payloads recorded
`core_version: 1.3.0`. `tests/test_release.py` did not catch it: it asks whether
the declared version has *a* heading in this file, not whether it is the current
one.

## v1.4.0

The wizard and the dashboard draw the same body, from the same file, and the
network's edges fan out instead of piling up. No output change; a study written
before this reads and renders exactly as it did.

**One copy of the figure.** `packages/dims-tabs/figure-geometry.js` holds the
body coordinates, the six places, the aliases and the token list. The tab loads
it from `vendor/`, the wizard is served it from the checkout. To move a body
part, change it there.

**Edges are fanned across the whole set.** Only edges with matching endpoints
used to get ranks of their own, so everything else sat at the minimum bow and
the cross-body lines arrived as one smear. The wizard's diagram draws the same
curves now, and the dashboard's nodes are smaller so the width channel reads.

**The example study is generated, not shipped.** ConvoConnect-Mini -- two
synthetic dyads, three minutes each, brains and hands and heads, transcript and
ELAN phases -- is written into a cache on first use. The two sample sessions and
their videos are out of the repository.

**Cross-wavelet has its own pairs again, and starts empty.** v1.3.0 made the
diagram the only way to pick one, which meant switching the analysis on seeded
every pair: 45 runs for ten measures, before anyone had chosen anything. The
chips are back and the diagram is a second view of the same set.

**Also:** step 6 streams its output instead of block-buffering it into what
looked like a hang; step 3 no longer prints a trim nobody applied; a link can be
dragged as well as clicked; and `sig95_wtc` is documented as `null` rather than
absent when no chance level was computed.

## v1.3.0

The cross-effector network is built by drawing it. No output change; a study
written before this reads and renders exactly as it did.

**The wizard draws the diagram.** Step 4 shows the same figures the dashboard
draws, at the same proportions. Add a person, click an empty circle to put a
time series on their head or a hand, click two placed nodes to draw the line
between them. A line is one cross-wavelet pair, so the cross-wavelet block no
longer has chips of its own -- picking the same thing in two places is how they
drift. The table of dropdowns v1.2.0 added is gone; the `effectors` config it
wrote is unchanged.

**Existing studies open already filled in.** A study that says all of this by
naming its measures `teacher_righthandspeed` is placed by the same inference the
tab runs, and the diagram says it guessed. Pressing Next writes the explicit
form. A test renders both through the tab's own grouping and layout and asserts
every node keeps its position, its label and its group -- a migration that
quietly moved one would be worse than none.

**`layout: "figure"` is implied** by placing anything, rather than being a
select nobody set.

**Also:** a person with neither a label nor a pattern is refused, since nothing
could ever be placed in it. And the builder's fix from v1.2.0 for
`scipy==1.26.4` was narrowed to that exact string after a sample study turned up
still carrying it -- see v1.2.0's note; the wrong end of that trade was chosen
twice before this.

## v1.2.0

A study can now say which time series is which node in the cross-effector
network, instead of encoding it in the measure's name and hoping the tab takes
it apart correctly. Additive: a study that declares nothing behaves exactly as
it did.

**`include_network.effectors`.** One entry per node — `series`, `label`,
`group`, and either a `part` of the figure or an `x`/`y` fraction of the chart.
Nothing is inferred from a name. Without it the tab reads the group off a
regular expression, the label off deleting that expression, and the body part
off a token found somewhere inside what is left; that works for a study whose
measures are called `teacher_righthandspeed` and leaves one whose measures are
called `bodysync` with a single undifferentiated column.

**The wizard asks.** Step 4 gains a table — one row per measure, with its group,
its label and where it goes — and the `layout` control it never had. It also
stops discarding what it cannot display: choosing the figure layout and then
reopening the study used to delete `layout` on the next Next, and an effector's
coordinates would have been the next casualty. There is a headless test suite
for the wizard's page now, which is what that class of bug needed.

**Two nodes no longer land on one spot.** The figure maps `head` and `nose` to
the same point, and `hand` and `lefthand` to the same point, so a study with
both drew one circle over another with a zero-length edge between them.

**The co-activity figure is documented, and was described wrongly.** Every edge
reports what share of the window both measures were active for. The schema said
it "is reported and never acted on"; it fades the edge below a quarter of the
window, and the tab's own comment contradicted the constant two lines below it.
What is true is that it never changes a coherence value.

**The tab has a page.** `docs/tabs/network.md` — how to read an edge, why
thickness is relative, why it needs a chance level, the co-activity channel and
its assumption that near-zero means "not moving", both layouts, and the effector
mapping.

## v1.1.0

One change to what an analysis writes, one to how the core is packaged, and a
cleanup pass behind both. A study takes this by bumping its pin and rebuilding;
cross-RQA payloads gain fields, and nothing else moves.

**Cross-RQA records the rate it aimed at.** It writes `target_recurrence`,
`achieved_recurrence` and `recurrence_rate_warning` for the first time, and the
rate under `recurrence_rate` as well as `global_recurrence_rate`. Contract A6
required this everywhere; only RQA did it, so a cross-RQA threshold that landed
on a plateau went unreported. No existing number changed.

**One distribution.** `packages/dims-analysis` no longer has its own
`pyproject.toml` declaring the same version, dependencies, console script and
three entry points as the root, so installing both no longer registers every
step twice. `dims_checks` is installable at last, three redundant
`requirements.txt` files are gone, and the one-click launchers install the
`builder` extra rather than a list that had drifted to no version floors.

**`dims-case` works when installed.** Its 253 lines lived in `tools/`, outside
any package, reached by a console script that ran the file by path — so `pip
install dims-network` gave a command that could only say it needed a checkout.
It is `dims_case.cli` now, with `tools/dims-case` kept as a shim.

**Faster, on the same numbers.** The windowed recurrence metrics no longer build
a run-length histogram in order to sum it: 23x faster at a 1000-sample window,
on the phase that dominated a recurrence analysis. The distance-triangle
percentile stopped spending two int64 index arrays to reach half a matrix. Every
value is bit-identical, which the reference baseline checks.

**Fixes you can see.** Four dashboard headings were white on the default white
background. Three tabs set a plot background that did not follow a theme switch.
A theme change and a video change cleared different tab caches.

**Fixes you cannot.** The recurrence steps rewrote a module-level input path, so
a second study analysed in one process would have read the first study's data;
they take parameters now, and no `global` survives in either. The privacy hooks'
fallback list of restricted directories was a second copy that nothing kept in
step with the first. `dims-case new` copied `__pycache__` into every new study.
A study's `scipy==` pin was silently unpinned by a repair meant for a template
that no longer exists. `.gitignore`'s `assets/` was unanchored and hid anything
new under the scaffold.

**The tests.** 382 to 446, and three that could not fail now can: the reference
baseline could not be regenerated at all (`make_baseline.py` pointed at the
wrong directory), a JS test looped over two absolute paths in one contributor's
home directory and passed everywhere else having asserted nothing, and `pytest`
at the repository root was a collection error rather than a skip without the
builder's extra. CI runs `packages/dims-case/tests` — the vendored-core check
and the privacy hooks — which no job had ever run.

## v1.0.2

Documentation only. No analysis or payload change: a study takes this by
re-vendoring, with no rebuild.

- The three analyses are documented. `docs/analyses/` covers cross-wavelet and
  coherence, RQA and cross-RQA — the algorithm, every parameter and its real
  default, every output field with its shape and units, and what each one does
  not do. The figures are produced by running the analyses over synthetic
  signals, not drawn.
- Stated for the first time: the recurrence steps apply **no time-delay
  embedding**, threshold on a recurrence rate rather than a radius, use no
  Theiler window, fix the minimum line length at 2, report `L_MAX` in seconds,
  and compute none of L, ENTR or TT.
- `docs/coherence.md` is now a section of the cross-wavelet page, beside the
  transform it comes from and the three other significance levels it is easy to
  confuse it with.
- The coherence page said 300 Monte Carlo surrogates was the default. It is 100
  when `include_network` is set and 0 otherwise; 300 is the number to publish
  with.
- Two gaps named rather than papered over: `crqa` records no achieved
  recurrence rate to compare with its target (contract A6), and
  `include_cRQA` silently ignores the flat list of data types that
  `include_crosswavelet` accepts.
- The step contract's example named a class that does not exist.

## v1.0.1

Documentation and wording only. No analysis or payload change: a study takes
this by re-vendoring, with no rebuild.

- The README's install and `dims-case new` commands work as written — the
  checkout install, `--visibility`, and `case-<name>` as the directory created.
- Python 3.10 is the floor everywhere. Three pages said 3.9, which pip refuses.
- The cross-effector network is documented where it was missing: the built-in
  tab list, the scaffold's tab table and config example, and what
  `include_network` needs to draw anything useful.
- A dashboard reading an old asset no longer names a release the renumbering
  removed; it says the payload is older and how to rebuild.
- The `agent-ready` issue label is now `ready`.

## v1.0.0

The first public release.

**The dashboard.** A study's recordings, time series, transcripts and ELAN
annotations on one timeline, with tabs that appear only when the study's
`config.json` asks for them: recurrence, cross-recurrence, cross-wavelet and
coherence, and a cross-effector network.

**The analyses**, as the `dims-analysis` package: recurrence quantification,
cross-recurrence, and the cross-wavelet transform with an AR(1) coherence null,
following Torrence & Compo (1998). Every constant taken from that paper is
transcribed in `examples/reference/`, and `tests/reference/` checks the results
against it, against `pyrqa`, and against an independently computed null.

**One study, one small repository.** `dims-case` creates a study, pins a
released core into `vendor/`, and verifies it byte for byte; studies with data
about identifiable people declare themselves private and get commit, push and CI
guards that keep that data out of git.

**A no-code builder.** `dims-builder` walks from a folder of recordings to a
working dashboard, including the analyses.

See [`docs/contracts/`](docs/contracts/) for what each part promises.
