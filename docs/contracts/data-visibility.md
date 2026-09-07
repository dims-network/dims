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
  "dimsCore": "1.2.0",
  "publishable": []
}
```

`visibility` is `"public"` or `"private"`, chosen once when the case is created.
`publishable` is a **default-deny allowlist**: for a private case, nothing under
`assets/` may be committed unless a path here says so.

## What `private` turns on

Four independent guards, ordered by how early they catch the mistake:

1. **Pre-commit hook** — refuses to stage restricted paths. This is the one that
   matters: it stops data before it enters history, where removing it needs a
   rewrite and the data has already been pushed.
2. **Pre-push hook** — the same check across the push range.
3. **CI** — fails if any *tracked* file matches a restricted path, and fails if
   `"visibility": "private"` while the GitHub repo is public. That last check
   catches the case nobody plans for: someone flipping visibility months later.
4. **`AGENTS.md` banner** — states the rule where an automated contributor will
   read it before touching anything.

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
- `assets/MANIFEST.json` is tracked and holds **names, checksums and provenance
  — never content**, so CI and the config validator can confirm a case is
  complete without ever seeing the data.
- Private cases are not wired to GitHub Pages. They are served locally.

## Going public

An explicit, gated transition. Never a default, never a side effect.

1. Run the anonymisation step over every video.
2. **Verify frame by frame.** Detection-based masking misses; the tooling's own
   documentation says it is a starting point, not a solution.
3. Move the cleared directories onto `publishable`.
4. Flip `visibility` to `"public"`.
5. Only now does the Pages workflow become available.

## For automated contributors

In a private case: never push, and never move asset content into anything
external — an issue, a prompt, a hosted page, a paste. Describing the data is
fine. Reproducing it is not.

## Acceptance

- `git add -f assets/videos/x.mp4` in a private case is refused.
- Bypassing with `--no-verify` produces a red CI run.
- Making a `"private"` case's repo public produces a red CI run.
- A private case runs locally, renders every tab, and leaves `git status` clean.
