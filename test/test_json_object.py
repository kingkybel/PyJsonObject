#!/usr/bin/env python3
from __future__ import annotations

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
fundamentals.Strings = str


def _force_strings(values):
    if values is None:
        return []
    if isinstance(values, str):
        return [values]
    try:
        return [str(v) for v in values]
    except TypeError:
        return [str(values)]


fundamentals.force_strings = _force_strings
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
pyprocess.PathType = str
pyprocess.PathIterable = list
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

    def test_explicit_exception_message_variants(self):
        e = JsonError()
        self.assertEqual(str(e), "")

        e = JsonGeneralError()
        self.assertEqual(str(e), "")

        e = JsonPathFormatError("a//b", "bad token")
        self.assertIn("a//b", str(e))
        self.assertIn("bad token", str(e))

        e = JsonKeyError(0, ["a"], json_obj={})
        self.assertIn("cannot be found", str(e))

        e = JsonIndexError(0, ["[0]"], json_obj=[])
        self.assertIn("out of bounds", str(e))


class TestJsonObjectAdditionalCoverage(unittest.TestCase):
    def test_to_str_and_get_json(self):
        obj = JsonObject(json_obj={"a": [1, 2], "b": {"x": True}})
        self.assertIsInstance(obj.to_str(indent=4), str)
        self.assertEqual(obj.get_json()["a"][1], 2)

    def test_from_string_empty_and_from_object_scalar(self):
        obj = JsonObject(json_str="   \n\t")
        self.assertEqual(str(obj), "{}")

        obj.from_object((1, 2, 3))
        self.assertEqual(obj.get_json(), [1, 2, 3])

    def test_convert_to_json_object_for_custom_with_dict(self):
        class C:
            def __init__(self):
                self.a = 1
                self.b = {"c": (2, 3)}

        converted = JsonObject.convert_to_json_object(C())
        self.assertEqual(converted, {"a": 1, "b": {"c": [2, 3]}})

    def test_convert_to_json_object_for_fallback_string(self):
        class S:
            __slots__ = ()

            def __str__(self):
                return "slot-object"

        converted = JsonObject.convert_to_json_object(S())
        self.assertEqual(converted, "slot-object")

    def test_to_file_and_set_dryrun(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "out.json")
            obj = JsonObject(json_obj={"a": 1})
            obj.to_file(out, dryrun=True)
            self.assertFalse(os.path.exists(out))

            obj.set("a", 2, force=False, dryrun=True)
            self.assertEqual(obj.get("a"), 1)

    def test_assert_json_files_valid_success(self):
        with tempfile.TemporaryDirectory() as td:
            p1 = os.path.join(td, "a.json")
            p2 = os.path.join(td, "b.json")
            with open(p1, "w", encoding="utf-8") as f:
                json.dump({"ok": 1}, f)
            with open(p2, "w", encoding="utf-8") as f:
                json.dump([1, 2, 3], f)
            code, failed = JsonObject.assert_json_files_valid(td)
            self.assertEqual(code, 0)
            self.assertEqual(failed, [])

    def test_get_raises_for_empty_keys_and_incompatible(self):
        obj = JsonObject(json_obj={"a": 1, "b": [1]})
        with self.assertRaises(JsonKeyError):
            obj.get("")
        with self.assertRaises(JsonKeyError):
            obj.get("[0]")
        self.assertEqual(obj.get("[0]", default="d"), "d")

    def test_get_with_key_list_input(self):
        obj = JsonObject(json_obj={"root": [{"name": "n"}]})
        key_list = JsonKeyPath("root/[0]/name").key_list()
        self.assertEqual(obj.get(key_list), "n")

    def test_get_with_generator_keys(self):
        obj = JsonObject(json_obj={"root": [{"name": "n"}]})
        key_gen = (k for k in ["root", "[0]", "name"])
        self.assertEqual(obj.get(key_gen), "n")

    def test_set_reconfigures_root_type_when_forced(self):
        obj = JsonObject(json_str="[]")
        obj.set("a/b", 7, force=True)
        self.assertEqual(obj.get("a/b"), 7)

        obj2 = JsonObject(json_str="{}")
        obj2.set("[0]/x", 1, force=True)
        self.assertEqual(obj2.get("[0]/x"), 1)

    def test_set_not_forced_error_paths(self):
        obj = JsonObject(json_obj={"a": {"b": 1}, "arr": [1, 2]})

        with self.assertRaises(JsonGeneralError):
            obj.set("missing/key", 1, force=False)

        with self.assertRaises(JsonValueMismatch):
            obj.set("arr/[5]", 3, force=False)

        with self.assertRaises(JsonValueMismatch):
            obj.set("arr/key", 3, force=False)

    def test_json_key_path_iterable_and_errors(self):
        kp = JsonKeyPath(("a", "[0]", "b"))
        self.assertEqual(str(kp), "a/[0]/b")

        with self.assertRaises(JsonPathFormatError):
            JsonKeyPath(123)  # wrong type

        with self.assertRaises(TypeError):
            JsonKeyPath(["a", None])

    def test_json_string_key_more_invalid_cases(self):
        for val in ["\tb", "b\t", 'b"c', "a/b", "x[y", "x]y"]:
            with self.assertRaises(JsonStringKeyError):
                JsonStringKey(val)

    def test_json_index_key_numeric_string_and_non_numeric(self):
        self.assertEqual(str(JsonIndexKey("10")), "[10]")
        with self.assertRaises(JsonIndexKeyError):
            JsonIndexKey("1a")

    def test_to_dict_returns_deep_copy_and_copy_is_independent(self):
        obj = JsonObject(json_obj={"a": {"b": [1, 2]}})
        as_dict = obj.to_dict()
        as_dict["a"]["b"][0] = 99
        self.assertEqual(obj.get("a/b/[0]"), 1)

        clone = obj.copy()
        clone.set("a/b/[0]", 7, force=True)
        self.assertEqual(clone.get("a/b/[0]"), 7)
        self.assertEqual(obj.get("a/b/[0]"), 1)

    def test_get_many_success_and_defaults(self):
        obj = JsonObject(json_obj={"u": {"name": "Ada"}, "arr": [10, 20]})
        got = obj.get_many(["u/name", "arr/[1]", "missing/path"], default="N/A")
        self.assertEqual(got["u/name"], "Ada")
        self.assertEqual(got["arr/[1]"], 20)
        self.assertEqual(got["missing/path"], "N/A")

    def test_get_many_raises_when_no_default(self):
        obj = JsonObject(json_obj={"u": {"name": "Ada"}})
        with self.assertRaises(JsonGeneralError):
            obj.get_many(["u/name", "u/[0]"])

    def test_delete_dict_and_list_paths(self):
        obj = JsonObject(json_obj={"a": {"x": 1, "y": 2}, "arr": ["first", "last"]})
        self.assertTrue(obj.delete("a/x"))
        self.assertFalse(obj.key_exists("a/x"))

        self.assertTrue(obj.delete("arr/[^]"))
        self.assertEqual(obj.get("arr/[0]"), "last")

        self.assertTrue(obj.delete("arr/[$]"))
        self.assertEqual(obj.get("arr", default=[]), [])

    def test_delete_silent_and_dryrun(self):
        obj = JsonObject(json_obj={"a": {"b": 1}})
        self.assertFalse(obj.delete("a/c", silent=True))
        self.assertTrue(obj.delete("a/b", dryrun=True))
        self.assertTrue(obj.key_exists("a/b"))

    def test_delete_raises_on_invalid_path(self):
        obj = JsonObject(json_obj={"a": 1})
        with self.assertRaises(JsonGeneralError):
            obj.delete("a/b")

    def test_delete_with_generator_keys(self):
        obj = JsonObject(json_obj={"a": {"b": 1}})
        key_gen = (k for k in ["a", "b"])
        self.assertTrue(obj.delete(key_gen))
        self.assertFalse(obj.key_exists("a/b"))

    def test_update_shallow_existing_dict(self):
        obj = JsonObject(json_obj={"cfg": {"a": 1, "nested": {"x": 1}}})
        obj.update("cfg", {"b": 2, "nested": {"y": 2}}, force=False, deep=False)
        self.assertEqual(obj.get("cfg/a"), 1)
        self.assertEqual(obj.get("cfg/b"), 2)
        self.assertEqual(obj.get("cfg/nested"), {"y": 2})

    def test_update_deep_merge(self):
        obj = JsonObject(json_obj={"cfg": {"nested": {"x": 1}, "keep": True}})
        obj.update("cfg", {"nested": {"y": 2}}, deep=True)
        self.assertEqual(obj.get("cfg/nested/x"), 1)
        self.assertEqual(obj.get("cfg/nested/y"), 2)
        self.assertTrue(obj.get("cfg/keep"))

    def test_update_force_creates_missing_path(self):
        obj = JsonObject(json_obj={})
        obj.update("settings/profile", {"theme": "dark"}, force=True)
        self.assertEqual(obj.get("settings/profile/theme"), "dark")

    def test_update_force_replaces_non_dict_target(self):
        obj = JsonObject(json_obj={"cfg": "text"})
        obj.update("cfg", {"k": 1}, force=True)
        self.assertEqual(obj.get("cfg/k"), 1)

    def test_update_errors_and_dryrun(self):
        obj = JsonObject(json_obj={"cfg": {"a": 1}, "x": 3})

        with self.assertRaises(JsonGeneralError):
            obj.update("cfg", [1, 2, 3])

        with self.assertRaises(JsonValueMismatch):
            obj.update("x", {"a": 1}, force=False)

        obj.update("cfg", {"b": 2}, dryrun=True)
        self.assertFalse(obj.key_exists("cfg/b"))


if __name__ == "__main__":
    unittest.main()
