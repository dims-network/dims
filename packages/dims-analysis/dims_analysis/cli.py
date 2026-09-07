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
    steps = discover()

    wanted = None
    if args.steps and args.steps != "all":
        wanted = {s.strip() for s in args.steps.split(",") if s.strip()}
        unknown = wanted - set(steps)
        if unknown:
            print(f"error: unknown step(s): {', '.join(sorted(unknown))}", file=sys.stderr)
            print(f"       available: {', '.join(sorted(steps)) or '(none)'}", file=sys.stderr)
            return 2

    ctx = StepContext(project_dir, config, output_dir=args.output_dir)
    ran, skipped, failed = [], [], []

    for sid, step in sorted(steps.items()):
        if wanted is not None and sid not in wanted:
            continue
        if not step.gate(config):
            skipped.append(sid)
            continue
        print(f"=== {sid} ===")
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
            ran.append(sid)

    print()
    print(f"ran: {', '.join(ran) or '(none)'}")
    if skipped:
        print(f"skipped (not enabled in config): {', '.join(skipped)}")
    if failed:
        print(f"FAILED: {', '.join(failed)}", file=sys.stderr)
        return 1
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

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
