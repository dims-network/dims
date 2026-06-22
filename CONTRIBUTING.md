# Contributing

Full, canonical documentation lives on the DIMS docs site:

- **Contributing:** <https://dims-network.github.io/docs/contributing.html>
- **Integration workflow:** <https://dims-network.github.io/docs/workflow.html>
- **System architecture:** <https://dims-network.github.io/docs/architecture.html>

In short: dashboard code changes are made in
[DIMS_dashboard_template](https://github.com/dims-network/DIMS_dashboard_template);
this builder vendors the template under [`template/`](template/) as a **git
subtree**. Integrate upstream changes with:

```sh
scripts/update-template.sh
```

Changes to the wizard itself (the Flask app in `app/`, the UI in `app/static/`)
are made directly in this repo.