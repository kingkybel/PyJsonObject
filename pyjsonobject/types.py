from collections.abc import Iterable
from typing import Optional, Union

JSONScalar = Union[bool, int, float, str]
JSONValue = Union[JSONScalar, list, dict]
JSONObjectContainer = Union[list, dict]

# mirrors fundamentals.Strings semantics used throughout project
Strings = Optional[Union[str, Iterable[str]]]
