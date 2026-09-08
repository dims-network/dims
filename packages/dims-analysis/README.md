# dims-analysis

The Python analyses behind a DIMS dashboard.

```sh
pip install -e .
dims-analysis list
dims-analysis run --config config.json
```

## The steps it ships

| step | writes | what it is |
|---|---|---|
| `rqa` | `assets/rqa/{id}_rqa_data.json` | recurrence quantification of one signal |
| `crqa` | `assets/crqa/{id}_crqa_data.json` | cross-recurrence between a pair |
| `crosswavelet` | `assets/crosswavelet/{id}_crosswavelet_data.json` | cross-wavelet power and coherence for a pair, against an AR(1) chance level |

Each reads its parameters from `analysis.<step>` in the study's `config.json`;
`dims-analysis list` prints what is installed. Coherence is only interpretable
beside its chance level — see [`docs/coherence.md`](../../docs/coherence.md) —
and the Monte Carlo null that produces it is the expensive part of a rebuild:
cost follows pairs x recordings x scale count, not minutes of video.

Steps are discovered through the `dims.steps` entry point group, so adding one
never requires editing this package. The contract, with its acceptance checks,
is in [`docs/contracts/step.md`](../../docs/contracts/step.md).

`run` **fails loudly**: a step that raises makes the command exit non-zero. Its
predecessor emitted an exit-code sentinel that nothing read, so a crashed
analysis looked exactly like a successful one.
