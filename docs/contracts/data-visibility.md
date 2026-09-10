# Contract: public and private data

Much DIMS data is video of identifiable people. Visibility is therefore
**declared by the researcher, never inferred**, and enforced by machinery rather
than by memory.

## Declare it

`dims-case.json`, at the root of every case repo:

```json
{
  "case": "karnatak",
  "visibility": "private",
  "dimsCore": "1.4.1",
  "publishable": [],
  "restricted": [
    "assets/videos",
    "assets/timeseries",
    "assets/transcripts",
    "assets/elan",
    "assets/motion_tracking"
  ]
}
```

`visibility` is `"public"` or `"private"`, chosen once when the case is created.
`publishable` is a **default-deny allowlist**: for a private case, nothing under
`assets/` may be committed unless a path here says so. `restricted` is what the
allowlist opens exceptions to; `dims-case new` writes it, and every guard reads
it from here so the rule lives in one place. If it is absent the guards fall
back to the core's own list rather than passing everything — an earlier version
of this example omitted the key, and a study written by hand from it had guards
that declared themselves private and blocked nothing.

## What `private` turns on

Three independent guards, ordered by how early they catch the mistake:

1. **Pre-commit hook** — refuses to stage restricted paths. This is the one that
   matters: it stops data before it enters history, where removing it needs a
   rewrite and the data has already been pushed.
2. **Pre-push hook** — the same check across the push range.
3. **CI** — fails if any *tracked* file matches a restricted path, and fails if
   `"visibility": "private"` while the GitHub repo is public. That last check
   catches the case nobody plans for: someone flipping visibility months later.

Enable the hooks once per clone:

```sh
git config core.hooksPath .githooks
```

A `.gitignore` is not one of these guards. It is a convention, and `git add -f`
walks straight through it.

## Working with private data comfortably

This half matters as much as the guards: a guard that makes the work painful
gets disabled.

- Data lives **outside the repo**, at a path named in `data.local.json`
  (untracked). `serve.py` and `dims-analysis` both resolve assets through it, so
  everything runs against real data with an empty tracked `assets/`.
- `assets/MANIFEST.json` is tracked and holds **names, sizes and checksums —
  never content**, so a rebuild can be confirmed complete without anyone seeing
  the data. Write it with `dims-analysis manifest` (or `build_assets.py
  --write-manifest`) once the assets are right; check it with `dims-analysis
  manifest --check`, which compares names and sizes, or `--check --deep`, which
  verifies the checksums and on a study with video takes minutes. Both hooks
  and the CI guard exempt this file by name, which is exactly why it may never
  carry content.
- Private cases are not wired to GitHub Pages. They are served locally.

## Going public

An explicit, gated transition. Never a default, never a side effect.

1. Run the anonymisation step over every video.
2. **Verify frame by frame.** Detection-based masking misses; the tooling's own
   documentation says it is a starting point, not a solution.
3. Move the cleared directories onto `publishable`.
4. Flip `visibility` to `"public"`.
5. Only now does the Pages workflow become available.

## Working in a private case

In a private case: never push, and never move asset content into anything
external — an issue, a prompt, a hosted page, a paste. Describing the data is
fine. Reproducing it is not.

## Acceptance

- `git add -f assets/videos/x.mp4` in a private case is refused.
- Bypassing with `--no-verify` produces a red CI run.
- Making a `"private"` case's repo public produces a red CI run.
- A private case runs locally, renders every tab, and leaves `git status` clean.
