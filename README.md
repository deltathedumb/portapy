# PortaPy

PortaPy is a separately versioned, embeddable Python interpreter derived from the reusable Python-written core of asmpython's `pyinbin` interpreter.

The interpreter implementation remains Python source compiled by asmpython. The public C ABI, generated assembly passes, and small C shims are host/build boundaries only; they do not implement parsing, evaluation, objects, imports, or exception semantics.

Native artifact names:

- `portapy.dll` on Windows
- `libportapy.so` on Linux
- `libportapy.dylib` on macOS when that asmpython target becomes available

## Universal public API

The stable cross-language contract is a C ABI. Any language capable of calling C functions can use the same native library. PortaPy does not provide `import_module`; the host language imports or loads its own modules and then adds their objects to an environment.

The first-class helper exports are:

- `portapy_new()` and `portapy_new_with_config()`
- `portapy_add()` and `portapy_add_all()`
- `portapy_add_value_utf8()` and `portapy_add_callable_utf8()`
- `portapy_execute()` and `portapy_evaluate()`
- `portapy_destroy()`

`portapy_environment` is an alias of the opaque `portapy_runtime` handle, so a host may freely move between the helper layer and the complete low-level runtime, value, global, callback, container, traceback, and error APIs.

See [`docs/FFI.md`](docs/FFI.md) for C and direct C# P/Invoke examples.

## High-level Python API

The native binary interface is environment-oriented and available through a Python facade:

```python
import math

from portapy import import_binary

portapy = import_binary("portapy.dll")
environment = portapy.new()
environment.add(math)
environment.set("requested_value", 41.9)
environment.set("coordinates", (10, 20, (30, 40)))
environment.set("settings", {"scale": 2, "nested": {"value": 21}})
environment.set("samples", [18, [1, 2], 24])
environment.execute("""
import math
floor_value = math.floor(requested_value)
answer = floor_value + 1
first_coordinate = coordinates[0]
scaled = settings["nested"]["value"] * settings["scale"]
first_sample = samples[0]
""")

snapshot = environment.snapshot()
answer = snapshot.var["answer"]
coordinates = snapshot.var["coordinates"]
settings = snapshot.var["settings"]
samples = snapshot.var["samples"]
```

`add(value)` binds a named function, class, module, or object using its `__name__`, unless an explicit name is supplied. `add_all(module)` flattens eligible public members from a module, object, or mapping. `add_module()`, `add_modules()`, `expose()`, and `add_builtin()` remain compatibility or fine-grained namespace operations.

Executed source may use `import module`, aliases, comma-separated imports, and `from module import member` for module objects already added by the host. Imports perform namespace resolution only; they never load host modules. `from module import *` is intentionally replaced by the explicit host-side `add_all(module)` operation.

The adapter recursively converts Python `None`, booleans, signed 64-bit integers, floats, strings, bytes, tuples, lists, string-key mappings, modules, objects, and callables into native PortaPy values. PortaPy-created functions, closures, classes, and instances remain opaque PortaPy-owned handles rather than being misreported as host objects.

Snapshots capture a shallow, detached set of global bindings. `snapshot.var` is read-only, while `snapshot.restore()` restores those bindings and deletes globals created after the snapshot. Mutations inside referenced host objects are intentionally not deep-rolled back.

Native failures include indexed traceback frames:

```python
from portapy import ExecutionError

try:
    environment.execute("result = missing_name")
except ExecutionError as error:
    print(error.error.traceback_text)
    for frame in environment.traceback_frames:
        print(frame.filename, frame.function, frame.line, frame.source_line)
```

The hosted implementation uses the same environment API:

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

## Standalone runtime

The exported `execute` and `evaluate` paths now use PortaPy's own lexer, parser, portable bytecode frontend, and full virtual machine. The generated native adapter preserves the existing ABI while providing:

- persistent, isolated VM namespaces per runtime
- classes, inheritance, descriptors, methods, properties, closures, and `nonlocal`
- exceptions, context managers, generators, comprehensions, matching, and async/`await`
- host object and host callable proxies using the existing callback ABI
- host-added module resolution for `import` and `from ... import ...`
- recursive public tuple, dictionary, and list marshalling
- source-positioned traceback frames through the existing C ABI

Interpreter semantics remain Python-authored. C and NASM only marshal ABI values, calling conventions, library initialization, and exports.

## Building

Install the pinned asmpython compiler and the native toolchain for the target, then use the stable builder:

```bash
python -m pip install --force-reinstall \
  'git+https://github.com/deltathedumb/asmpython.git@376cf9422c28123673a1dedd7dd66b845f3c5ed1'

python tools/build_native_typed.py \
  --target linux \
  --output dist/libportapy.so \
  --work-dir dist/build-linux
```

On Windows:

```powershell
python tools/build_native_typed.py `
  --target windows `
  --output dist/portapy.dll `
  --work-dir dist/build-windows
```

`build_native_typed.py` prepares the full VM for the pinned compiler and selects the standalone adapter by default. Compiler-focused source probes may pass `--source path/to/entry.py` to bypass the final environment adapter.

## Fine-grained native ABI

The helper API is built on and interoperates with the complete public C ABI:

- `portapy_runtime_create()` and `portapy_runtime_destroy()` for explicit runtime ownership
- `portapy_exec_utf8()` and `portapy_eval_utf8()` for UTF-8 spans and filenames
- scalar, text, bytes, tuple, dictionary, list, callable, and opaque object values
- `portapy_set_global_utf8()`, `portapy_get_global_utf8()`, and `portapy_delete_global_utf8()`
- global enumeration for exact snapshot restoration
- host attribute graphs and synchronous callback dispatch
- indexed traceback frames and UTF-8 traceback field copies
- structured errors and checked retain/release ownership

The complete declarations are in [`include/portapy.h`](include/portapy.h) and [`include/portapy_traceback.h`](include/portapy_traceback.h).

## 3.14 status

The standalone runtime architecture is implemented on the `finish-3.14-runtime` branch. The project remains marked `3.14-dev.1` until the canonical Linux and Windows matrices finish successfully and prove that the final libraries:

- pass hosted and pinned-compiler generated-entry tests
- execute the complete external C conformance matrix
- contain no CPython runtime dependency
- expose only the approved ABI symbols
- contain no Linux text relocations
- ship matching metadata, headers, examples, and SHA-256 checksums

See [`docs/NATIVE-STATUS.md`](docs/NATIVE-STATUS.md) and [`RELEASE_STATUS.json`](RELEASE_STATUS.json) for the exact gate state.

## Relationship to pyinbin

`pyinbin` remains tailored to asmpython's native/static import pipeline and packaged-source fallback. PortaPy forks the reusable interpreter core and exposes it as a separately versioned embeddable product.
