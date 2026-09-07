# Contract: a Python analysis step

An analysis turns time series into something a tab can draw. There are two
places to put one, and choosing correctly is most of this document.

| | Put it in | Because |
|---|---|---|
| Every study could use it | `packages/dims-analysis/dims_analysis/steps/` | one copy, one fix, reaches every study by a version bump |
| Only this study needs it | the study's own `opt/step_<id>.py` | its input is that study's own upstream pipeline |

**Most analyses are the second kind**, and both shipped examples are: ORTHO's
categorical gaze RQA reads a game database, and Karnatak's motion tracking
reads video. Neither belongs in a package every study installs.

---

## A study-owned analysis

A plain script in `opt/`, named `step_<id>.py`, run by `build_assets.py` and
gated by `"include_<id>": true` in `config.json`. It is handed
`--config config.json` and nothing else; it decides where its own output goes.

```python
#!/usr/bin/env python3
"""What this produces, and what it reads to produce it."""
import argparse, json
from dims_analysis.common import assets, results, series

ap = argparse.ArgumentParser()
ap.add_argument('--config', default='config.json')
args = ap.parse_args()
config = json.load(open(args.config))

for video_id in config['videoIDs']:
    path = assets.resolve(f'assets/timeseries/{video_id}_gaze.csv')
    loaded = series.load_or_none(path, min_points=10)
    if loaded is None:            # already explained why, on stdout
        continue
    time, values = loaded
    ...
    results.write_payload(assets.resolve(f'assets/rqa/{video_id}_rqa_data.json'),
                          {'video_id': video_id, 'categorical_rqa': ...})
```

Three things this example is doing on purpose:

- **`assets.resolve`** on every path. A private study keeps its data outside
  the repository, at the path `data.local.json` names. A script that skips this
  works for its author and for nobody else.
- **`results.write_payload`** rather than `json.dump`. It merges into whatever
  is already in that file, so an analysis writing beside a shared one does not
  erase it. ORTHO's categorical RQA writes into the same
  `assets/rqa/<id>_rqa_data.json` the shared RQA step writes; before merging
  existed, whichever ran second won.
- **No `--output-dir`.** `build_assets.py` deliberately does not pass one to a
  study-owned step, because a step that writes into an existing directory on
  purpose must not have that overridden.

## A shared step

A class in `packages/dims-analysis/dims_analysis/steps/`, found through an
entry point. The runner never lists steps, so adding one edits no existing
file.

```python
from dims_analysis.base import Step

class RQAStep(Step):
    id          = "rqa"                       # also the CLI selector
    config_key  = "include_RQA"               # gate key in config.json
    output_dir  = "assets/rqa"                # default; resolved through data.local.json
    output_name = "{video_id}_rqa_data.json"
    description = "Recurrence quantification, per video"

    def run(self, config, ctx) -> None:
        for video_id in config["videoIDs"]:
            ...
            ctx.write_result(self, video_id, {"rqa_data": ...})
```

```toml
[project.entry-points."dims.steps"]
rqa = "dims_analysis.steps.rqa:RQAStep"
```

A step in a *separate* package registers the same way — that is how an outside
module joins the pipeline without a change here.

### What `ctx` is for

`ctx` is paths and results. It is **not** a data-access layer, and does not
wrap the analysis helpers; those are module functions you import directly.
Every method takes the step as its first argument, because one context serves
every step in a run.

| | |
|---|---|
| `ctx.project_dir` | absolute path to the study |
| `ctx.path(*parts)` | a path inside the study |
| `ctx.output_dir_for(step)` | where this step's output belongs, resolved through `data.local.json`; no side effects |
| `ctx.output_path(step, video_id)` | the full output filename, creating the directory |
| `ctx.write_result(step, video_id, payload)` | writes it, **merging** with anything already in that file |
| `ctx.params(step, defaults)` | per-step tuning from `config.json`'s `analysis` block, over your defaults |
| `ctx.output_snapshot(step)` | `{path: mtime}`, which the runner uses to detect a step that wrote nothing |

### The helpers, which are not on `ctx`

Import these from `dims_analysis.common`. They exist because each was
previously copied into ten or twelve places, in signatures that disagreed.

| module | what it settles |
|---|---|
| `assets` | where the data actually is: `resolve(path)`, `assets_root()` |
| `series` | one reader: canonical `Time` column, NaNs dropped, **sorted by time**, a caller-stated minimum length. `load_or_none` reports and returns `None` |
| `recurrence` | one recurrence rule for RQA and cross-RQA: `threshold_for_target`, `recurrence_rate`, `line_lengths`, `window_metrics` |
| `reduce` | reducing for the browser without lying: `block_mean` for series, `block_binary` for a recurrence matrix |
| `results` | `write_payload`, which merges; `compare_entries`, which says what a re-run replaced |
| `npz` | `add_group`, appending a full-resolution array group without recompressing the file |
| `payload` | `round_payload`: browser payloads carry significant figures, not decimal places |

## Rules

1. **Self-gate.** If your key is absent, do nothing and exit cleanly. Do not
   raise, and do not make the runner know about you.
2. **Never hardcode a path.** Everything through `assets.resolve` or `ctx`.
   Two absorbed scripts hardcoded `./config.json` and their own input
   directory; they could only run from one working directory, and on a private
   study they read a directory that did not exist while printing "assets
   resolved" and reporting success.
3. **Tuning belongs in config**, via `ctx.params` or a documented key. A
   module-level constant cannot vary per study without editing the source,
   which is exactly how a fork ends up maintaining its own copy of an analysis.
4. **Write both resolutions.** The JSON is the browser payload and may be
   reduced; the `.npz` beside it is the real result. Record the reduction
   factor in the payload — a reader who cannot tell a 500-point plot from a
   6000-point one does not know what the axis means. Never let a reduction be
   the only surviving analysis.
5. **Reduce honestly.** A recurrence matrix has two properties a reader takes
   from the picture: where the structure is, and how much of the plot is
   recurrent. Striding keeps the rate and deletes any line off the main
   diagonal — which is what a lagged coupling looks like. Block-OR keeps the
   structure and inflates the rate; measured on ORTHO at factor 9, 10.9% became
   54.4% beside a caption saying 10.9%. Use `reduce.block_binary`, which keeps
   both.
6. **Fail loudly.** Raise on real errors. The runner checks that an enabled
   step wrote something, because for a long time a crashed analysis scrolled
   past in the log and the build reported success.
7. **Be deterministic.** Seed anything stochastic and put the seed in the
   output. An unseeded Monte Carlo made one significance threshold vary by 0.04
   between runs on identical data.

## Acceptance

Run these. Do not reason about them.

- A shared step: `dims-analysis run --config config.json` finds it with no
  other file edited. `dims-analysis list` shows it.
- A study-owned step: `python build_assets.py --check` lists it under
  *study-owned*, and lists it as *not enabled* when its config key is absent.
- With the config key absent, the run succeeds and writes nothing.
- Running twice over identical input produces byte-identical output.
- A deliberate `raise` inside the step makes the command exit non-zero.
- On a study with `data.local.json`, the step reads and writes under the
  external root, and `git status` is clean afterwards.
