# `dims-analysis`

Run the analyses a study's `config.json` asks for, list what is installed,
remove results it no longer asks for, or record what a complete set of assets
looks like.

```
dims-analysis run      [--config PATH] [--steps IDS] [--output-dir DIR] [--keep-going] [--traceback]
dims-analysis list
dims-analysis prune    [--config PATH] [--steps IDS] [--output-dir DIR] [--apply]
dims-analysis manifest [--project-dir DIR] [--check] [--deep] [--no-checksums]
```

Inside a study you will normally reach it through `python build_assets.py`, which
calls `run` for the shared steps and then any study-owned steps in `opt/`.

---

## `run`

| flag | default | |
|---|---|---|
| `--config PATH` | `config.json` | the study's config. **The project directory is taken from this file's location**, not from the working directory |
| `--steps IDS` | `all` | comma-separated step ids |
| `--output-dir DIR` | — | override every step's output directory |
| `--keep-going` | off | carry on after a step fails instead of stopping |
| `--traceback` | off | print a traceback when a step raises |

Steps are discovered through the `dims.steps` entry-point group, not a list in
this file — see [`contracts/step.md`](../../contracts/step.md). Each is run only if
its own `gate(config)` says the config enables it, and those the config left off
are listed as skipped. **Steps excluded by `--steps` are not listed at all** — the
skipped line reports the config's choices, not yours.

### It fails loudly, and that is the point

The runner this replaced emitted an exit-code sentinel that nothing read, so a
crashed analysis scrolled past in the log and the build reported success —
leaving a dashboard with missing data and no indication anything was wrong. Every
exit path here is therefore explicit:

| situation | exit |
|---|---|
| everything the config enabled ran and wrote something | `0` |
| no such config file | `2` |
| an unknown step id in `--steps` | `2` — and it prints the available ids |
| a step you asked for could not be **imported** | `1` |
| a step raised | `1` |
| **a step ran, was enabled, and wrote nothing** | `1` |

**"Could not be imported" is kept separate from "unknown".** Saying
`unknown step: crosswavelet` when the real cause is a missing `pycwt` sends you
looking for a typo instead of an install.

**A missing dependency fails the whole run, whatever your config says.** With no
`--steps`, *every* unimportable step counts as blocking — the config's own gate is
never consulted for it. So a study that does not enable cross-wavelet still exits
`1` on a plain `dims-analysis run` if `pycwt` is not installed. Narrow the run with
`--steps` to work around it.

**"Wrote nothing" is the failure that actually happens.** It does not raise: every
step catches its own unreadable-input case, prints a warning and returns
normally. Before this check existed, the run reported success over an empty output
directory and `build_assets.py` printed "Asset build complete". The check works by
snapshotting the step's output directory before and after and comparing file
modification times — so a re-run that rewrites the same filenames still counts as
having produced something, and the test does not depend on filesystem timestamp
granularity.

The message names the directory it expected files in, and points you at the step's
own messages above for the reason. The usual cause is missing input.

### The summary

```
ran: rqa, crqa
skipped (not enabled in config): crosswavelet
PRODUCED NOTHING: crqa
FAILED: crosswavelet
```

`PRODUCED NOTHING` and `FAILED` go to stderr; `ran` and `skipped` to stdout.

## `list`

Every registered step and its one-line description, two spaces in, ids padded to a
common width:

```
  crosswavelet  Cross-wavelet transform and coherence, with an AR(1) coherence null
  crqa          Cross-recurrence quantification between pairs of time series
  rqa           Recurrence quantification analysis of single time series
```

Prints `no steps registered` and exits `0` when the entry-point group is empty —
which, in an installed environment, means the install is broken rather than that
there is nothing to run.

This output is what CI greps to prove the three shipped steps registered, so its
shape is load-bearing.

## `prune`

Removes payload entries the config no longer asks for. Nothing is recomputed.

| flag | default | |
|---|---|---|
| `--config` | `config.json` | the study to read |
| `--steps` | `all` | comma-separated step ids |
| `--output-dir` | — | override every step's output directory |
| `--apply` | off | actually remove them; without it, only reports |

A rebuild already removes the entries a step **owns** and the config no longer
asks for. This exists for the ones it cannot: a file written before owners were
recorded stamps nothing, and an unstamped entry is never removed on a guess, so
a study built before v1.5.0 keeps its orphans through any number of rebuilds.

```
$ dims-analysis prune --config config.json

assets/crosswavelet/dyad01_crosswavelet_data.json
  would remove crosswavelet_pairs/personLeftLeftHandSpeed_vs_rtpjSync (owner: unknown)
  ...

12 entries would be removed. Re-run with --apply.
```

**Read the list before applying.** An entry stamped by another step is never
offered — it is reported as `keeping`, naming the owner — but an entry showing
`owner: unknown` is only *probably* an orphan. In one real study, `gaze_child`
and `gaze_parent` sit in `*_rqa_data.json`, are absent from `include_RQA`, and
are not orphans at all: they are a study-owned categorical RQA's results.

A step is skipped unless it answers `expected_entries`, because `{}` there means
*cannot say* rather than *asks for nothing*. Its `extra_output_names` are walked
too, so cross-wavelet's full-resolution file is cleaned with its reduced one and
the two cannot end up disagreeing about which pairs the study has.

## `manifest`

A private study's data lives outside git, so `assets/MANIFEST.json` is the only
thing **in** the repository that says what a complete set of assets looks like.
After a rebuild it answers the question a green exit code cannot: did it produce
everything?

```sh
dims-analysis manifest                    # write it
dims-analysis manifest --no-checksums     # names and sizes only — fast over video
dims-analysis manifest --check            # compare against disk
dims-analysis manifest --check --deep     # …verifying checksums too
```

Writing reports the file count and which mode it used. Checking reports one line
per discrepancy:

| line | means |
|---|---|
| `missing: <path>` | the manifest expects it and it is not there |
| `differs: <path>` | it is there and does not match |
| `not in the manifest: <path>` | it is there and was not expected |

`missing` or `differs` fail with exit `1` and the summary *"the rebuild is not
complete"*. **Extra files are not a failure** — a study may hold working files the
manifest was never asked about — they are only listed. Checking with no manifest
present exits `2` and tells you to write one.

Checksums are recorded on a write unless you pass `--no-checksums`. Verifying them
on a `--check` is opt-in, with `--deep`. **`--deep` does nothing on a write** — it
is defined as a modifier for `--check` and the write path never reads it.

## See also

- [`contracts/step.md`](../../contracts/step.md) — writing a step, and how
  discovery works.
- [`contracts/analysis-output.md`](../../contracts/analysis-output.md) — what a
  step must write.
- [the analyses](../../analyses/index.md) — what the three shipped steps compute.
- [`dims-case`](dims-case.md) — creating the study this runs inside.
