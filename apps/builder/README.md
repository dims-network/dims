# DIMS Dashboard Builder

A no-code wizard: point it at your recordings, time series and annotations, and
it produces a working DIMS dashboard.

```sh
pip install "dims-network[builder]"
dims-builder
```

It lives in the DIMS monorepo alongside the core it builds against, so a study
it generates is identical to one made with `dims-case` — same scaffold, same
pinned core, same checks. It used to carry its own copy of the dashboard, kept
in step by hand; that copy is gone.

## Quick start

**macOS** — double-click `run.command`
**Linux** — `./run.sh`
**Windows** — double-click `run.bat`

Or manually (also the simplest way to avoid the macOS prompt below):

```bash
pip install -r requirements.txt
dims-builder
```

> **macOS, first run only:** if you downloaded the ZIP you may see *“Apple could not
> verify ‘run.command’ is free of malware.”* Click **Done**, then go to
> **System Settings → Privacy & Security**, scroll to **Security**, and click
> **Open Anyway**. This is macOS flagging any downloaded unsigned script; it happens
> once. (Running `dims-builder` in a terminal skips it entirely.)

Your browser opens to the wizard. Follow the 7 steps:

1. **Your study** — pick a folder, and say **who may see the data**. Private is
   the default and turns on the guards in
   [`data-visibility.md`](../../docs/contracts/data-visibility.md): a pre-commit
   hook, a pre-push hook and a CI check. There is nothing to choose about the
   dashboard code — one scaffold ships in this repository and it is the one used.
   You can also **open a study you made earlier**: everything comes back filled
   in, so adding a session or changing an analysis is a rebuild rather than a
   hand-edit of `config.json`.
2. **Sessions & files** — drag your files in, or press **Load the example
   study** for two ready-made sessions that ship with the builder. The builder
   works out what each file is (`.mp4`, `.csv`, `_transcript.json`, `.eaf`),
   which session it belongs to, and splits a multi-column CSV into one file per
   measure. If a session was filmed from several angles, name them here and the
   dashboard gets a camera selector.
3. **Align video & data** — when a session's video and measurements have
   different lengths the dashboard shows dead space. Per session, a
   shared-timeline preview shows the video track above each measurement track,
   and you can either *trim the video* to a window you pick with a dual-handle
   slider, or *pad the measurements* with zeros at either end. Edits are
   **non-destructive** — your originals are never modified; the trim or pad is
   applied only to the copies written at build time. (Trimming uses the `ffmpeg`
   that ships via `imageio-ffmpeg` — no system install needed.)
4. **Tabs & analyses** — switch on recurrence, cross-recurrence, cross-wavelet,
   the cross-effector network and ELAN annotations, and pick which measures or
   pairs each runs on. Every analysis has a **Settings** panel for the tuning
   the study can set — the recurrence window and target rate, the cross-wavelet
   picture size and its chance-level surrogate count. A line at the foot of the
   step says how many runs that adds up to and which of them are the slow ones,
   because the first sign that a choice was expensive should not be being forty
   minutes into step 6.
5. **Build** — files are copied into place and `config.json` is written, after
   being checked against the same schema CI validates every study against.
6. **Compute** — the builder creates a study-local Python environment and runs
   the analyses. Progress streams live.
7. **Open it** — opens your dashboard locally and shows copy-paste commands
   to deploy it to GitHub Pages / Netlify / Vercel.

## Requirements

- Python 3.9+
- That's it. The dashboard is in this repository, beside the builder, so
  **git and an internet connection are not required** to build a study. `git` is
  worth having afterwards, for the privacy guards a private study installs.

## What the builder produces

A study, identical to one `dims-case new` makes — same scaffold, same pinned
core, same guards:

```
your-project/
  config.json                              # written for you
  assets/videos/{id}.mp4
  assets/timeseries/{id}_{dataType}.csv
  assets/transcripts/{id}_transcript.json
  assets/elan/{id}.eaf                      # if ELAN enabled
  assets/rqa/{id}_rqa_data.json             # if RQA enabled (precomputed)
  assets/crosswavelet/{id}_crosswavelet_data.json  # if cross-wavelet enabled
  ...                                       # the rest of the template, unchanged
```

This folder is the deployable artifact — host it on any static host that supports
HTTP Range requests (needed for video seeking).
