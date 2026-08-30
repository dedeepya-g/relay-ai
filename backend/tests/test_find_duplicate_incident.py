"""Unit tests for the deterministic shortlisting logic in deduplication.

_floor_distance is the one place a past regression actually shipped: a
basement label compared unequal to every numbered floor instead of sitting
one floor below ground level. These cases pin that behavior down.
"""

from __future__ import annotations

from tools.find_duplicate_incident import _floor_distance


def test_same_floor_is_zero_distance() -> None:
    assert _floor_distance("3", "3") == 0


def test_adjacent_numbered_floors_are_one_apart() -> None:
    assert _floor_distance("3", "2") == 1
    assert _floor_distance("2", "3") == 1


def test_distant_numbered_floors() -> None:
    assert _floor_distance("1", "5") == 4


def test_basement_is_adjacent_to_ground_floor() -> None:
    """B1 sits directly below floor 1, so the two must be one floor apart.

    This is the case that was wrong once already: treating basement labels
    as incomparable with numbered floors would silently drop the ranking
    boost a leak spreading from floor 1 into the basement depends on.
    """
    assert _floor_distance("B1", "1") == 1
    assert _floor_distance("1", "B1") == 1


def test_basements_stack_below_ground_floor() -> None:
    assert _floor_distance("B1", "B2") == 1
    assert _floor_distance("B2", "1") == 2


def test_unknown_or_missing_labels_return_none() -> None:
    assert _floor_distance(None, "1") is None
    assert _floor_distance("1", None) is None
    assert _floor_distance(None, None) is None
    assert _floor_distance("penthouse", "1") is None


def test_basement_label_is_case_insensitive() -> None:
    assert _floor_distance("b1", "1") == 1
