#!/usr/bin/env python3
import json
import os
import sys
import tempfile
import types
import unittest


# Provide lightweight stand-ins for external runtime deps used by the package.
flashlogger = types.ModuleType("flashlogger")
flashlogger.log_command = lambda *args, **kwargs: None
sys.modules.setdefault("flashlogger", flashlogger)

fundamentals = types.ModuleType("fundamentals")


def _squeeze_chars(source: str, squeeze_set: str, replace_with: str):
    out = source
    for ch in squeeze_set:
        out = out.replace(ch, replace_with)
    while replace_with * 2 in out:
        out = out.replace(replace_with * 2, replace_with)
    return out.strip() if replace_with == " " else out


def _is_empty_string(value):
    return value is None or (isinstance(value, str) and value.strip() == "")


def _matches_any(search_string: str, patterns: list[str]):
    import re
    return any(re.match(pattern, search_string) for pattern in patterns)


fundamentals.squeeze_chars = _squeeze_chars
fundamentals.is_empty_string = _is_empty_string
fundamentals.matches_any = _matches_any
sys.modules.setdefault("fundamentals", fundamentals)

pyprocess = types.ModuleType("pyprocess")


def _find(paths, file_type_filter="f", name_patterns=r".*\.json"):
    import re
    import pathlib
    pattern = re.compile(name_patterns)
    if isinstance(paths, (str, os.PathLike)):
        paths = [paths]
    out = []
    for p in paths:
        path = pathlib.Path(p)
        if path.is_file() and pattern.match(path.name):
            out.append(str(path))
        elif path.is_dir():
            for sub in path.rglob("*"):
                if sub.is_file() and pattern.match(sub.name):
                    out.append(str(sub))
    return out


pyprocess.find = _find
sys.modules.setdefault("pyprocess", pyprocess)

from pyjsonobject import JsonObject
from pyjsonobject.exceptions import (
    JsonError,
    JsonGeneralError,
    JsonIndexError,
    JsonIndexKeyError,
    JsonKeyError,
    JsonPartialKeyError,
    JsonPathFormatError,
    JsonStringKeyError,
    JsonValueMismatch,
)
from pyjsonobject.json_key_path import JsonIndexKey, JsonKeyPath, JsonStringKey


class TestJsonKeyParts(unittest.TestCase):
    def test_index_key_valid_and_invalid(self):
        with self.assertRaises(JsonIndexKeyError):
            JsonIndexKey("")
        with self.assertRaises(JsonIndexKeyError):
            JsonIndexKey("abc")
        with self.assertRaises(JsonIndexKeyError):
            JsonIndexKey(-1)

        self.assertEqual(str(JsonIndexKey("^")), "[^]")
        self.assertEqual(str(JsonIndexKey("$")), "[$]")
        self.assertEqual(str(JsonIndexKey(7)), "[7]")

    def test_string_key_valid_and_invalid(self):
        invalid = ["", " key", "key ", "a/b", "a[b", "a]b", 'a"b', "k\n"]
        for value in invalid:
            with self.assertRaises(JsonStringKeyError):
                JsonStringKey(value)
        self.assertEqual(str(JsonStringKey("alpha")), "alpha")

    def test_key_path_valid_and_invalid(self):
        with self.assertRaises(JsonPathFormatError):
            JsonKeyPath("")
        with self.assertRaises(JsonPathFormatError):
            JsonKeyPath([])
        with self.assertRaises(TypeError):
            JsonKeyPath(["ok", object()])
        with self.assertRaises(JsonPathFormatError):
            JsonKeyPath("a//b")
        with self.assertRaises(JsonPathFormatError):
            JsonKeyPath(["[]"])

        kp = JsonKeyPath("user/[0]/name")
        self.assertEqual(str(kp), "user/[0]/name")
        self.assertEqual(len(kp.key_list()), 3)


class TestJsonObjectCore(unittest.TestCase):
    def test_constructors_and_to_str(self):
        self.assertEqual(str(JsonObject(json_str="")), "{}")
        self.assertEqual(str(JsonObject(json_str="[]")), "[]")
        self.assertIn("\n", JsonObject(json_obj={"a": 1}).to_str(indent=2))

    def test_from_object_converts_sets_tuples_and_custom(self):
        class Weird:
            def __str__(self):
                return "weird"

        obj = JsonObject(json_obj={"s": {1, 2}, "t": ("a", "b"), "w": Weird()})
        got_s = obj.get("s")
        self.assertIsInstance(got_s, list)
        self.assertEqual(sorted(got_s), [1, 2])
        self.assertEqual(obj.get("t"), ["a", "b"])
        self.assertEqual(obj.get("w"), "weird")

    def test_file_io_and_assert_json_files_valid(self):
        with tempfile.TemporaryDirectory() as td:
            good = os.path.join(td, "good.json")
            bad = os.path.join(td, "bad.json")
            out = os.path.join(td, "out.json")
            with open(good, "w", encoding="utf-8") as f:
                json.dump({"k": [1, 2]}, f)
            with open(bad, "w", encoding="utf-8") as f:
                f.write("{ broken")

            jo = JsonObject(filename=good)
            self.assertEqual(jo.get("k/[1]"), 2)
            jo.to_file(out, indent=2)
            self.assertTrue(os.path.isfile(out))

            with self.assertRaises(json.JSONDecodeError):
                JsonObject.assert_json_files_valid(td)

            with self.assertRaises(JsonGeneralError):
                JsonObject(filename=os.path.join(td, "missing.json"))

    def test_get_success_and_default_paths(self):
        obj = JsonObject(json_obj={"user": {"name": "Ada"}, "arr": [3, 4]})
        self.assertEqual(obj.get("user/name"), "Ada")
        self.assertEqual(obj.get("arr/[0]"), 3)
        self.assertEqual(obj.get("arr/[^]"), 3)
        self.assertEqual(obj.get("arr/[$]"), 4)
        self.assertEqual(obj.get("user/city", default="unknown"), "unknown")

        with self.assertRaises(JsonKeyError):
            obj.get("arr/key")
        with self.assertRaises(JsonGeneralError):
            obj.get("arr/[9]")

    def test_set_force_and_non_force(self):
        obj = JsonObject(json_str="{}")
        obj.set("a/[0]/name", "node", force=True)
        self.assertEqual(obj.get("a/[0]/name"), "node")

        with self.assertRaises(JsonValueMismatch):
            obj.set("a/[0]/name", "node2", force=False)

        obj.set("a/[0]/name", "node2", force=True)
        self.assertEqual(obj.get("a/[0]/name"), "node2")

        with self.assertRaises(JsonValueMismatch):
            obj.set("a/[0]/name", 9, force=False)

        with self.assertRaises(JsonGeneralError):
            obj.set("a/[0]/name", None, force=False)

        with self.assertRaises(JsonGeneralError):
            obj.set("a/[0]/name", {1, 2}, force=False)

    def test_set_special_array_tokens(self):
        obj = JsonObject(json_str="[]")
        obj.set("[$]", "last", force=True)
        obj.set("[^]", "first", force=True)
        self.assertEqual(obj.get("[^]"), "first")
        self.assertEqual(obj.get("[$]"), "last")

    def test_key_exists(self):
        obj = JsonObject(json_obj={"a": {"b": 1}})
        self.assertTrue(obj.key_exists("a/b"))
        self.assertFalse(obj.key_exists("a/c"))


class TestExceptions(unittest.TestCase):
    def test_exception_hierarchy_and_messages(self):
        self.assertTrue(issubclass(JsonGeneralError, JsonError))
        self.assertTrue(issubclass(JsonPartialKeyError, JsonError))

        e = JsonGeneralError("boom")
        self.assertIn("boom", str(e))

        e = JsonValueMismatch("a", 1)
        self.assertIn("Cannot overwrite value of different type", str(e))


if __name__ == "__main__":
    unittest.main()
