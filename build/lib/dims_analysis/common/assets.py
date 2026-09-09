"""Where a study's data actually lives.

A private study keeps its recordings and derived time series out of git, so
`assets/` inside the repository is empty and the real files sit somewhere else --
named in `data.local.json`, which is untracked:

    { "assetsRoot": "/Users/me/Data/karnatak/assets" }

`serve.py` has always honoured that. The analysis did not, so running a step from
a private case directory found no input at all and reported every pair as
"file not found" -- a confusing failure, because the data is right there on the
disk and the dashboard can read it.

Resolution rules, deliberately narrow:

  * no `data.local.json`, no `assetsRoot`, or a path that is not a directory
    -> paths are used exactly as given, which is the public-study case;
  * only paths under `assets/` are redirected. An explicit `--output-dir
    /tmp/somewhere` is the caller being specific and is never rewritten;
  * an absolute path is never rewritten either.
"""
import json
import os

MARKER = 'data.local.json'
_ASSETS = 'assets'


def assets_root(project_dir='.'):
    """The configured external assets root, or None to use the project's own."""
    try:
        with open(os.path.join(project_dir, MARKER)) as fh:
            root = json.load(fh).get('assetsRoot')
    except (OSError, ValueError):
        return None
    if not root:
        return None
    root = os.path.abspath(os.path.expanduser(root))
    return root if os.path.isdir(root) else None


def resolve(path, project_dir='.', root=None):
    """Map a project-relative `assets/...` path onto the external root."""
    if not path or os.path.isabs(path):
        return path
    root = root if root is not None else assets_root(project_dir)
    if not root:
        return path
    parts = os.path.normpath(path).split(os.sep)
    if not parts or parts[0] != _ASSETS:
        return path
    return os.path.join(root, *parts[1:]) if len(parts) > 1 else root


def describe(project_dir='.'):
    """One line for a step to print, or None when nothing is redirected."""
    root = assets_root(project_dir)
    return f'assets resolved through {MARKER}: {root}' if root else None
