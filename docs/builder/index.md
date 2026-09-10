# The no-code builder

A local wizard that turns a folder of recordings and CSVs into a working
dashboard, without a terminal beyond the one command that starts it. It is the
path for the researchers DIMS is for, who are domain experts and not necessarily
programmers.

```sh
pip install -e './dims[builder]'
dims-builder
```

Your browser opens on step 1. Flags, ports and launchers are on
[the `dims-builder` reference](../reference/cli/dims-builder.md).

**It writes an ordinary study.** Nothing about the result is wizard-specific: the
skeleton comes from the same `dims_case.core` the
[`dims-case`](../reference/cli/dims-case.md) command uses, so a study you build
here and one you create on the command line are the same thing, and either can be
continued with the other.

## The seven steps

### 1 · Study
New or existing, where it goes, and `public` / `private` — the
[visibility decision](../contracts/data-visibility.md), which you answer once and
which is not inferred. Then the study's title, subtitle, authors, contacts and
`defaultWindowSize`.

### 2 · Sessions & files
Drop files in. Each is given a **role** inferred from its extension, a session id
and — for a time series — a measure name; you correct any of that in the table.
This is where `videoIDs` and `dataTypes` come from.

**"Load the example study"** builds a complete synthetic study called
ConvoConnect-Mini — two dyads, hand and rtpjSync measures, transcripts, an `.eaf`
and generated video — so you can see the whole path before committing your own
data. It is generated on demand, not shipped, and it is byte-stable: generating
it twice gives identical files.

Studies filmed from several angles configure `perspectives` here.

### 3 · Align
**The step that earns its place.** Per session, trim the video and zero-pad the
time series until the two cover the same span, with live extent bars showing where
they currently disagree.

This is the one requirement DIMS cannot check for you and cannot recover from:
each signal's time axis must map onto the video clock. A misalignment is displayed
faithfully as a misalignment, and it is easily mistaken for meaningful dynamics.

It records **specs**, not edits — your original files are not modified.

### 4 · Tabs & analyses
Which analyses to run, and on what.

- **RQA, cross-RQA and cross-wavelet** get chip pickers for measures and pairs,
  plus the advanced settings that become the `analysis` block.
- **The network diagram** is drawn here: place measures on a body, drag between
  two of them to ask for that coupling. It is the same figure the dashboard draws,
  from the same [geometry file](../reference/figure-geometry.md), and the pairs
  you draw are the *same list* as the cross-wavelet chips above — either view
  edits it and both redraw.
- **ELAN** is a toggle.

Switching the network on forces cross-wavelet on, because the network is a view of
it. It also sets `mcCount` to 100 — but **only when you have not set one**; an
existing non-zero value is left alone. The network is the only thing that reads the
coherence null and is meaningless without it.

### 5 · Build
Validation problems first — a `series` with no CSV and a duplicated `series` are
errors; an unknown body part and an undefined group are warnings — then the
assembled `config.json` for review, then write.

The config is also checked against
[`config.schema.json`](../contracts/config.schema.json), though **during** the
write rather than before it: the staged assets are copied into the study first, so
a schema failure leaves a partly-populated directory rather than nothing. See
[the API page](api.md).

### 6 · Compute
Runs the analyses, streaming the log into the page with a running clock. It
creates a virtualenv inside the study so the run does not depend on how you
installed the builder.

**This is the step that can take real time**, and what governs it is `mcCount`,
not the size of your study. The coherence null costs the same for an 8-second clip
as for a twenty-minute recording, and results are cached, so the cost scales with
how many distinct nulls are needed.

The default is `0` — no null — unless you switched the network on, which asks for
100. Only a study that sets `mcCount` itself reaches 300, the publication setting,
which is the one that runs into hours.

### 7 · Open it
Preview the dashboard locally, and the command to deploy it. For a private study
this is also where the reminder sits that the data stays out of git.

## What it does not do

- **It does not produce your time series.** DIMS is not a preprocessing pipeline:
  it assumes time-aligned modalities already exist. Tracking, filtering and
  synchrony estimation happen before the wizard.
- **It does not check that your alignment is correct** — only that you were given
  the chance to fix it in step 3.
- **It is not a server.** It binds to localhost, has no authentication, and is
  meant to run on the machine holding the data.

## See also

- [its HTTP API](api.md) — if you are working on the wizard itself.
- [`dims-case`](../reference/cli/dims-case.md) — the same job from a terminal.
