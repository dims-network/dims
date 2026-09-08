# Working on DIMS as an automated contributor

The issue tracker links here, so this is likely the first file you read. It is
deliberately short: the map of what to read for a given task is the **Working
on DIMS** table in [`README.md`](README.md), and repeating it here would give
this project two maps that drift apart. Read the one file that table names for
your task, and no more.

What follows is only what a machine contributor gets wrong more often than a
person does.

## The data is real, and some of it identifies people

Several studies hold video of identifiable participants — children among them.
A case repository declares this in `dims-case.json`, and the machinery in
[`docs/contracts/data-visibility.md`](docs/contracts/data-visibility.md)
enforces it. Three consequences, in order of how badly they end:

- **Never move data content into an external service.** Not into an issue, a
  pull request body, a hosted page, a paste bin, or a prompt to another
  service. A filename may be discussed. Contents may not.
- **Never commit anything under `assets/`** in a study that declares
  `"visibility": "private"`. Hooks refuse it and CI refuses it, but the guards
  exist because the mistake is easy, not because it is survivable: removing
  data from a pushed history means a rewrite.
- **Never copy data into the repository to make a script work.** If a path is
  wrong, the fix is `data.local.json`, which points at where the data already
  lives. A script that only runs after data is copied in is a broken script.

Assume private until `dims-case.json` says otherwise.

## One copy of the code

Case repositories carry a pinned, vendored copy of this core. It is verified
byte-for-byte against the release tag in CI, so editing anything under
`vendor/` does not produce a fix — it produces a red build and, if it somehow
merged, a fork.

Fix the code here; a study takes the fix by bumping `dimsCore`.

## Finish the verification, not just the change

Every contract ends with an acceptance check that can be run without reading
any other file. Run it. Where a change concerns a guard, a test or a CI job,
the acceptance check is specifically that it **fails when it should** — this
repository has twice shipped a check that could not fail: a privacy hook that
inspected an empty staging area, and a vendor check with no callers.

## The reference study is not optional

`examples/reference/` is a synthetic study whose answers are known before
anything runs: a 2 s sine recurs at 2 s, a copy delayed 0.4 s puts its
cross-recurrence line 0.4 s off the diagonal, two independent red noises beat a
95 % level 5 % of the time, and the wavelet constants are Torrence & Compo's
published ones. Every claim in it is checked against pyrqa, against that paper,
or against an independently computed null — never against this project's own
previous output.

**Any change to `steps/rqa.py`, `steps/crqa.py`, `steps/crosswavelet.py` or
anything under `common/` runs it, and it must be green before the change is
committed:**

```sh
pip install -e packages/dims-analysis && pip install pytest pyrqa
python -m pytest examples/reference/tests -q
```

`pyrqa` is `importorskip`ed, so a machine without OpenCL stays green while the
independent oracle for DET, LAM and RR silently does not run. Check `-rs` and
make sure the skips are ones you meant. CI installs `pocl-opencl-icd` and fails
outright if pyrqa is missing, for exactly this reason.

This matters beyond this repository. The analyses are **not** vendored — a
study installs them from the core it pins — so a defect that gets past here
reaches `case-demo`, `case-ortho` and `case-karnatak` the moment they bump, and
lands in their committed assets. That is how the nine already found got where
they were. The generated `core-update.yml` in every study therefore runs this
same suite against the candidate release before it will open the bump PR.

`tests/baseline.json` pins every number the analyses currently produce.
When it fails, **read the diff before doing anything else**: it is telling you
what your change did to the answers. Regenerate it only after deciding the new
numbers are better, with `python examples/reference/tests/make_baseline.py`, and
say in the commit message why each number moved. Regenerating first is how a
regression becomes the new normal.

## Scope

Do what the issue asks. Issues labelled `agent-ready` name the files, link the
contract and state the acceptance check; an issue without those three is not
ready, and the right move is to ask rather than to guess. If you find a second
problem while fixing the first, say so — do not quietly widen the change.
