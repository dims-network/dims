"""Reading a study's config without turning a typo into a traceback.

Two things about `config.json` have caught people, and both fail in the worst
way available: quietly, or with an error about the wrong thing.

**Case.** The gate keys are written `include_RQA`, `include_cRQA`,
`include_crosswavelet` -- three different conventions in three keys, which is
history rather than design. A study that writes `include_crqa` used to be
skipped in silence by the runner while `build_assets.py`, which matched
case-insensitively, reported that the step would run. Matching is now
case-insensitive everywhere, so the two agree.

**Shape.** `include_RQA` is a list of data types and `include_cRQA` a list of
pairs, but `include_elan` and the tab-owned keys are plain booleans. Writing
`"include_RQA": true` -- which is what anyone assumes from the name, and what
the getting-started page told people to write -- produced
`TypeError: 'bool' object is not iterable` from inside the step, six frames
from anything the author wrote.
"""
from __future__ import annotations


class ConfigError(Exception):
    """A config problem stated in terms of the file the author edited."""


def gate_value(config: dict, key: str):
    """The value under `key`, matched case-insensitively. None if absent.

    Two spellings of the same key in one file is an error, not a preference.
    Silently taking the exact match would resolve
    `{"include_cRQA": [], "include_crqa": [["a","b"]]}` to "off", which is the
    opposite of what whoever added the second line meant.
    """
    wanted = key.lower()
    found = [(k, v) for k, v in config.items() if k.lower() == wanted]
    if len(found) > 1:
        names = ", ".join(f'"{k}"' for k, _ in sorted(found))
        raise ConfigError(
            f"config.json has {names} -- the same key spelled more than one "
            f"way. Keys are matched case-insensitively, so which one applies "
            f"would be arbitrary. Keep one.")
    return found[0][1] if found else None


def enabled(config: dict, key: str) -> bool:
    """Whether a step gated by `key` should run at all."""
    return bool(gate_value(config, key))


def as_list(config: dict, key: str, what: str) -> list:
    """The list under `key`, or a message naming the file and the fix.

    `what` completes the sentence "expects a list of ..." -- it is what the
    author has to write instead, so it goes in the error rather than in a
    docstring they will not read.
    """
    value = gate_value(config, key)
    if value is None or value is False:
        return []
    if value is True:
        raise ConfigError(
            f'config.json: "{key}": true is not enough -- this key expects a '
            f'list of {what}, and true does not say which. Write, for example: '
            f'"{key}": {_example(key)}')
    if isinstance(value, str):
        raise ConfigError(
            f'config.json: "{key}" is a single string; it expects a list of '
            f'{what}. Write ["{value}"] rather than "{value}".')
    if not isinstance(value, (list, tuple)):
        raise ConfigError(
            f'config.json: "{key}" should be a list of {what}, not '
            f'{type(value).__name__}.')
    return list(value)


def _example(key: str) -> str:
    pairwise = key.lower() in ("include_crqa", "include_crosswavelet")
    return '[["bodysync", "neuralsync"]]' if pairwise else '["bodysync"]'
