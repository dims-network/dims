# `dims-case`

Create a study, or refresh the core it has vendored. Four subcommands, each with
one job:

```
dims-case new   <name> --visibility public|private [--dir PATH]
dims-case adopt <path> --name NAME --visibility public|private
dims-case sync  <path> [--version VERSION]
dims-case check <path> [--release]
```

`sync` is what the version-bump bot runs. `check` is what a study's CI runs. The
work itself lives in `dims_case.core`, so this command and
[the no-code builder](../../../apps/builder/README.md) produce the same study rather than
two slightly different ones.

> `tools/dims-case` in the core checkout is a small shim kept for anyone with that
> path in their fingers — it puts the package on `sys.path` and calls the same
> `main()`. **The command is `dims-case`**, installed as a console script.

---

## `new` — start an empty study

```sh
dims-case new my-study --visibility public     # creates ./case-my-study
```

| argument | |
|---|---|
| `name` | the study's name. The directory becomes `case-<name>` unless `--dir` says otherwise |
| `--visibility` | **required**, `public` or `private`. The researcher's decision, recorded — never inferred |
| `--dir PATH` | put the study somewhere other than `./case-<name>` |

**It refuses a directory that exists and is not empty**, and exits non-zero. That
is deliberate: `new` can never scribble over someone's data. Converting an
existing study is `adopt`, below.

What it writes:

- the scaffold, copied from `packages/dims-case-scaffold`,
- `vendor/dims-core/` and `vendor/dims-tabs/`, with a SHA-256 recorded per
  directory,
- `dims-case.json` — see [its fields](#dims-casejson),
- the GitHub workflows for the declared visibility,
- for a private study, the commit and push hooks and the `.gitignore` block.

A private study is told its two remaining steps, because neither can be done for
it: enabling the hooks in the clone, and creating `data.local.json` from the
example.

## `adopt` — convert a study you already have

```sh
dims-case adopt ./old-dashboard --name ortho --visibility private
```

Requires the path to be a directory containing a `config.json`; it exits with
"is this a study?" if not.

**It never reads or writes `config.json`, and never touches a file under
`assets/`.** Those are the study's own. It does *create* the seven asset
subdirectories if they are missing — `rqa`, `crqa`, `crosswavelet`, `timeseries`,
`videos`, `transcripts`, `elan` — but nothing already in them is read, moved or
rewritten.

What it adds is what a case needs and nothing else: `serve.py`, a rewritten
`index.html`, those directories, the vendored core, the study's own tabs
registered in `index.html`, `dims-case.json`, the workflows, and the private guards
if declared private.

An existing `dims-case.json` has its **`publishable` list preserved**; everything
else in the file is rewritten.

### It sorts out your `opt/` directory for you

If the study has an `opt/` directory, `adopt` reports what is in it in two groups,
because the right action differs:

- **Files that now come from the core** — `step_RQA.py`, `step_cRQA.py`,
  `step_crosswavelet.py`, `requirements.txt`. These can go; run them with
  `dims-analysis run --config config.json` instead.
- **Files that look specific to this study** — any other `.py` or `.txt`. **Keep
  these.** Study-specific data preparation belongs with the study; only the shared
  analyses moved to the core. Note the filter: a `.sh`, `.R`, `.ipynb` or `.csv` in
  `opt/` is reported in neither group and passes unmentioned.

It only reports. It deletes nothing.

## `sync` — take a new core

```sh
dims-case sync ./case-my-study --version v1.4.3
```

With no `--version`, the version is read from the core checkout with
`git describe --tags --abbrev=0`.

Refreshes everything that is generated: the vendored directories, `index.html`,
the study-owned tab registrations, the seeded scaffold files, **the workflows**,
and — for a private study — **the hooks**. The last two matter more than they
look. A study that kept whatever CI it was created with is how five repositories
ended up with five drifted copies; and a fix to a privacy hook has to reach
studies that already exist, which a bump is the only route for.

It prints the transition (`my-study: 1.4.2 -> 1.4.3`) and then any notes about
shadowed tabs or stale assets — **at bump time, which is when the owner is
deciding what to do about it**, rather than at check time when they have moved on.

## `check` — verify the pin

```sh
dims-case check .              # offline, against the study's own record
dims-case check . --release    # against this core checkout
```

Exits `1` and prints `::error::` lines — the GitHub Actions annotation format —
when the vendored core does not match, or when the study's committed analysis
outputs are from a payload version the pinned core no longer reads.

### The two modes are not the same check, and only one catches a fork

| | compares against | catches | misses |
|---|---|---|---|
| `check` | the hashes recorded in the study's own `dims-case.json` | someone hand-editing a file under `vendor/` | a `vendor/` that was copied from a **modified** core — it agrees with itself perfectly |
| `check --release` | `vendor/` rebuilt from the core checkout the command is running from | that fork | nothing of the above |

CI runs the release's own copy of the command, so `--release` means *the version
this study pins*, and it is a comparison a fork cannot pass. **The offline mode
alone is not evidence that a study is running unmodified core code.**

### Warnings, which do not fail the check

- **A shadowed tab** — the study owns a tab file whose `id` is now a built-in, so
  it registers nothing. The dashboard still works; the study is just carrying a
  file that does nothing.
- **A private study whose clone has not enabled the hooks.** They are tracked, but
  git does not run them until the clone opts in with
  `git config core.hooksPath .githooks`, and forgetting is silent — which is the
  one thing a guard may not be. CI still stops data, but only after a push.

On success it says which comparison passed: `vendored core matches core 1.4.3` —
the recorded `dimsCore`, which is stored without the leading `v` — or
`vendored core matches the recorded pin`.

---

## `dims-case.json`

| field | is |
|---|---|
| `case` | the study's name |
| `visibility` | `public` or `private`, as declared |
| `dimsCore` | the core version this study pins |
| `publishable` | paths exempt from the restricted-directory rule. Preserved across `adopt` and `sync` |
| `restricted` | the directories the privacy guards refuse to commit. Written from one definition in the core so the hook and CI cannot disagree |
| `vendorHashes` | SHA-256 per vendored directory — what plain `check` compares |
| `seededHashes` | written by `sync`, for the seeded-once scaffold files |

## The three tiers of file ownership

`sync` has to know what it may overwrite. Three answers:

| tier | files | rule |
|---|---|---|
| **regenerated** | `vendor/`, `index.html`, the workflows, the private hooks, `serve.py` | overwritten on every sync. Do not edit them in the study |
| **seeded once** | `build_assets.py`, `requirements.txt`, `data.local.json.example` | written at creation, then refreshed **only while still byte-identical** to what was seeded. Edit one and it becomes yours, tracked by `seededHashes` |
| **never touched** | `config.json`, `assets/`, `opt/`, `tabs/` | the study's own. `sync` touches none of them; `adopt` creates empty `assets/` subdirectories but changes nothing inside |

## See also

- [`contracts/case.md`](../../contracts/case.md) — the shape of a case repository.
- [`contracts/data-visibility.md`](../../contracts/data-visibility.md) — what
  `private` actually turns on.
- [`dims-analysis`](dims-analysis.md) — running the analyses inside a study.
