# Contract: a Python analysis step

A step turns time series into something the dashboard can draw. It is a class in
`packages/dims-analysis/dims_analysis/steps/`, discovered through an entry
point — the runner never lists steps, and adding one must not require editing
any existing file.

## The shape

```python
from dims_analysis.base import Step

class RQAStep(Step):
    id          = "rqa"                          # also the CLI selector
    config_key  = "include_RQA"                  # gate key in config.json
    output_dir  = "assets/rqa"
    output_name = "{video_id}_rqa_data.json"

    def gate(self, config) -> bool:
        """Default: truthy config[config_key]. Override for richer rules."""
        return bool(config.get(self.config_key))

    def run(self, config, ctx) -> None:
        for video_id in config["videoIDs"]:
            series = ctx.load_series(video_id, "bodysync")
            ...
            ctx.write_result(video_id, {"rqa_data": ...})
```

Register it in `pyproject.toml`:

```toml
[project.entry-points."dims.steps"]
rqa = "dims_analysis.steps.rqa:RQAStep"
```

A step in a *separate* package registers exactly the same way — that is how an
outside module (an EnvisionBox analysis, say) joins the pipeline without a
change here.

## What `ctx` gives you

| | |
|---|---|
| `ctx.load_series(video_id, data_type)` | `(time, values)`, NaNs dropped, sorted, `Time` matched case-insensitively |
| `ctx.align(video_id, type_a, type_b)` | both series on one uniform grid, z-normalised |
| `ctx.write_result(video_id, payload)` | writes `output_dir/output_name`, merging with any existing file |
| `ctx.write_analysis(video_id, arrays)` | full-resolution `.npz` for notebooks and downstream work |
| `ctx.params(defaults)` | per-step tuning from `config.json`, falling back to your defaults |

Use these rather than reimplementing. The helpers they replace were previously
copied 10–12 times across the repos, in two mutually incompatible signatures.

## Rules

1. **Self-gate.** If your key is absent, return cleanly. Do not raise, and do
   not make the runner know about you.
2. **Never hardcode paths.** Everything relative to the project root, through
   `ctx`. Two existing scripts hardcode `./config.json` and their own input
   directories; they are the reason this line exists.
3. **Tuning belongs in config**, via `ctx.params()`. A module-level constant
   cannot vary per study without editing the source, which is what forced one
   fork to maintain its own copy of a whole step.
4. **Write both resolutions.** `write_result` is the browser payload and may be
   reduced; `write_analysis` is the real result. Reduce by block-averaging, and
   record the factor. Never let striding be the only surviving analysis.
5. **Fail loudly.** Raise on real errors. Exit codes are checked; a step that
   fails must not look like a step that succeeded.
6. **Be deterministic.** Seed anything stochastic and put the seed in the
   output. An unseeded Monte Carlo made one significance threshold vary by 0.04
   between runs on identical data.

## Acceptance

- `dims-analysis run --config config.json` finds your step with no other edit.
- With your `config_key` absent, the run succeeds and does nothing.
- Running twice over identical input produces byte-identical output.
- A deliberate failure inside `run()` makes the CLI exit non-zero.
