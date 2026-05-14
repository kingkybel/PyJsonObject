from abc import ABC, abstractmethod
from collections.abc import Iterable

from fundamentals import is_empty_string, matches_any
from pyjsonobject.exceptions import JsonIndexKeyError, JsonStringKeyError, JsonPathFormatError, JsonPartialKeyError
from pyjsonobject.types import Strings


class JsonKey(ABC):
    """Marker base class for parsed JSON path key components."""

    @abstractmethod
    def __str__(self) -> str:
        """
        Return the canonical string representation of the key fragment.
        :return: Path-fragment string.
        """
        raise NotImplementedError()


class JsonIndexKey(JsonKey):
    """Represents an array index component in a JSON key path."""

    def __init__(self, index: (str | int)) -> None:
        """
        Parse and validate an index token (int, '^', or '$').
        :param index: The index token to parse.
        :raises JsonIndexKeyError: If the token is invalid or negative.
        """
        self.is_start = False
        self.is_end = False
        self.index = None
        if isinstance(index, str):
            if index == "^":
                self.is_start = True
            elif index == "$":
                self.is_end = True
            else:
                try:
                    self.index = int(index)
                except ValueError:
                    raise JsonIndexKeyError(index)
        else:
            self.index = index

        if self.index is not None and self.index < 0:
            raise JsonIndexKeyError(self.index)

    def __str__(self) -> str:
        """
        Return the canonical string representation of the index token.
        :return: Canonical token string such as "[^]", "[$]" or "[3]".
        """
        if self.is_start:
            return "[^]"
        elif self.is_end:
            return "[$]"
        return f"[{self.index}]"


class JsonStringKey(JsonKey):
    """Represents an object-key component in a JSON key path."""

    def __init__(self, key: str) -> None:
        """
        Validate and store a string key token.
        :param key: The key token to validate.
        :raises JsonStringKeyError: If the key is empty or contains invalid characters.
        """
        if is_empty_string(key):
            raise JsonStringKeyError(key)
        if matches_any(search_string=key, patterns=[".* $", ".*\t$",
                                                    "^ .*", "^\t.*",
                                                    ".*\n.*",
                                                    ".*/.*",
                                                    r".*\[.*",
                                                    r".*\].*",
                                                    r".*\".*"]):
            raise JsonStringKeyError(key=key)
        self.key = key

    def __str__(self) -> str:
        """
        Return the raw key string.
        :return: The raw object-key token.
        """
        return self.key


class JsonKeyPath:
    """Parses and stores a normalized list of JSON path key components."""

    def __init__(self, key_path: Strings = None) -> None:
        """
        Create a key path from a slash-delimited string or key list.
        :param key_path: A slash-delimited path string or list of key fragments.
        :raises JsonPathFormatError: If the path is empty or contains invalid fragments.
        """

        if not key_path:
            raise JsonPathFormatError(path_string="<EMPTY-PATH!!>")
        self._list_of_keys: list = []
        if isinstance(key_path, str):
            key_path = key_path.split("/")
        elif isinstance(key_path, Iterable):
            key_path = [k for k in key_path]
        else:
            raise JsonPathFormatError(path_string=f"Incorrect type. Cannot create KeyPath from {key_path}")
        if len(key_path) == 0:
            raise JsonPathFormatError(path_string="<EMPTY-PATH!!>")
        for partial in key_path:
            if not isinstance(partial, (str | int)):
                raise JsonPathFormatError(path_string="/".join(key_path),
                                          extra_info="All elements in key-path list must be of type string or int, "
                                                     f"but type({partial}) is {type(partial)}")
            try:
                if isinstance(partial, str) and partial.startswith("[") and partial.endswith("]"):
                    partial = partial[1:len(partial) - 1]
                    self._list_of_keys.append(JsonIndexKey(partial))
                else:
                    self._list_of_keys.append(JsonStringKey(str(partial)))
            except JsonPartialKeyError as e:
                raise JsonPathFormatError(path_string="/".join(key_path), extra_info=e.message)

    def __str__(self) -> str:
        """
        Render the normalized key path as a slash-delimited string.
        :return: Normalized path string.
        """
        return "/".join([str(key) for key in self._list_of_keys])

    def key_list(self) -> list:
        """
        Return the parsed key components as a list.
        :return: List of JsonStringKey/JsonIndexKey components.
        """
        return self._list_of_keys

