import json
import os
import os.path
from os import PathLike

from flashlogger import log_command
from fundamentals import squeeze_chars, is_empty_string
from pyprocess import find

from pyjsonobject.exceptions import JsonGeneralError, JsonError, JsonKeyError, JsonIndexError, JsonValueMismatch
from pyjsonobject.json_key_path import JsonKeyPath, JsonIndexKey, JsonStringKey

class JsonObject:
    NOT_FOUND = None

    def __init__(self,
                 json_str: (str | list) = None,
                 filename: (str | PathLike) = None,
                 json_obj: (list | dict) = None):
        self.json_ = None
        if json_str is not None:
            if squeeze_chars(source=json_str, squeeze_set="\n\t\r ", replace_with=" ") == "":
                json_str = "{}"
            self.from_string(json_str)
        elif not is_empty_string(filename):
            self.from_file(filename)
        elif json_obj is not None:
            self.from_object(json_obj)
        else:
            self.from_string("{}")

    def __str__(self):
        return json.dumps(self.json_)

    def to_str(self, indent: int = 2):
        return json.dumps(self.json_, indent=indent)

    def from_string(self, json_str: str):
        if is_empty_string(json_str):
            json_str = "{}"
        self.json_ = json.loads(json_str)

    @classmethod
    def convert_sets_to_vectors(cls, obj):
        if isinstance(obj, set):
            # If it's a set, convert it to a list after doing the same recursively.
            return [JsonObject.convert_sets_to_vectors(item) for item in obj]
        elif isinstance(obj, dict):
            # If it's a dictionary, recursively process its values
            return {key: JsonObject.convert_sets_to_vectors(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            # If it's a list, recursively process its elements
            return [JsonObject.convert_sets_to_vectors(item) for item in obj]
        elif isinstance(obj, tuple):
            # If it's a tuple, recursively process its elements and convert to list
            return [JsonObject.convert_sets_to_vectors(item) for item in obj]
        # elif isinstance(obj, object):
        #     # If it's a custom object, recursively process its attributes
        #     for attr_name in dir(obj):
        #         attr_value = getattr(obj, attr_name)
        #         setattr(obj, attr_name, JsonObject.convert_sets_to_vectors(attr_value))
        if not isinstance(obj, (bool, int, float, str)):
            return str(obj)
        return obj

    def from_object(self, obj: object):
        obj = JsonObject.convert_sets_to_vectors(obj)
        self.from_string(json.dumps(obj))

    def from_file(self, filename: (str | PathLike)):
        if not os.path.isfile(filename):
            raise JsonGeneralError(f"Cannot load json from file '{filename}': file does not exist")
        file = open(filename)
        try:
            self.json_ = json.load(file)
        except json.JSONDecodeError:
            file.close()
            raise
        file.close()

    def to_file(self, filename: (str | PathLike), indent: int = 4, dryrun: bool = False):
        log_command(f"JsonObject.to_file({filename})", dryrun=dryrun)
        if not dryrun:
            with open(filename, 'w') as file:
                json.dump(self.json_, file, indent=indent)

    @classmethod
    def assert_json_files_valid(cls, paths: (str | PathLike | list[str | PathLike])):
        json_files = find(paths=paths, file_type_filter="f", name_patterns=r".*\.json")
        failed_files = list()
        reval = 0
        for json_file in json_files:
            try:
                JsonObject(filename=json_file)
            except JsonError:
                failed_files.append(json_file)
                reval = -1
        return reval, failed_files

    @classmethod
    def __try_get_key(cls, json_obj, key: (int | str)):
        if not isinstance(json_obj, (dict | list)):
            return JsonObject.NOT_FOUND
        if isinstance(json_obj, list) and not isinstance(key, int):
            return JsonObject.NOT_FOUND
        try:
            return json_obj[key]
        except KeyError:
            return JsonObject.NOT_FOUND

    def key_exists(self, keys: (str | list[str])):
        not_exist_str = "KEY-DOES-NOT-EXIST"
        if self.get(keys, default=not_exist_str) == not_exist_str:
            return False
        return True

    def get(self, keys: (str | list[str]), default=None):
        if isinstance(keys, str):
            keys = JsonKeyPath(keys).key_list()
        if isinstance(keys[0], JsonIndexKey) and not isinstance(self.json_, list):
            if default is not None:
                return default
            raise JsonKeyError(key=0, keys=keys, json_obj=self.json_)
        iterator = self.json_
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
            value: (bool | int | float | str | list | dict),
            force: bool = False,
            dryrun: bool = False):
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

    def __set_forced(self, keys: list[str], value: (bool | int | float | str | list | dict)):
        if isinstance(keys[0], JsonIndexKey) and not isinstance(self.json_, list):
            self.json_ = list()
        elif isinstance(keys[0], JsonStringKey) and not isinstance(self.json_, dict):
            self.json_ = dict()

        prev_iterator = None
        prev_key = None
        iterator = self.json_
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
                    for i in range(len(iterator), int(index) + 1):
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
        return self.json_

    def __set_not_forced(self, keys: list[str], value: (bool | int | float | str | list | dict)):
        if isinstance(keys[0], JsonIndexKey) and not isinstance(self.json_, list):
            raise JsonIndexError(key_number=0, keys=keys, json_obj=self.json_)
        elif isinstance(keys[0], JsonStringKey) and not isinstance(self.json_, dict):
            raise JsonKeyError(key=0, keys=keys, json_obj=self.json_)
        iterator = self.json_
        cur_key = keys[0]
        for i in range(0, len(keys)):
            try:
                is_last = (i == len(keys) - 1)
                cur_key = keys[i]
                if isinstance(cur_key, JsonIndexKey):
                    if not isinstance(iterator, list):
                        raise JsonIndexError(key_number=i, keys=keys, json_obj=self.json_)
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
                        raise JsonKeyError(key=cur_key, keys=keys, json_obj=self.json_)
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
        return self.json_
