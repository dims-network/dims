"""``dims-analysis`` — run the analyses a config asks for.

Replaces a hardcoded list of three functions, where adding one analysis meant
editing four separate files.

It also **fails loudly**. The runner this supersedes emitted an exit-code
sentinel that nothing ever read, so a crashed analysis scrolled past in the log
and the build reported success — leaving a dashboard with missing data and no
indication anything was wrong.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from dims_analysis.base import StepContext
from dims_analysis.registry import discover


def _load_config(path: str) -> dict:
    with open(path) as fh:
        return json.load(fh)


def cmd_list(args) -> int:
    steps = discover()
    if not steps:
        print("no steps registered")
        return 0
    width = max(len(s) for s in steps)
    for sid, step in sorted(steps.items()):
        print(f"  {sid:<{width}}  {step.description or step.__class__.__name__}")
    return 0


def cmd_run(args) -> int:
    if not os.path.exists(args.config):
        print(f"error: no such config: {args.config}", file=sys.stderr)
        return 2
    config = _load_config(args.config)
    project_dir = os.path.dirname(os.path.abspath(args.config)) or "."
    import_problems: list = []
    steps = discover(import_problems)

    unloadable = {name for name, _ in import_problems}

    wanted = None
    if args.steps and args.steps != "all":
        wanted = {s.strip() for s in args.steps.split(",") if s.strip()}
        # A step that is registered but failed to import is not unknown. Saying
        # "unknown step: crosswavelet" when pycwt is missing sends the user
        # looking for a typo instead of an install.
        unknown = wanted - set(steps) - unloadable
        if unknown:
            print(f"error: unknown step(s): {', '.join(sorted(unknown))}", file=sys.stderr)
            print(f"       available: {', '.join(sorted(steps)) or '(none)'}", file=sys.stderr)
            return 2

    ctx = StepContext(project_dir, config, output_dir=args.output_dir)
    ran, skipped, failed, empty = [], [], [], []

    # A step that could not be imported is only a warning if nothing wanted it.
    # A missing pycwt used to mean the one analysis the config asked for never
    # ran, with a warning in the log and an exit code of 0.
    blocking = unloadable if wanted is None else (unloadable & wanted)
    if blocking:
        for name, exc in import_problems:
            if name in blocking:
                print(f"error: step '{name}' could not be loaded: {exc}", file=sys.stderr)
        print(f"       install its dependencies, or pass --steps without it",
              file=sys.stderr)
        if not args.keep_going:
            return 1
        failed.extend(sorted(blocking))

    for sid, step in sorted(steps.items()):
        if wanted is not None and sid not in wanted:
            continue
        if not step.gate(config):
            skipped.append(sid)
            continue
        print(f"=== {sid} ===")
        before = ctx.output_snapshot(step)
        try:
            step.run(config, ctx)
        except Exception as exc:  # noqa: BLE001 - reported, then surfaced in the exit code
            failed.append(sid)
            print(f"error: step '{sid}' failed: {exc}", file=sys.stderr)
            if args.traceback:
                import traceback
                traceback.print_exc()
            if not args.keep_going:
                break
        else:
            # Producing nothing is the failure mode that actually happens, and
            # it does not raise: every step catches its own unreadable-input
            # case, prints a warning and returns. The run then reported success
            # with an empty output directory, and build_assets.py -- which uses
            # check=True -- printed "Asset build complete".
            after = ctx.output_snapshot(step)
            if not _wrote_something(before, after):
                empty.append(sid)
                print(f"error: step '{sid}' was enabled by the config but wrote "
                      f"no output", file=sys.stderr)
                print(f"       expected files in {ctx.output_dir_for(step)}",
                      file=sys.stderr)
                print(f"       the step's own messages above say why; the usual "
                      f"cause is missing input", file=sys.stderr)
                if not args.keep_going:
                    break
            else:
                ran.append(sid)

    print()
    print(f"ran: {', '.join(ran) or '(none)'}")
    if skipped:
        print(f"skipped (not enabled in config): {', '.join(skipped)}")
    if empty:
        print(f"PRODUCED NOTHING: {', '.join(empty)}", file=sys.stderr)
    if failed:
        print(f"FAILED: {', '.join(failed)}", file=sys.stderr)
    return 1 if (failed or empty) else 0


def _wrote_something(before: dict, after: dict) -> bool:
    """True if any file appeared or was rewritten between the two snapshots.

    Comparing snapshots rather than a wall-clock start avoids depending on the
    filesystem's timestamp granularity, and counts a rewritten file -- a re-run
    over the same study writes the same names.
    """
    for path, mtime in after.items():
        if before.get(path) != mtime:
            return True
    return False


def cmd_manifest(args) -> int:
    """Write `assets/MANIFEST.json`, or check the assets against it.

    A private study's data is outside git, so this file is the only thing in
    the repository that says what a complete set of assets looks like. After a
    rebuild it answers the question a green exit code cannot: did it produce
    everything?
    """
    from dims_analysis.common import manifest as mf

    where = mf.path_for(args.project_dir)
    if not args.check:
        m = mf.write(args.project_dir, deep=not args.no_checksums)
        kind = "with checksums" if m["checksums"] else "names and sizes only"
        n = len(m["files"])
        print(f"wrote {where}: {n} file{'' if n == 1 else 's'}, {kind}")
        return 0

    result = mf.compare(args.project_dir, deep=args.deep)
    if result is None:
        print(f"error: no manifest at {where}. Write one with "
              f"`dims-analysis manifest`.", file=sys.stderr)
        return 2
    missing, changed, extra = result
    for rel in missing:
        print(f"missing: {rel}")
    for rel in changed:
        print(f"differs: {rel}")
    for rel in extra:
        print(f"not in the manifest: {rel}")
    if missing or changed:
        print(f"\n{len(missing)} missing, {len(changed)} different. The rebuild "
              f"is not complete.", file=sys.stderr)
        return 1
    # Extra files are not a failure: a study may hold working files the
    # manifest was not asked about.
    print(f"assets match the manifest ({len(mf.load(args.project_dir)['files'])} files"
          + (", checksums verified" if args.deep else ", names and sizes")
          + (f"; {len(extra)} not listed" if extra else "") + ")")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="dims-analysis", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", help="run the analyses this config enables")
    r.add_argument("--config", default="config.json")
    r.add_argument("--steps", default="all", help="comma-separated step ids, or 'all'")
    r.add_argument("--output-dir", default=None, help="override every step's output directory")
    r.add_argument("--keep-going", action="store_true", help="continue after a step fails")
    r.add_argument("--traceback", action="store_true")
    r.set_defaults(func=cmd_run)

    l = sub.add_parser("list", help="show the registered steps")
    l.set_defaults(func=cmd_list)

    m = sub.add_parser("manifest", help="record or verify what assets/ should hold")
    m.add_argument("--project-dir", default=".")
    m.add_argument("--check", action="store_true",
                   help="compare the recorded manifest with what is on disk")
    m.add_argument("--deep", action="store_true",
                   help="with --check, verify checksums as well as sizes")
    m.add_argument("--no-checksums", action="store_true",
                   help="when writing, record names and sizes only (fast on video)")
    m.set_defaults(func=cmd_manifest)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
