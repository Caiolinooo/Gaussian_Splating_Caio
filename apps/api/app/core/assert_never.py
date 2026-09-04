"""Exhaustive-switch helper for closed unions/enums."""

from typing import NoReturn


def assert_never(value: object) -> NoReturn:
    raise AssertionError(f"unhandled value: {value!r}")
