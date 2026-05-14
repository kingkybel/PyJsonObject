import json
import os
import os.path
from os import PathLike
from pathlib import Path

from flashlogger import log_command
from fundamentals import squeeze_chars, is_empty_string
from pyprocess import find, PathType, PathIterable

from pyjsonobject.exceptions import JsonGeneralError, JsonError, JsonKeyError, JsonIndexError, JsonValueMismatch
from pyjsonobject.json_key_path import JsonKeyPath, JsonIndexKey, JsonStringKey
from pyjsonobject.types import JSONValue, JSONObjectContainer, Strings

class JsonObject:
    """Wrapper around dict/list JSON data with path-based get/set helpers."""

    NOT_FOUND = None

    @classmethod
    def __normalize_keys(cls, keys: Strings) -> tuple[list, str]:
        """Normalize incoming key container to parsed key list + display path string."""
        if keys is None or (isinstance(keys, str) and keys == ""):
            raise JsonKeyError(key=0, keys=keys, json_obj=None)

        # Already parsed key objects from JsonKeyPath(...).key_list()
        if isinstance(keys, list) and all(isinstance(k, (JsonStringKey, JsonIndexKey)) for k in keys):
            return keys, "/".join(str(k) for k in keys)

        if isinstance(keys, str):
            path = JsonKeyPath(keys)
            return path.key_list(), str(path)

        key_materialized = [k for k in keys]
        path = JsonKeyPath(key_materialized)
        return path.key_list(), str(path)

    def __init__(self,
                 json_str: str  = None,
                 filename: PathType = None,
                 json_obj: JSONObjectContainer = None) -> None:
        """
        Initialize from JSON string, file, Python object, or empty object.
        :param json_str: JSON content as string.
        :param filename: File path to load JSON content from.
        :param json_obj: Pre-existing Python dict/list to initialize from.
        """
        self._json = None
        if json_str is not None:
            if squeeze_chars(source=json_str, squeeze_set="\n\t\r ", replace_with=" ") == "":
                json_str = "{}"
            self.from_string(json_str)
        elif filename and not is_empty_string(filename):
            self.from_file(filename)
        elif json_obj is not None:
            self.from_object(json_obj)
        else:
            self.from_string("{}")

    def __str__(self) -> str:
        """Return compact JSON string representation of the current object."""
        return json.dumps(self._json)

    def to_str(self, indent: int = 2):
        """
        Return pretty-printed JSON string representation.
        :param indent: Indentation width for formatting.
        :return: JSON string.
        """
        return json.dumps(self._json, indent=indent)

    def from_string(self, json_str: str) -> None:
        """
        Load JSON content from a string into this object.
        :param json_str: JSON content to parse.
        :raises json.JSONDecodeError: If the string cannot be parsed as JSON.
        """
        if is_empty_string(json_str):
            json_str = "{}"
        self._json = json.loads(json_str)

    @classmethod
    def convert_to_json_object(cls, obj) -> JSONValue:
        """
        Recursively convert Python objects into JSON-serializable structures.
        :param obj: Source object.
        :return: JSON-serializable value.
        """
        if isinstance(obj, (bool, int, float, str)):
            return obj
        if isinstance(obj, set):
            # If it's a set, convert it to a list after doing the same recursively.
            return [JsonObject.convert_to_json_object(item) for item in obj]
        if isinstance(obj, dict):
            # If it's a dictionary, recursively process its values
            return {key: JsonObject.convert_to_json_object(value) for key, value in obj.items()}
        if isinstance(obj, list):
            # If it's a list, recursively process its elements
            return [JsonObject.convert_to_json_object(item) for item in obj]
        if isinstance(obj, tuple):
            # If it's a tuple, recursively process its elements and convert to list
            return [JsonObject.convert_to_json_object(item) for item in obj]
        if hasattr(obj, "__dict__"):
            # If it's a custom object, recursively process only instance attributes.
            converted = {
                key: JsonObject.convert_to_json_object(value)
                for key, value in vars(obj).items()
            }
            return converted if len(converted) > 0 else str(obj)
        return str(obj)

    def from_object(self, obj: object) -> None:
        """
        Load content from an arbitrary Python object.
        :param obj: Source object to convert and load.
        """
        obj = JsonObject.convert_to_json_object(obj)
        self.from_string(json.dumps(obj))

    def from_file(self, filename: PathType) -> None:
        """
        Load JSON content from a file.
        :param filename: Path to JSON file.
        :raises JsonGeneralError: If file does not exist.
        :raises json.JSONDecodeError: If file content is invalid JSON.
        """
        if not os.path.isfile(filename):
            raise JsonGeneralError(f"Cannot load json from file '{str(Path(filename))}': file does not exist")
        file = open(filename)
        try:
            self._json = json.load(file)
        except json.JSONDecodeError:
            file.close()
            raise
        file.close()

    def to_file(self, filename: (str | PathLike), indent: int = 4, dryrun: bool = False) -> None:
        """
        Write the current JSON content to a file.
        :param filename: Output file path.
        :param indent: Indentation width for JSON formatting.
        :param dryrun: If True, log only and skip writing.
        """
        log_command(f"JsonObject.to_file({str(Path(filename))})", dryrun=dryrun)
        if not dryrun:
            with open(filename, 'w') as file:
                json.dump(self._json, file, indent=indent)

    def get_json(self) -> JSONObjectContainer:
        """
        Return the underlying JSON object (dict or list).
        :return: Backing JSON container.
        """
        return self._json

    def to_dict(self) -> JSONObjectContainer:
        """
        Return a deep-copied Python representation of the backing JSON object.
        :return: Deep copy of the backing dict/list container.
        """
        return json.loads(json.dumps(self._json))

    def copy(self) -> "JsonObject":
        """
        Return an independent copy of this JsonObject.
        :return: New JsonObject instance with copied content.
        """
        return JsonObject(json_obj=self.to_dict())

    @classmethod
    def assert_json_files_valid(cls, paths: PathIterable) -> tuple[int, PathIterable]:
        """
        Validate all JSON files found under the provided paths.
        :param paths: Search roots containing JSON files.
        :return: Tuple of (status_code, failed_files).
        """
        json_files = find(paths=paths, file_type_filter="f", name_patterns=r".*\.json")
        failed_files = []
        reval = 0
        for json_file in json_files:
            try:
                JsonObject(filename=json_file)
            except JsonError:
                failed_files.append(json_file)
                reval = -1
        return reval, failed_files

    @classmethod
    def __try_get_key(cls, json_obj, key: (int | str)) -> object:
        """
        Safely fetch a key/index from dict/list, returning NOT_FOUND if absent.
        :param json_obj: Candidate dict/list object.
        :param key: Key/index to resolve.
        :return: Found value or JsonObject.NOT_FOUND.
        """
        if not isinstance(json_obj, (dict | list)):
            return JsonObject.NOT_FOUND
        if isinstance(json_obj, list) and not isinstance(key, int):
            return JsonObject.NOT_FOUND
        try:
            return json_obj[key]
        except KeyError:
            return JsonObject.NOT_FOUND

    def key_exists(self, keys: Strings) -> bool:
        """
        Return True if the given key path exists, otherwise False.
        :param keys: Path expression string or key list.
        :return: True when key path resolves, False otherwise.
        """
        not_exist_str = "KEY-DOES-NOT-EXIST"
        if self.get(keys, default=not_exist_str) == not_exist_str:
            return False
        return True

    def get_many(self, paths: list[Strings], default=None) -> dict[str, object]:
        """
        Resolve multiple key paths and return values in a single mapping.
        :param paths: List of path strings or path key-lists.
        :param default: Optional fallback when a path is missing/incompatible.
        :return: Mapping path-string -> resolved value/default.
        """
        result = {}
        for path in paths:
            path_string = str(path) if isinstance(path, str) else str(JsonKeyPath(path))
            result[path_string] = self.get(path, default=default)
        return result

    def update(self,
               keys: Strings,
               mapping: dict,
               force: bool = False,
               deep: bool = False,
               dryrun: bool = False) -> None:
        """
        Update a dictionary value at the provided path using another mapping.
        :param keys: Path to the target dictionary.
        :param mapping: Mapping containing keys/values to merge in.
        :param force: If True, create/reshape the target path when missing/incompatible.
        :param deep: If True, recursively merge nested dictionaries.
        :param dryrun: If True, log only and skip mutation.
        """
        if not isinstance(mapping, dict):
            raise JsonGeneralError(f"update() expects dict mapping, got {type(mapping)}")

        if not force:
            target = self.get(keys)
            if not isinstance(target, dict):
                raise JsonValueMismatch(orig_value=target, new_value=mapping)
        else:
            if not self.key_exists(keys):
                self.set(keys, {}, force=True, dryrun=dryrun)
            target = self.get(keys)
            if not isinstance(target, dict):
                self.set(keys, {}, force=True, dryrun=dryrun)
                target = self.get(keys)

        def _deep_merge(dst: dict, src: dict):
            for k, v in src.items():
                if isinstance(v, dict) and isinstance(dst.get(k), dict):
                    _deep_merge(dst[k], v)
                else:
                    dst[k] = JsonObject.convert_to_json_object(v)

        log_command(
            f"JsonObject.update(keys={str(JsonKeyPath(keys))}, force={force}, deep={deep}, dryrun={dryrun})",
            dryrun=dryrun
        )
        if dryrun:
            return
        if deep:
            _deep_merge(target, mapping)
        else:
            target.update({k: JsonObject.convert_to_json_object(v) for k, v in mapping.items()})

    def get(self, keys: Strings, default=None) -> object:
        """
        Return the value at the given key path or default/error when missing.
        :param keys: Path expression string or key list.
        :param default: Optional fallback value for missing paths.
        :return: Resolved value or default.
        :raises JsonKeyError: If a dict key cannot be resolved and no default is given.
        :raises JsonIndexError: If an index cannot be resolved and no default is given.
        :raises JsonGeneralError: For unexpected navigation/key access errors.
        """
        try:
            keys, _ = JsonObject.__normalize_keys(keys)
        except JsonKeyError:
            raise JsonKeyError(key=0, keys=keys, json_obj=self._json)

        if isinstance(keys[0], JsonIndexKey) and not isinstance(self._json, list):
            if default is not None:
                return default
            raise JsonKeyError(key=0, keys=[str(k) for k in keys], json_obj=self._json)

        iterator = self._json
        for i in range(0, len(keys)):
            try:
                is_last = (i == len(keys) - 1)
                cur_key = keys[i]
                if isinstance(cur_key, JsonIndexKey):
                    if not isinstance(iterator, list):
                        if default is not None:
                            return default
                        raise JsonIndexError(key_number=i, keys=keys, json_obj=iterator)
                    if cur_key.is_start:
                        index = 0
                    elif cur_key.is_end:
                        index = len(iterator) - 1
                    else:
                        index = cur_key.index
                    if is_last:
                        if int(index) > len(iterator) - 1:
                            if default is not None:
                                return default
                            raise JsonIndexError(key_number=i, keys=keys, json_obj=iterator)
                        return iterator[int(index)]
                    iterator = iterator[int(index)]
                elif isinstance(cur_key, JsonStringKey):
                    if isinstance(iterator, list):
                        if default is not None:
                            return default
                        raise JsonKeyError(key=i, keys=keys, json_obj=iterator)
                    if is_last:
                        try:
                            return iterator[cur_key.key]
                        except KeyError:
                            if default is not None:
                                return default
                            raise JsonKeyError(key=i, keys=keys, json_obj=iterator)
                    iterator = iterator[cur_key.key]
            except JsonKeyError:
                raise
            except KeyError as k:
                if default is not None:
                    return default
                error_msg = f"Cannot get key number '{i}' in json {iterator}. {k}"
                raise JsonGeneralError(message=error_msg)
        return iterator

    def set(self,
            keys: (str | list[str]),
            value: JSONValue,
            force: bool = False,
            dryrun: bool = False) -> None:
        """
        Set a value at the given key path with optional force behavior.
        :param keys: Path expression string or key list.
        :param value: Value to store.
        :param force: If True, create/reshape intermediate path nodes.
        :param dryrun: If True, log only and skip mutation.
        :raises JsonGeneralError: If value is None or has unsupported type.
        :raises JsonValueMismatch: If non-force update changes value type.
        :raises JsonKeyError: If non-force update hits key type mismatch.
        :raises JsonIndexError: If non-force update hits index type mismatch.
        """
        if value is None:
            raise JsonGeneralError("Cannot set value that is None")
        if not isinstance(value, (bool, int, float, str, dict, list)):
            raise JsonGeneralError(f"Unsupported json-value type {type(value)}")
        path = JsonKeyPath(keys)
        keys = path.key_list()

        log_command(f"JsonObject.set(keys={str(path)}, value={value}, force={force} dryrun={dryrun}")
        if not dryrun:
            if force:
                self.__set_forced(keys, value)
            else:
                self.__set_not_forced(keys, value)

    def delete(self, keys: Strings, silent: bool = False, dryrun: bool = False) -> bool:
        """
        Delete the value at the given key path.
        :param keys: Path expression string or key list.
        :param silent: If True, return False when path does not exist/incompatible.
        :param dryrun: If True, log only and skip mutation.
        :return: True when an item was deleted, False when silent and not deleted.
        """
        try:
            parsed_keys, path_string = JsonObject.__normalize_keys(keys)
        except JsonKeyError:
            if silent:
                return False
            raise JsonKeyError(key=0, keys=keys, json_obj=self._json)

        parent = self._json
        for i in range(0, len(parsed_keys) - 1):
            cur_key = parsed_keys[i]
            try:
                if isinstance(cur_key, JsonIndexKey):
                    if not isinstance(parent, list):
                        if silent:
                            return False
                        raise JsonIndexError(key_number=i, keys=parsed_keys, json_obj=parent)
                    if cur_key.is_start:
                        index = 0
                    elif cur_key.is_end:
                        index = len(parent) - 1
                    else:
                        index = cur_key.index
                    parent = parent[int(index)]
                else:
                    if not isinstance(parent, dict):
                        if silent:
                            return False
                        raise JsonKeyError(key=i, keys=parsed_keys, json_obj=parent)
                    parent = parent[cur_key.key]
            except (KeyError, IndexError):
                if silent:
                    return False
                raise JsonGeneralError(f"Cannot delete key-path at segment {i}: '{cur_key}'")

        last_key = parsed_keys[-1]
        log_command(f"JsonObject.delete(keys={path_string}, silent={silent}, dryrun={dryrun})", dryrun=dryrun)
        try:
            if isinstance(last_key, JsonIndexKey):
                if not isinstance(parent, list):
                    if silent:
                        return False
                    raise JsonIndexError(key_number=len(parsed_keys) - 1, keys=parsed_keys, json_obj=parent)
                if last_key.is_start:
                    index = 0
                elif last_key.is_end:
                    index = len(parent) - 1
                else:
                    index = last_key.index
                if not dryrun:
                    del parent[int(index)]
                return True

            if not isinstance(parent, dict):
                if silent:
                    return False
                raise JsonKeyError(key=len(parsed_keys) - 1, keys=parsed_keys, json_obj=parent)
            if not dryrun:
                del parent[last_key.key]
            return True
        except (KeyError, IndexError):
            if silent:
                return False
            raise JsonGeneralError(f"Cannot delete key '{last_key}'")

    def __set_forced(self, keys: list[str], value: JSONValue) -> JSONObjectContainer:
        """
        Set a value while creating/replacing intermediate structures as needed.
        :param keys: Parsed path keys.
        :param value: Value to store.
        :return: Updated backing JSON object.
        """
        if isinstance(keys[0], JsonIndexKey) and not isinstance(self._json, list):
            self._json = list()
        elif isinstance(keys[0], JsonStringKey) and not isinstance(self._json, dict):
            self._json = dict()

        prev_iterator = None
        prev_key = None
        iterator = self._json
        for i in range(0, len(keys)):
            is_first = (i == 0)
            is_last = (i == len(keys) - 1)
            cur_key = keys[i]
            next_key = None
            next_key_is_list = False
            if not is_last:
                next_key = keys[i + 1]
                next_key_is_list = isinstance(next_key, JsonIndexKey)
            if not is_first:
                prev_key = keys[i - 1]
            if next_key_is_list:
                blank_object_type = list
            else:
                blank_object_type = dict
                if is_last and isinstance(value, (str, bool, int, float)):
                    blank_object_type = type(value)

            if isinstance(cur_key, JsonIndexKey):
                if not isinstance(iterator, list):
                    iterator = list()
                if cur_key.is_start:
                    iterator.insert(0, blank_object_type())
                    index = 0
                elif cur_key.is_end:
                    iterator.append(blank_object_type())
                    index = len(iterator) - 1
                else:
                    index = cur_key.index
                    for _ in range(len(iterator), int(index) + 1):
                        iterator.append(blank_object_type())

                if is_last:
                    iterator[int(index)] = value
                elif not isinstance(iterator[int(index)], blank_object_type):
                    iterator[int(index)] = blank_object_type()
                prev_iterator = iterator
                iterator = iterator[int(index)]
            else:
                if not isinstance(iterator, dict):
                    iterator = dict()
                if is_last:
                    iterator[str(cur_key)] = value
                elif JsonObject.__try_get_key(iterator, cur_key) == next_key:
                    tmp = blank_object_type()
                    tmp[str(cur_key)] = blank_object_type()
                    iterator = tmp
                    prev_iterator[str(prev_key)] = iterator
                elif not isinstance(iterator, blank_object_type):
                    iterator[str(cur_key)] = blank_object_type()
                else:
                    try:
                        iterator[str(cur_key)]
                    except KeyError:
                        iterator[str(cur_key)] = blank_object_type()

                prev_iterator = iterator
                iterator = iterator[str(cur_key)]
        return self._json

    def __set_not_forced(self, keys: list[str], value: JSONValue) -> JSONObjectContainer:
        """
        Set a value only when path and types already match existing structure.
        :param keys: Parsed path keys.
        :param value: Value to store.
        :return: Updated backing JSON object.
        :raises JsonIndexError: If list/index path expectations are violated.
        :raises JsonKeyError: If dict/key path expectations are violated.
        :raises JsonValueMismatch: If existing leaf type differs from new value type.
        :raises JsonGeneralError: For unexpected path overwrite/navigation failures.
        """
        if isinstance(keys[0], JsonIndexKey) and not isinstance(self._json, list):
            raise JsonIndexError(key_number=0, keys=keys, json_obj=self._json)
        elif isinstance(keys[0], JsonStringKey) and not isinstance(self._json, dict):
            raise JsonKeyError(key=0, keys=keys, json_obj=self._json)
        iterator = self._json
        cur_key = keys[0]
        for i in range(0, len(keys)):
            try:
                is_last = (i == len(keys) - 1)
                cur_key = keys[i]
                if isinstance(cur_key, JsonIndexKey):
                    if not isinstance(iterator, list):
                        raise JsonIndexError(key_number=i, keys=keys, json_obj=self._json)
                    if cur_key.is_start:
                        index = 0
                    elif cur_key.is_end:
                        index = len(iterator) - 1
                    else:
                        index = cur_key.index

                    if is_last:
                        if type(iterator[int(index)]) == type(value):
                            iterator[int(index)] = value
                        else:
                            raise JsonValueMismatch(orig_value=iterator[int(index)], new_value=value)
                    iterator = iterator[int(index)]
                else:
                    if isinstance(iterator, list):
                        raise JsonKeyError(key=cur_key, keys=keys, json_obj=self._json)
                    if is_last:
                        if type(iterator[cur_key.key]) == type(value):
                            iterator[cur_key.key] = value
                    else:
                        raise JsonValueMismatch(orig_value=iterator[cur_key.key], new_value=value)
                    iterator = iterator[cur_key.key]
            except JsonKeyError:
                raise
            except JsonIndexError:
                raise
            except KeyError:
                error_msg = f"Cannot create/overwrite key number '{i}' '{cur_key}' - not leaf"
                raise JsonGeneralError(message=error_msg)
        return self._json
