# Contributing

## Repos

- **DIMS_dashboard_builder** (this repo) — the no-code wizard that scaffolds a
  dashboard project, places assets, writes `config.json`, and runs the template's
  analysis scripts.
- **[DIMS_dashboard_template](https://github.com/dims-network/DIMS_dashboard_template)**
  — the dashboard itself: the frontend (`js/`, `css/`, `index.html`), the
  analysis scripts (`opt/step_*.py`), and `serve.py`.

## How the template lives inside the builder

The builder ships a complete copy of the template under [`template/`](template/)
so a non-technical user needs **neither git nor a network connection** to build a
dashboard (`acquire_template` in [`app/project.py`](app/project.py) copies it into
each generated project, and the builder runs the project's own `opt/` scripts).

That `template/` directory is a **git subtree** of the upstream template repo —
the files are committed here (offline-safe), but their history is linked to
upstream so updates can be pulled in with one command.

## Adding a feature to the dashboard

1. Open a PR against **DIMS_dashboard_template** (frontend or `opt/` scripts).
2. Once it's merged to `main`, an admin integrates it into the builder:

   ```sh
   scripts/update-template.sh
   # equivalently:
   # git subtree pull --prefix=template \
   #     https://github.com/dims-network/DIMS_dashboard_template.git main --squash
   ```

3. Review the squashed merge, run a quick build to sanity-check, then
   `git push` the builder repo.

> Existing generated projects pick up the new scripts automatically: on the next
> build, `acquire_template` refreshes a project's template *code* (`opt/`, the
> frontend, the deploy workflow) from the bundled copy while preserving the
> user's `config.json` and `assets/`.

## Working on the builder itself

Changes to the wizard (the Flask app in `app/`, the static UI in `app/static/`)
are made directly in this repo as normal PRs.
