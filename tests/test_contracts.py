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


def test_the_figure_layout_vocabulary_is_the_same_in_every_file_that_names_it():
    """Where the network can put a node is written down four times.

    SPOTS in packages/dims-tabs/figure-geometry.js draws them -- the tab and the
    wizard's diagram both draw from it -- the `part` enum in the config schema
    accepts them, FIGURE_PARTS in the builder's validate.py warns about them, and
    the builder's own dropdown offers them. Nothing connects the four, and the
    failure is quiet in the direction that matters: a part one of them has not
    heard of is stacked beside the figure by the tab, which reads as a layout the
    study chose rather than a name it got wrong.
    """
    schema = json.load(open(os.path.join(ROOT, "docs/contracts/config.schema.json")))
    net = schema["properties"]["include_network"]["oneOf"][1]
    from_schema = set(net["properties"]["effectors"]["items"]["properties"]["part"]["enum"])

    source = open(os.path.join(ROOT, "packages/dims-tabs/figure-geometry.js")).read()
    body = source[source.index("const SPOTS = ["):source.index("const ALIASES")]
    # Six places, and the older spellings for two of them. A study may still say
    # `nose`, so the schema accepts eight names for six spots -- which is what
    # positions() hands back, and so what the tab can actually draw.
    aliases = source[source.index("const ALIASES = {"):]
    from_tab = (set(re.findall(r"part:\s*'(\w+)'", body))
                | set(re.findall(r"(\w+):", aliases[:aliases.index("}")])))

    validate = open(os.path.join(ROOT, "apps/builder/dims_builder/validate.py")).read()
    block = validate[validate.index("FIGURE_PARTS = ("):]
    from_validate = set(re.findall(r'"(\w+)"', block[:block.index(")")]))

    builder = open(os.path.join(
        ROOT, "apps/builder/dims_builder/static/builder.js")).read()
    if "FIGURE_PARTS" in builder:
        line = builder[builder.index("const FIGURE_PARTS"):]
        from_builder = set(re.findall(r'"(\w+)"', line[:line.index("]")]))
        assert from_builder == from_schema, (
            f"builder.js offers {sorted(from_builder)}, schema accepts "
            f"{sorted(from_schema)}")

    assert from_tab == from_schema, (
        f"figure-geometry.js draws {sorted(from_tab)}, schema accepts "
        f"{sorted(from_schema)}")
    assert from_validate == from_schema, (
        f"validate.py knows {sorted(from_validate)}, schema accepts "
        f"{sorted(from_schema)}")


def test_the_payload_version_is_the_same_number_in_both_languages():
    """The analyses write it; the browser refuses anything else. Two files.

    `common/arrays.py` decides what a payload is stamped with and
    `dims-core.js` decides what a dashboard will read. Nothing compared them,
    so a bump on one side alone would not fail here -- it would fail in a
    browser, as every analysis panel in every study going blank behind
    "rebuild the study's assets", which is not the cause and would send the
    reader to rebuild assets that were already correct.

    `dims_case/core.py` holds a third copy and already imports the Python one
    when it can, so it is not the drift this guards.
    """
    from dims_analysis.common.arrays import PAYLOAD_VERSION as from_python

    core = open(os.path.join(ROOT, "packages/dims-core/dims-core.js")).read()
    match = re.search(r"PAYLOAD_VERSION:\s*(\d+)", core)
    assert match, (
        "dims-core.js declares no PAYLOAD_VERSION. The browser has to know "
        "which payload format it can read; without it every stale asset is "
        "drawn as though it were current.")
    from_js = int(match.group(1))

    assert from_js == from_python, (
        f"dims-core.js reads payload version {from_js} and the analyses write "
        f"{from_python}. One of them was bumped without the other, and the "
        f"symptom is every analysis panel blank with a message naming the "
        f"wrong fix.")
