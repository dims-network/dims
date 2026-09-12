"""The plumbing every step repeats between reading a config and writing a file.

Three steps, three copies, and they had already drifted. The merge report -- the
loop that prints what a write kept and what it replaced -- was byte-identical in
rqa.py, crqa.py and crosswavelet.py, which means the fourth step would have
copied it too and the first one to change would have been the only one that
changed.

The `Step` adapter was worse than duplication. All three set `sys.argv` and
`os.chdir`-ed into the project, then called `main()`, which read its input
directory from a module global that `main()` rewrote in place. `assets.resolve`
returns an already-absolute path unchanged, so once one private study had
resolved it, a second `Step.run()` in the same process would have read the first
study's time series while writing into the second study's output, in silence.
Nothing ships that runs two projects in one process, which is why it survived.
Passing the paths in is what removes it, and this module is what keeps passing
them in from meaning the argparse block gets written twice.
"""
from __future__ import annotations

import argparse
import os

from dims_analysis.common import assets as _assets
from dims_analysis.common import config as _config
from dims_analysis.common import results as _results


def parse_args(prog: str, description: str, default_output_dir: str,
               argv=None) -> argparse.Namespace:
    """`--config`, `--output-dir`, `--window` and `--step`, once.

    `--window` and `--step` default to None rather than to a number, because
    None is what "the study's config decides" looks like. A numeric default here
    would silently outrank `analysis.<step>.window`, which is the defect
    tests/test_tuning.py exists for.
    """
    parser = argparse.ArgumentParser(prog=prog, description=description)
    parser.add_argument('--config', default='config.json',
                        help='Path to config.json')
    parser.add_argument('--output-dir', default=default_output_dir,
                        help=f'Output directory (default: {default_output_dir})')
    parser.add_argument('--window', type=float, default=None,
                        help=f'Windowed-metric window size in seconds '
                             f'(default: analysis.{prog}.window, else 20)')
    parser.add_argument('--step', type=float, default=None,
                        help=f'Windowed-metric step in seconds '
                             f'(default: analysis.{prog}.step, else 1)')
    return parser.parse_args(argv)


def tuning(config: dict, step_id: str, window_sec, step_sec,
           target_recurrence_default: float) -> tuple:
    """(window_sec, step_sec, target_recurrence): a flag wins, then the config.

    Tuning belongs in the study's config, not in a module constant and not only
    on a command line the step adapter never passed. A flag still wins where one
    is given, so a one-off run can override without editing the study.

    Routed through `config.tuned_number`, which refuses `"window": "20s"` by
    name rather than quietly analysing at the default and leaving the study
    wondering why its setting had no effect.
    """
    window = window_sec if window_sec is not None else \
        _config.tuned_number(config, step_id, 'window', 20.0)
    step = step_sec if step_sec is not None else \
        _config.tuned_number(config, step_id, 'step', 1.0)
    target = _config.tuned_number(
        config, step_id, 'targetRecurrence', target_recurrence_default)
    return window, step, target


def resolve_io(input_dir: str, output_dir: str, project_dir: str = '.') -> tuple:
    """Both directories through data.local.json, the banner, and the mkdir.

    Both of them, which is the point: a private study's data lives outside the
    repository, and resolving only one of the two ends with a log line saying
    the mechanism worked beside a read of a path that does not exist.
    """
    note = _assets.describe()
    if note:
        print(note)
    resolved_in = _assets.resolve(input_dir, project_dir)
    resolved_out = _assets.resolve(output_dir, project_dir)
    os.makedirs(resolved_out, exist_ok=True)
    return resolved_in, resolved_out


def payload_writer(output_dir: str, output_name: str, label: str,
                   owner: str | None = None, expected: dict | None = None):
    """A `write(video_id, payload) -> report` for `main()`.

    `Step.run()` passes `ctx.write_result` instead. One function is handed to
    the analysis either way, so the two entry points cannot drift into writing
    two different files -- which is what the adapter's "INTERIM: replacing this
    means giving run() the real parameters" was deferring.

    `owner` is that step's id, and both entry points must pass the same one:
    a step that owns its entries under `run()` and not under `main()` would
    prune on one path and accumulate on the other.
    """
    def write(video_id: str, payload: dict) -> dict:
        path = os.path.join(output_dir, output_name.format(video_id=video_id))
        body = {"video_id": video_id}
        body.update(payload)
        report = _results.write_payload(path, body, owner=owner,
                                        expected=expected)
        print(f"\nSaved {label} to {path}")
        return report
    return write


def report_merge(report: dict) -> None:
    """Print what a write kept, what it replaced, and what it removed.

    Every part is worth saying. A silent keep leaves stale results in a file
    that looks freshly written; a silent replace is how a study loses the
    results of an analysis it owns; and a silent removal would be that same
    failure once more. `results.compare_entries` computes it, three steps
    printed it identically, and it belongs in one place.

    A kept entry is **not** announced as being "from another analysis" any
    more. It might be, and that is the case the merge exists for -- but it can
    equally be this step's own entry in a file written before ownership was
    recorded, and a study chasing a result it did not ask for was sent looking
    for a second analysis that does not exist.
    """
    report = report or {}
    for key, names in report.get('kept', {}).items():
        print(f"  kept {len(names)} existing {key} entr"
              f"{'y' if len(names) == 1 else 'ies'} this run did not write: "
              f"{', '.join(names)}")
        print(f"       they belong to another analysis, or to a run from before "
              f"this file recorded who wrote what. `dims-analysis prune` "
              f"removes the ones the config no longer asks for.")
    for key, names in report.get('replaced', {}).items():
        print(f"  replaced {len(names)} existing {key} entr"
              f"{'y' if len(names) == 1 else 'ies'}: {', '.join(names)}")
    for key, names in report.get('pruned', {}).items():
        print(f"  removed {len(names)} {key} entr"
              f"{'y' if len(names) == 1 else 'ies'} this analysis wrote before "
              f"and no longer produces: {', '.join(names)}")
