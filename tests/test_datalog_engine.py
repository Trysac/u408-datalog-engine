"""Behavior tests for the public API of datalog_engine."""

from __future__ import annotations

import pytest

import datalog_engine


def test_normalize_trims_and_lowercases() -> None:
    assert datalog_engine.normalize("  Hello World ") == "hello world"


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_normalize_rejects_blank_input(value: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        datalog_engine.normalize(value)


def test_version_is_semver() -> None:
    parts = datalog_engine.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
