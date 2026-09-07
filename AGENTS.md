# Working on DIMS

A map, not a manual. Find your task, read the **one** file named. Do not read
this whole directory before starting — the contracts are written to be read
individually.

## Which file do I need?

| I want to… | Read |
|---|---|
| Add or change a **tab** in the dashboard | `docs/contracts/tab.md` |
| Add or change a **Python analysis** | `docs/contracts/step.md` |
| Know what goes in `config.json` | `docs/contracts/config.schema.json` |
| Know where a data file belongs / how it is named | `docs/contracts/assets.md` |
| Work in a repo that holds **human-subject data** | `docs/contracts/data-visibility.md` |
| Set up a new study | `docs/contracts/case.md` |
| Understand how the repos fit together | `docs/architecture.md` |

## The five rules

1. **One copy of the code.** It lives here. Case repos hold `config.json`, data
   and a pinned copy of this core — never edited by hand. If you find yourself
   fixing the same bug twice, stop: you are in the wrong repo.
2. **Everything self-registers.** Tabs and analyses are discovered, not listed.
   Adding one must not require editing an existing file. If it does, the
   contract is wrong — fix the contract, not your feature.
3. **Style through CSS custom properties only** (`var(--text)`, `var(--accent)`).
   Never read the host's JS theme object; it is initialised after plugins load.
4. **Assume the data is private** until `dims-case.json` says otherwise. Never
   commit anything under `assets/`, and never move data content into an external
   service — an issue, a prompt, a hosted page.
5. **Verify by running it.** Every contract ends with an acceptance check that
   does not require reading any other file.

## Repository layout

```
packages/dims-core/          the host: config, video, time bus, tab registry
packages/dims-tabs/          one file per tab, all self-registering
packages/dims-analysis/      the Python analyses, a pip package
packages/dims-case-scaffold/ what `dims case new` emits
apps/builder/                the no-code wizard
docs/contracts/              read one of these, not all of them
```

## Picking up work

Issues labelled **`agent-ready`** are self-contained: they name the files, link
the contract, and state the acceptance check. Start there. An issue without
those three things is not ready — ask for them rather than guessing.

Labels: `area:core|tabs|analysis|builder|docs`, `type:bug|feat|chore`.

## House style

- Match the surrounding code; there is no build step and no bundler, by design —
  a researcher must be able to open a dashboard from a file server.
- Comment *why*, not *what*. The comments that earned their place in this
  codebase explain a decision or a trap, not a line of syntax.
- If you fix something subtle, leave the measurement behind. The best comments
  here carry numbers.
