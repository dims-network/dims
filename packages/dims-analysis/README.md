# dims-analysis

The Python analyses behind a DIMS dashboard.

```sh
pip install -e .
dims-analysis list
dims-analysis run --config config.json
```

Steps are discovered through the `dims.steps` entry point group, so adding one
never requires editing this package. The contract, with its acceptance checks,
is in [`docs/contracts/step.md`](../../docs/contracts/step.md).

`run` **fails loudly**: a step that raises makes the command exit non-zero. Its
predecessor emitted an exit-code sentinel that nothing read, so a crashed
analysis looked exactly like a successful one.
