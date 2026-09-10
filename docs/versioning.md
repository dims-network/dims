# Versions, vendoring and the pin

How one fix reaches every study, and why a study can be archived and still make
sense years later. This is the explanation; the commands are on
[the `dims-case` reference](reference/cli/dims-case.md).

```
                dims-network/dims          all the code, released as vX.Y.Z
                       │
        ┌──────────────┴──────────────┐
  vendor/ , pinned            dims-analysis, installed
  what the browser loads      what rebuilds the assets
  (bot PR; CI rebuilds it     (pip install -e ./dims —
   from the release tag)       not on PyPI yet)
        │                              │
   ┌────┴─────┬──────────────┐         └── used by every study, and by the builder
case-demo  case-ortho  case-karnatak
 (public)   (public)     (PRIVATE — data lives outside the repository)
```

## One version number, both halves

A study depends on the core twice, in two different ways: **the browser loads a
copy** of `dims-core` and `dims-tabs` from its own `vendor/` directory, and **the
analyses are installed** as a Python package that rebuilds its assets.

Both halves are released together and are meant to carry the same version number.
A study's `dims-case.json` records it once, as `dimsCore`, taken from
`git describe` on the core it was vendored from — and that is what the vendor
check compares against.

**The assets record their version separately.** Every payload carries
`provenance.core_version`, read from `dims_analysis.__version__`. Nothing compares
the two: the only check on a study's committed output is `payload_version` against
the format version the dashboard reads. So "one version number" is the intent that
`tests/test_release.py` enforces *across packages* — it is not a single string the
tooling reads twice, and the two can drift if a release forgets to bump the
literals.

That is the whole reason for lockstep versioning. A study whose frontend and
analyses came from different releases can display a payload it half understands,
which is worse than refusing it.

## How a fix travels

1. It is made **once**, in the monorepo.
2. A release is tagged.
3. Each study's **own** scheduled workflow notices, and opens a pull request in
   its own repository changing `dimsCore` and refreshing `vendor/`. That is
   [`dims-case sync`](reference/cli/dims-case.md#sync--take-a-new-core). Studies
   pull; the core does not push — otherwise it would need write access to every
   study.
4. The study's CI checks the result — [`dims-case check --release`](reference/cli/dims-case.md#check--verify-the-pin).
5. If the payload format moved, the study rebuilds its assets. Until it does, the
   dashboard says so rather than drawing a blank panel.

**Propagation is a version bump, not a merge.** Nothing is ever copied between
studies.

## Why the check rebuilds instead of comparing records

A study records a hash of what its `vendor/` should be. Comparing against that
record catches a hand-edited file — but **a `vendor/` copied from a modified core
agrees with its own record perfectly.** Both sides of that comparison came from
the study.

So the release check rebuilds `vendor/` from a core checkout and compares against
that, rather than against the study's record. It is the one comparison a fork
cannot pass. `dims-case check` is the
offline version and `dims-case check --release` is what CI runs; only the second
is evidence.

This is why case repositories do not drift: editing vendored code by hand is a
red X, not a silent fork.

**Never edit `vendor/`.** Fix it in the monorepo and bump the pin.

## What a study owns, and what the core keeps rewriting

`sync` has to know what it may overwrite, and the answer is three tiers — the
full table is in [the `dims-case` reference](reference/cli/dims-case.md#the-three-tiers-of-file-ownership).
In short: `vendor/`, `index.html`, the workflows, the private hooks and `serve.py`
are regenerated every sync; `build_assets.py`, `requirements.txt` and `data.local.json.example`
are seeded once and become yours the moment you edit one; `config.json`,
`assets/`, `opt/` and `tabs/` are never touched.

A study needing a different parameter changes `config.json` under `analysis` —
**never a copied analysis script.** Keeping a fork of a step is exactly what the
monorepo exists to make unnecessary, and it puts the study outside the guarantee
above.

## Archiving

Because the analysis code that produced a study's results is inside the study, at
the version that produced them, a case repository can be archived as it stands and
still be read. That is the point of vendoring a copy rather than depending on a
package that may be yanked, moved or changed.

**One caveat, and it is real.** A dashboard is not self-contained in the browser —
`index.html` loads five libraries from a CDN, so one opened without a network shows
an empty page. That caveat and the issue tracking it are on
[`architecture.md`](architecture.md#why-no-build-step).

## See also

- [`contracts/case.md`](contracts/case.md) — the shape of a case repository.
- [`architecture.md`](architecture.md) — why the code is arranged this way.
- [`reference/cli/dims-case.md`](reference/cli/dims-case.md) — the commands.
