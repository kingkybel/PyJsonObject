from __future__ import annotations

from collections.abc import Iterable
from typing import TypeAlias

JSONScalar: TypeAlias = bool | int | float | str
JSONValue: TypeAlias = JSONScalar | list | dict
JSONObjectContainer: TypeAlias = list | dict

# mirrors fundamentals.Strings semantics used throughout project
Strings: TypeAlias = str | Iterable[str] | None
