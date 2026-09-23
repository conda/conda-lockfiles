from __future__ import annotations

import warnings

from conda_lockfiles.aliases import (
    flipped_alias_binding_warning,
    pending_alias_binding_warning,
)


def test_pending_alias_binding_warning_repeats_when_filter_allows() -> None:
    alias = pending_alias_binding_warning(
        "short-format",
        current="format-v1",
        future="format-v2",
        flip_release="the next release",
    )
    mapping = {alias: "resolved"}

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        assert mapping["short-format"] == "resolved"
        assert mapping["short-format"] == "resolved"

    assert [warning.category for warning in captured] == [
        PendingDeprecationWarning,
        PendingDeprecationWarning,
    ]
    assert "short-format" in str(captured[0].message)
    assert "format-v1" in str(captured[0].message)
    assert "format-v2" in str(captured[0].message)


def test_flipped_alias_binding_warning_is_one_shot() -> None:
    alias = flipped_alias_binding_warning(
        "short-format",
        current="format-v2",
        previous="format-v1",
    )
    mapping = {alias: "resolved"}

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        assert mapping["short-format"] == "resolved"
        assert mapping["short-format"] == "resolved"

    assert len(captured) == 1
    assert captured[0].category is DeprecationWarning
    assert "short-format" in str(captured[0].message)
    assert "format-v2" in str(captured[0].message)
    assert "format-v1" in str(captured[0].message)
