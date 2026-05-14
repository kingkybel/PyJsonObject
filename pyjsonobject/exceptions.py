from fundamentals import force_strings
from pyjsonobject.types import Strings, JSONValue, JSONObjectContainer


class JsonError(Exception):
    """Base exception for all errors raised by pyjsonobject."""

    def __init__(self, message: str = None) -> None:
        """
        Initialize the exception with an optional message.
        :param message: Human-readable error message.
        """
        if message is None:
            message = ""
        self.message = message
        super().__init__(message)


class JsonGeneralError(JsonError):
    """Generic exception for non-specific JsonObject errors."""

    def __init__(self, message: str = None) -> None:
        """
        Initialize the exception with an optional message.
        :param message: Human-readable error message.
        """
        if message is None:
            message = ""
        self.message = message
        super().__init__(message)


class JsonPartialKeyError(JsonError):
    """Base exception for invalid individual key/path fragments."""

    pass


class JsonIndexKeyError(JsonPartialKeyError):
    """Raised when an index key is syntactically or semantically invalid."""

    def __init__(self, index: (str | int)) -> None:
        """
        Create an index validation error for the given index token.
        :param index: Invalid index token.
        """
        self.message = f"Index '{index}' (type={type(index)}) is not a valid index. " \
                       "Only 0, positive ints or '^'/'$' are allowed"
        super().__init__(self.message)


class JsonStringKeyError(JsonPartialKeyError):
    """Raised when a string key contains unsupported characters or spacing."""

    def __init__(self, key: str) -> None:
        """
        Create a string-key validation error for the given key.
        :param key: Invalid key token.
        """
        self.message = f"Json-key '{key}' (type={type(key)}) is not a valid index. " \
                       "Must not have whitespace at front or back, or contain '[', ']', '/' or '\"'"
        super().__init__(self.message)


class JsonPathFormatError(JsonError, ValueError):
    """Raised when a full JSON key-path string cannot be parsed."""

    def __init__(self, path_string: str = None, extra_info: str = None) -> None:
        """
        Create a key-path format error with optional diagnostic details.
        :param path_string: The original path string that failed validation.
        :param extra_info: Optional extra diagnostics for the path error.
        """
        if path_string is None:
            path_string = ""
        if extra_info is None:
            extra_info = ""
        else:
            extra_info = f". ({extra_info})"
        self.message = f"Json path-string '{path_string}' does not conform to " \
                       f"(\\[ <int> | '^' | '$' \\] | <string-id>)+{extra_info}"
        super().__init__(self.message)


class JsonKeyError(JsonError, KeyError):
    """Raised for object-key access failures in nested JSON structures."""

    def __init__(self,
                 key: int,
                 keys: Strings,
                 json_obj: (JSONObjectContainer | None) = None) -> None:
        """
        Create a descriptive key access error for path navigation.
        :param key: Index of the failing key in the path.
        :param keys: Full key path components.
        :param json_obj: Current JSON sub-object where resolution failed.
        """
        normalized_keys: list[str] = [k for k in force_strings(keys)]
        key_value = normalized_keys[key] if 0 <= int(key) < len(normalized_keys) else key
        if json_obj is None:
            self.message = f"Key '{key_value}' at key-number {key} cannot be resolved in empty json object"
        elif isinstance(json_obj, list):
            self.message = f"Key '{key_value}' at key-number {key} requires object type(dict) " \
                           f"but found '{type(json_obj)}'"
        else:
            self.message = f"Key '{key_value}' at key-number {key} cannot be found in '{json_obj}'"
        super().__init__(self.message)


class JsonIndexError(JsonError, KeyError):
    """Raised for array-index access failures in nested JSON structures."""

    def __init__(self,
                 key_number: int,
                 keys: Strings,
                 json_obj: (JSONObjectContainer | None) = None) -> None:
        """
        Create a descriptive index access error for path navigation.
        :param key_number: Index of the failing key in the path.
        :param keys: Full key path components.
        :param json_obj: Current JSON sub-object where resolution failed.
        """
        normalized_keys: list[str] = [k for k in force_strings(keys)]
        key_value = normalized_keys[key_number] if 0 <= int(key_number) < len(normalized_keys) else key_number
        if json_obj is None:
            self.message = f"Index '{key_value}' at key-number {key_number} cannot be resolved in empty json object"
        elif not isinstance(json_obj, list):
            self.message = f"Index '{key_value}' at key-number {key_number} requires object type(list) " \
                           f"but found '{type(json_obj)}'"
        else:
            upper = len(json_obj) - 1
            self.message = f"Index '{key_value}' at key-number {key_number} is out of bounds [0..{upper}]"
        super().__init__(self.message)


class JsonValueMismatch(JsonError, ValueError):
    """Raised when overwriting a value with a different type without force."""

    def __init__(self,
                 orig_value: JSONValue,
                 new_value: JSONValue) -> None:
        """
        Create a value-type mismatch error.
        :param orig_value: Existing value in JSON structure.
        :param new_value: Replacement value requested by caller.
        """
        self.message = f"Cannot overwrite value of different type if not forced. " \
                       f"Original value '{orig_value}' type({type(orig_value)}), New value '{new_value}' " \
                       f"type({type(new_value)})"
        super().__init__(self.message)
