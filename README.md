# PortaPy

PortaPy is a separately versioned, embeddable interpreter project derived from the reusable Python-written core of asmpython's `pyinbin` interpreter.

The interpreter implementation remains Python source compiled by asmpython. The public C ABI and generated assembly passes are host/build boundaries; they do not implement parsing, evaluation, objects, imports, or exception semantics.

Native artifact names:

- `portapy.dll` on Windows
- `libportapy.so` on Linux
- `libportapy.dylib` on macOS when that asmpython target becomes available

## Universal public API

The stable cross-language contract is a C ABI. Any language capable of calling C functions can use the same native library. PortaPy does not provide `import_module`; the host language loads its own modules and adds their objects to an environment.

The first-class helper exports are:

- `portapy_new()` and `portapy_new_with_config()`
- `portapy_add()` and `portapy_add_all()`
- `portapy_add_value_utf8()` and `portapy_add_callable_utf8()`
- `portapy_execute()` and `portapy_evaluate()`
- `portapy_destroy()`

`portapy_environment` aliases the opaque `portapy_runtime` handle, so hosts can freely move between the helper layer and the complete low-level runtime, value, global, callback, container, snapshot, and error APIs.

See [`docs/FFI.md`](docs/FFI.md) for C and direct C# P/Invoke examples.

## High-level Python API

```python
import math

from portapy import import_binary

portapy = import_binary("portapy.dll")
environment = portapy.new()
environment.add(math)
environment.add_all({"seed": 40})
environment.set("values", [40, 2])
environment.execute("""
def total(items):
    result = 0
    for item in items:
        result += item
    return result

class Box:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

box = Box(value=total(items=values))
answer = box.get()
""")
assert environment.get("answer") == 42
```

`add(value)` binds a named function, class, module, or object using its `__name__`, unless an explicit name is supplied. `add_all(value)` flattens eligible public members from a module, object, or mapping. `add_module()`, `add_modules()`, `expose()`, and `add_builtin()` remain compatibility or fine-grained namespace operations.

The adapter converts Python `None`, booleans, signed 64-bit integers, floats, strings, bytes, tuples, lists, string-key mappings, modules, objects, and callables into native PortaPy values. Containers are converted recursively and remain ordinary PortaPy values across globals, snapshots, and callback arguments/results. Native mapping keys are restricted to non-empty ASCII strings.

Snapshots capture a shallow detached set of global bindings. `snapshot.var` is read-only, while `snapshot.restore()` restores those bindings and deletes globals created after the snapshot.

The hosted implementation uses the same API:

```python
import portapy


def plus_one(value):
    return value + 1


environment = portapy.new()
environment.add(plus_one)
environment.add_all({"seed": 41})
environment.execute("answer = plus_one(seed)")
assert environment.snapshot().var["answer"] == 42
```

## Fine-grained native ABI

The helper API interoperates with the complete public C ABI:

- explicit runtime/environment ownership
- UTF-8 source execution and expression evaluation
- scalar, string, bytes, tuple, list, dictionary, callable, and opaque object values
- retained container extraction and mutable list/dictionary operations
- global injection, enumeration, replacement, and deletion
- host attribute graphs and synchronous callback dispatch
- snapshots and exact post-snapshot global cleanup
- checked conversions, buffer copies, retain/release ownership, and structured errors

See [`include/portapy.h`](include/portapy.h) for the authoritative function surface.

## PortaPy 3.14.0

`3.14.0` is the first source-ready stable release. The canonical Linux and Windows artifacts contain PortaPy's standalone parser, full frontend, bytecode VM, and public embedding ABI.

The native runtime includes:

- ordinary source execution and expression evaluation
- functions, defaults, positional-only/keyword-only parameters, `*args`, and `**kwargs`
- nested functions and captured closures
- classes, constructors, instance attributes, and bound methods
- `if`, `while`, `for`, `break`, `continue`, and early return
- tuples, mutable lists, and string-key dictionaries with recursive ownership
- configured import statements inside executed PortaPy source
- exceptions, structured errors, and synthetic traceback frame chains
- host objects, flattened module exposure, and synchronous callbacks
- language-neutral C ABI plus Python and direct C# facades
- Linux and Windows external C/Python conformance suites
- reproducible native builds pinned to a verified asmpython compiler commit

The release artifacts are `portapy.dll`, `libportapy.so`, `portapy.h`, metadata manifests, FFI examples, and SHA-256 checksums.

## Relationship to pyinbin

`pyinbin` remains tailored to asmpython's native/static import pipeline and packaged-source fallback. PortaPy forks the reusable interpreter core and exposes it as a separately versioned embeddable product.

See `docs/DESIGN.md`, `docs/FFI.md`, `RELEASE_STATUS.json`, and `include/portapy.h`.
