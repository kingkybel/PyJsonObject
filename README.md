![PyJsonObject banner](./assets/banners/pyjsonobject-banner.svg)

# PyJsonObject

`PyJsonObject` is a Python library for reading and modifying nested JSON values using slash-separated key paths.
It is the Python counterpart of the C++ `JsonObject` library and follows the same core usage model.

## What this repository contains

- Core package:
  - `pyjsonobject/json_object.py`
  - `pyjsonobject/json_key_path.py`
  - `pyjsonobject/exceptions.py`
- Unit tests in `test/`
- Packaging and build metadata:
  - `pyproject.toml`
  - `setup.py`

## Core capabilities

- Access nested JSON values with string paths like `user/profile/name`
- Access array items with index keys like `[0]`, `[1]`
- Use special array symbols:
  - `[^]` first element (or prepend on `set(..., force=True)`)
  - `[$]` last element (or append on `set(..., force=True)`)
- Optional default values for safe reads
- Optional `force=True` writes to create compatible intermediate containers
- File I/O helpers:
  - `from_file(filename)`
  - `to_file(filename, indent)`

## Path syntax

- Segments are separated by `/`
- Object keys are plain strings, for example: `settings/theme`
- Array indices are bracketed, for example: `users/[0]/name`
- Valid index symbols: `[0]`, `[1]`, ..., `[^]`, `[$]`

## Examples

### 1) Basic get/set

```python
from pyjsonobject import JsonObject

obj = JsonObject(json_str='{"user":{"name":"Ada","age":36}}')

obj.set("user/name", "Ada Lovelace")
name = obj.get("user/name")
```

### 2) Defaults and compatibility checks

```python
from pyjsonobject import JsonObject

obj = JsonObject(json_str='{"user":{"name":"Ada"}}')

# Missing key in a compatible object path -> returns default
city = obj.get("user/city", default="unknown")

# Incompatible path still raises an error (object vs array mismatch)
# obj.get("user/[0]", default="fallback")
```

### 3) Array operations with special symbols

```python
from pyjsonobject import JsonObject

arr = JsonObject(json_str='[1,2,3]')

arr.set("[^]", 0, force=True)  # prepend -> [0,1,2,3]
arr.set("[$]", 4, force=True)  # append  -> [0,1,2,3,4]

first = arr.get("[^]")
last = arr.get("[$]")
```

### 4) Force-create intermediate structures

```python
from pyjsonobject import JsonObject

obj = JsonObject(json_str='{}')

# Without force this raises due to missing path/container
obj.set("a/[0]/name", "node-0", force=True)
```

### 5) Using JsonKeyPath directly

```python
from pyjsonobject import JsonObject
from pyjsonobject.json_key_path import JsonKeyPath

obj = JsonObject(json_str='{"items":[{"id":7}]}')
path = JsonKeyPath("items/[0]/id")

value = obj.get(path.key_list())
```

### 6) Load and write files

```python
from pyjsonobject import JsonObject

obj = JsonObject()
obj.from_file("input.json")
obj.set("meta/version", 2, force=True)
obj.to_file("output.json", indent=2)
```

## Install

### From source (editable)

```bash
cd /home/dkybelksties/Repos/Github/PyJsonObject
python3 -m pip install -e .
```

### Build a wheel

```bash
cd /home/dkybelksties/Repos/Github/PyJsonObject
python3 -m pip install build
python3 -m build
```

## Run tests

```bash
cd /home/dkybelksties/Repos/Github/PyJsonObject
python3 -m pytest -q
```
