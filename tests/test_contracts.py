"""The contracts, checked where a developer will see it.

Every one of these ran only in CI before, which meant they were discovered
after a release rather than before a commit. The scaffold's config.json broke
the schema check and stayed broken across four releases, because `pytest` had
nothing to say about it and CI's word arrived later.
"""
import json
import os
import re

import pytest

jsonschema = pytest.importorskip("jsonschema")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = os.path.join(ROOT, "docs", "contracts", "config.schema.json")
SCAFFOLD = os.path.join(ROOT, "packages", "dims-case-scaffold", "config.json")


def schema():
    with open(SCHEMA) as fh:
        return json.load(fh)


def scaffold():
    with open(SCAFFOLD) as fh:
        return json.load(fh)


def test_the_schema_is_a_valid_schema():
    """It validates every case repo, so a broken one fails them all at once."""
    jsonschema.Draft202012Validator.check_schema(schema())


def test_the_scaffold_ships_no_study():
    """It used to carry a session1/session2 fixture and a hardcoded author.

    Every project ever created from it inherited someone else's study and had
    to notice in order to remove it.
    """
    cfg = scaffold()
    assert cfg.get("videoIDs") == [], cfg.get("videoIDs")
    assert not cfg.get("dataTypes"), cfg.get("dataTypes")
    for key in ("authors", "contacts"):
        assert not cfg.get(key), f"{key} is filled in: {cfg.get(key)!r}"


def test_the_scaffold_satisfies_the_schema_once_it_is_filled_in():
    """A scaffold is not a study, and the difference is `videoIDs`.

    `minItems: 1` is right for a study — a dashboard with no recordings shows
    nothing — and wrong for a scaffold, which has not been filled in yet. So
    the scaffold is validated in the state it is actually used in. Validating
    it as a study is what made CI red for four releases.
    """
    cfg = dict(scaffold())
    cfg["videoIDs"] = ["s01"]
    cfg["dataTypes"] = {"s01": ["bodysync"]}
    errors = list(jsonschema.Draft202012Validator(schema()).iter_errors(cfg))
    assert not errors, [f"{list(e.path)}: {e.message}" for e in errors]


def test_an_empty_study_config_is_rejected():
    """The other half: the schema must still refuse a study naming nothing."""
    errors = list(jsonschema.Draft202012Validator(schema()).iter_errors(scaffold()))
    assert errors, "a config with no recordings should not validate as a study"


def test_every_path_the_readme_points_at_exists():
    """The README is the map. A dead link there sends a contributor nowhere."""
    text = open(os.path.join(ROOT, "README.md")).read()
    missing = [t for t in re.findall(r"\((docs/[^)]*)\)", text)
               if not os.path.exists(os.path.join(ROOT, t))]
    assert not missing, missing


def test_every_contract_the_docs_cross_reference_exists():
    """Contracts link to each other; the site turns those into page links."""
    contracts = os.path.join(ROOT, "docs", "contracts")
    missing = []
    for name in sorted(os.listdir(contracts)):
        if not name.endswith(".md"):
            continue
        text = open(os.path.join(contracts, name)).read()
        for target in re.findall(r"\]\((?!https?:|#)([^)]+)\)", text):
            target = target.split("#")[0]
            if not target:
                continue
            full = os.path.normpath(os.path.join(contracts, target))
            if not os.path.exists(full):
                missing.append(f"{name} -> {target}")
    assert not missing, missing
