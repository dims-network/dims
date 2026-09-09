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
| `rqa` | `assets/rqa/{id}_rqa_data.json` | recurrence quantification of one signal — [method](../../docs/analyses/rqa.md) |
| `crqa` | `assets/crqa/{id}_crqa_data.json` | cross-recurrence between a pair — [method](../../docs/analyses/crqa.md) |
| `crosswavelet` | `assets/crosswavelet/{id}_crosswavelet_data.json` | cross-wavelet power and coherence for a pair, against an AR(1) chance level — [method](../../docs/analyses/crosswavelet.md) |

Each reads its parameters from `analysis.<step>` in the study's `config.json`;
`dims-analysis list` prints what is installed. Those pages document every
parameter, every output field and what each analysis does *not* do — the
recurrence steps apply no time-delay embedding, and threshold on a recurrence
rate rather than a radius.

Two costs worth knowing before a rebuild. The Monte Carlo coherence null is the
expensive part: cost follows pairs x recordings x scale count, not minutes of
video, and it only runs when `mcCount` is set or `include_network` is on. And a
recurrence matrix is quadratic in the number of samples, so the steps refuse an
input above about 16,000 points rather than allocating 2 GiB.

Steps are discovered through the `dims.steps` entry point group, so adding one
never requires editing this package. The contract, with its acceptance checks,
is in [`docs/contracts/step.md`](../../docs/contracts/step.md).

`run` **fails loudly**: a step that raises makes the command exit non-zero. Its
predecessor emitted an exit-code sentinel that nothing read, so a crashed
analysis looked exactly like a successful one.
