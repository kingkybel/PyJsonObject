from fundamentals import is_empty_string, matches_any
from pyjsonobject.exceptions import JsonIndexKeyError, JsonStringKeyError, JsonPathFormatError, JsonPartialKeyError

class JsonKey:
    pass


class JsonIndexKey(JsonKey):
    def __init__(self, index: (str | int)):
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

    def __str__(self):
        if self.is_start:
            return "[^]"
        elif self.is_end:
            return "[$]"
        return f"[{self.index}]"


class JsonStringKey(JsonKey):
    def __init__(self, key: str):
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

    def __str__(self):
        return self.key


class JsonKeyPath:
    def __init__(self, key_path: (str | list) = None):
        self.list_of_keys = list()
        if isinstance(key_path, str):
            key_path = key_path.split("/")
        if len(key_path) == 0:
            raise JsonPathFormatError(path_string="<EMPTY-PATH!!>")
        for i in range(0, len(key_path)):
            partial = key_path[i]
            if not isinstance(partial, (str | int)):
                raise JsonPathFormatError(path_string="/".join(key_path),
                                          extra_info="All elements in key-path list must be of type string or int, "
                                                     f"but type({partial}) is {type(partial)}")
            try:
                if isinstance(partial, str) and partial.startswith("[") and partial.endswith("]"):
                    partial = partial[1:len(partial) - 1]
                    self.list_of_keys.append(JsonIndexKey(partial))
                else:
                    self.list_of_keys.append(JsonStringKey(str(partial)))
            except JsonPartialKeyError as e:
                raise JsonPathFormatError(path_string="/".join(key_path), extra_info=e.message)

    def __str__(self):
        return "/".join([str(key) for key in self.list_of_keys])

    def key_list(self):
        return self.list_of_keys
