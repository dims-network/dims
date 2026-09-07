"""Reading config.json without turning an author's typo into a traceback."""
import pytest

from dims_analysis.common import config as cfg


def test_a_gate_key_is_matched_whatever_its_case():
    """The three shipped keys use three conventions, so nobody remembers them.

    `build_assets.py` already matched loosely, so a study writing
    `include_crqa` was reported as enabled by one component and skipped in
    silence by the other.
    """
    assert cfg.enabled({"include_crqa": [["a", "b"]]}, "include_cRQA")
    assert cfg.enabled({"INCLUDE_RQA": ["a"]}, "include_RQA")
    assert not cfg.enabled({"include_crqa": []}, "include_cRQA")
    assert not cfg.enabled({}, "include_cRQA")


def test_two_spellings_of_one_key_is_an_error():
    """Resolving it quietly would pick the one nobody meant.

    A scaffold ships `"include_cRQA": []`; someone adds `"include_crqa"` with
    real pairs below it. Preferring the exact match resolves that to "off".
    """
    with pytest.raises(cfg.ConfigError) as exc:
        cfg.enabled({"include_cRQA": [], "include_crqa": [["a", "b"]]}, "include_cRQA")
    assert "spelled more than one way" in str(exc.value)


def test_true_where_a_list_belongs_says_what_to_write():
    """`"include_RQA": true` is what the name suggests, and it used to raise
    `TypeError: 'bool' object is not iterable` from six frames inside a step."""
    with pytest.raises(cfg.ConfigError) as exc:
        cfg.as_list({"include_RQA": True}, "include_RQA", "data types")
    message = str(exc.value)
    assert "include_RQA" in message and '["bodysync"]' in message


def test_a_pairwise_key_is_shown_a_pairwise_example():
    with pytest.raises(cfg.ConfigError) as exc:
        cfg.as_list({"include_cRQA": True}, "include_cRQA", "pairs of data types")
    assert '[["bodysync", "neuralsync"]]' in str(exc.value)


def test_a_bare_string_is_caught_too():
    with pytest.raises(cfg.ConfigError) as exc:
        cfg.as_list({"include_RQA": "bodysync"}, "include_RQA", "data types")
    assert '["bodysync"]' in str(exc.value)


def test_absent_and_false_are_simply_empty():
    assert cfg.as_list({}, "include_RQA", "data types") == []
    assert cfg.as_list({"include_RQA": False}, "include_RQA", "data types") == []


def test_a_real_list_passes_through():
    assert cfg.as_list({"include_RQA": ["a", "b"]}, "include_RQA", "data types") == ["a", "b"]
