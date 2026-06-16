# DIMS Dashboard Builder

A no-code, point-and-click tool for building a [DIMS dashboard](https://github.com/dims-network/DIMS_dashboard_template)
from your own recordings — **no JSON editing, no file renaming, no terminal scripts**.

It opens a wizard in your browser, lets you drag-and-drop your videos, time-series
CSVs and transcripts, runs the optional analyses (RQA, cross-wavelet) for you, and
produces a ready-to-deploy dashboard folder.

> This tool does **not** modify the template. It acquires a fresh copy of the
> template, fills it in, and leaves you a self-contained, deployable project.

## Quick start

**macOS / Linux**

```bash
./run.sh
```

**Windows** — double-click `run.bat`

Or manually:

```bash
pip install -r requirements.txt
python builder.py
```

Your browser opens to the wizard. Follow the 6 steps:

1. **Project** — pick an output folder. The DIMS dashboard template is **built into
   the builder**, so it's used by default — no git, no internet required. (Advanced:
   you can instead clone the latest from GitHub or point at a local template folder.)
   Set the title, authors, etc.
2. **Sessions & files** — drag in your files. The builder figures out what each one
   is (`.mp4` video, `.csv` time-series, `_transcript.json` transcript, `.eaf` ELAN),
   groups them under a session/video ID, and checks them as you go.
3. **Optional analyses** — turn on RQA and/or cross-wavelet and ELAN annotations.
4. **Build** — files are copied into place and `config.json` is written.
5. **Precompute** — the builder creates a project-local Python environment and runs
   the analysis scripts. Progress streams live.
6. **Preview / Deploy** — opens your dashboard locally and shows copy-paste commands
   to deploy it to GitHub Pages / Netlify / Vercel.

## Requirements

- Python 3.9+
- That's it for the default path — the template ships inside the builder
  (`template/`), so **git is not required**. (`git` is only needed if you choose the
  optional "clone the latest from GitHub" template source.)

## What the builder produces

A complete copy of the DIMS template with:

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
