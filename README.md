# PortaPy

PortaPy is a separately versioned, embeddable interpreter project derived from the reusable Python-written core of asmpython's `pyinbin` interpreter.

The interpreter implementation is required to remain Python source compiled by asmpython. The public C ABI and generated assembly passes are only host/build boundaries; they do not implement parsing, evaluation, objects, imports, or exception semantics.

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

`portapy_environment` is an alias of the opaque `portapy_runtime` handle, so a host may freely drop from the helper layer into the complete low-level runtime, value, global, callback, container, and error APIs.

See [`docs/FFI.md`](docs/FFI.md) for C and direct C# P/Invoke examples.

## High-level Python API

The native binary interface is environment-oriented and available through a Python facade:

```python
import math

from portapy import import_binary
from somnia import env

portapy = import_binary("portapy.dll")
environment = portapy.new()
environment.add(math)       # available as math.floor(...)
environment.add_all(env)    # public members become direct globals
environment.set("requested_value", 41.9)
environment.set("coordinates", (10, 20, (30, 40)))
environment.set("settings", {"scale": 2, "nested": {"value": 21}})
environment.set("samples", [18, [1, 2], 24])
environment.execute("""
http_provider = game.provider.HttpProvider
floor_value = math.floor(requested_value)
answer = floor_value + 1
first_coordinate = coordinates[0]
scaled = settings["nested"]["value"] * settings["scale"]
first_sample = samples[0]
""")

snapshot = environment.snapshot()
http_provider = snapshot.var["http_provider"]
answer = snapshot.var["answer"]
coordinates = snapshot.var["coordinates"]
settings = snapshot.var["settings"]
samples = snapshot.var["samples"]
```

`add(value)` binds a named function, class, module, or object using its `__name__`, unless an explicit name is supplied. `add_all(module)` flattens all eligible public members from a module, object, or mapping. `add_module()`, `add_modules()`, `expose()`, and `add_builtin()` remain compatibility or fine-grained namespace operations.

The adapter automatically converts Python `None`, booleans, signed 64-bit integers, floats, strings, bytes, tuples, lists, string-key mappings, modules, objects, and callables into native PortaPy values. Tuples, lists, and mappings are converted recursively and remain ordinary PortaPy values across globals, snapshots, and host callback arguments/results. Native mapping keys are currently restricted to non-empty ASCII strings. Object members become host attribute graphs, while callables are routed through the synchronous callback ABI.

Snapshots capture a shallow, detached set of global bindings. `snapshot.var` is a read-only mapping, while `snapshot.restore()` restores those bindings to the originating environment and deletes globals created after the snapshot. Mutations inside referenced host objects are intentionally not deep-rolled back.

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

The helper API is built on, and interoperates with, the complete public C ABI:

- `portapy_runtime_create()` and `portapy_runtime_destroy()` for explicit runtime ownership.
- `portapy_exec_utf8()` and `portapy_eval_utf8()` for explicit UTF-8 spans and filenames.
- `portapy_value_from_host_object()` for opaque objects with stable host IDs.
- `portapy_value_from_host_callable()` for callables with stable callable IDs.
- `portapy_value_from_tuple()` for immutable tuples built from borrowed item handles.
- `portapy_tuple_get_size()` and `portapy_tuple_get_item()` for retained tuple extraction.
- `portapy_value_from_dict()` and `portapy_dict_set_utf8()` for owned string-key dictionaries.
- `portapy_dict_get_size()`, `portapy_dict_key_copy_utf8()`, and `portapy_dict_get_item_utf8()` for enumeration and retained lookup.
- `portapy_value_from_list()` for mutable lists built from borrowed item handles.
- `portapy_list_get_size()`, `portapy_list_get_item()`, `portapy_list_set_item()`, and `portapy_list_append()` for retained extraction and mutation.
- `portapy_set_global_utf8()` and `portapy_delete_global_utf8()` for namespace management.
- `portapy_global_count()` and `portapy_global_name_copy_utf8()` for exact snapshot enumeration.
- `portapy_host_set_attr_utf8()` for host-owned attribute graphs.
- `portapy_host_set_call_handler()` for a raw synchronous dispatcher per runtime.
- helper callbacks and raw callback dispatchers coexisting in one environment.
- checked conversions, retained callback results, structured errors, and retain/release ownership.

## 3.14 Developer Preview 1

`3.14-dev.1` is the first genuine native-library preview. Its runtime state, value ownership, text storage, source parsing, UTF-8 validation, structured error state, control flow, functions, host-object graph, host-call parser, and namespace management are Python-authored and compiled by asmpython. Linux and Windows artifacts are exercised from independent C hosts and from the high-level Python binary facade before publication.

Implemented native ABI and source surface:

- isolated runtime and environment handles
- first-class cross-language `new`, `add`, `add_all`, `execute`, `evaluate`, and `destroy` exports
- `None`, normalized `bool`, signed 64-bit integer, bit-exact binary64, string, bytes, tuple, dictionary, list, callable, and opaque object handles
- stable 64-bit host object and callable IDs
- retained native global injection, enumeration, replacement, and deletion
- host attribute graph registration, replacement, lookup, and dotted traversal
- synchronous qualified, flattened, and nested host calls
- helper and fine-grained raw callbacks in the same environment
- borrowed callback arguments, owned callback results, and structured callback failures
- `import_binary()` / `load_native()` Python binary facades
- hosted and native `new()`, `add()`, `add_all()`, `add_modules()`, `expose()`, `set()`, `get()`, `remove()`, `execute()`, `evaluate()`, and snapshots
- automatic Python scalar, tuple, list, string-key mapping, module, object, and callable adaptation
- exact native snapshot restoration with post-snapshot global cleanup
- checked value-kind/conversion and buffer-copy operations
- public tuple construction, size, and retained item extraction
- public dictionary construction, replacement, key enumeration, and retained lookup
- public list construction, size, retained item extraction, replacement, and append
- recursive tuple, dictionary, and list release through normal value ownership
- recursive tuple/list/mapping globals, snapshots, and host callback round-trips
- per-runtime structured error status, type, message, line, and column
- retain/release and runtime-owned teardown
- precedence-aware integer arithmetic, powers, shifts, and bitwise expressions
- string/bytes concatenation and repetition
- native `None`, boolean, quoted string, bytes, tuple, dictionary, and list literals
- empty, single-item, multi-item, and nested tuples
- positive, negative, and chained tuple indexing
- tuple-aware `len()`, truthiness, and recursive structural equality
- owned string-key dictionaries with `len()`, truthiness, equality, and indexing
- mutable lists with positive/negative indexing, `len()`, truthiness, and recursive structural equality
- recursive dictionary and list child ownership
- UTF-8 source literals across hosted Unicode and native byte-oriented source boundaries
- tuple, dictionary, and list values passed through native functions and control flow
- container literals inside native function calls
- equality, ordering, `is`, and `is not` comparisons
- `not`, `and`, and `or` with Python-style truthiness and operand returns
- typed global assignment, lookup, aliasing, augmented assignment, and `eval`
- newline/semicolon statement blocks, bare expressions, and `pass`
- indented `if`/`else`, nested blocks, and `while`
- `break` and `continue`
- positional `def` functions, zero/multi-argument calls, nested calls, and `return`
- recursive `if`/`else` and `while` blocks inside native functions
- nested `break`, `continue`, and early `return` propagation inside functions
- trailing scalar defaults captured once when each `def` executes
- transactional capture replacement on successful function redefinition
- positional/keyword, mixed, reordered, and nested default calls
- `/` positional-only and bare `*` keyword-only parameter markers
- named `*args` parameters packed into real immutable tuple values
- named `**kwargs` parameters packed into owned string-key dictionaries
- mixed fixed, positional-only, keyword-only, positional-variadic, and keyword-variadic binding
- positional-only names captured by `**kwargs`, matching Python behavior
- local call-frame save/restore without leaking variadic bindings
- missing, duplicate, unexpected, parameter-kind, and positional-after-keyword argument errors
- callable value handles and cross-`exec` function persistence
- quote-aware comments and separators
- exact public export allowlists
- Linux position-independent linking with no text relocations
- independent Linux and Windows C and Python conformance hosts
- reproducible native builds pinned to a verified asmpython compiler commit

This preview is **not** the final standalone Python 3.14 interpreter release. Remaining gates include closures, classes, completing the frontend/bytecode VM transition, broader object syntax, full traceback-frame retrieval, and native module imports inside executed PortaPy source. Host module loading is intentionally outside the PortaPy embedding API.

## Relationship to pyinbin

`pyinbin` remains tailored to asmpython's native/static import pipeline and packaged-source fallback. PortaPy forks the reusable interpreter core and exposes it as a separately versioned embeddable product.

See `docs/DESIGN.md`, `docs/FFI.md`, `RELEASE_STATUS.json`, and `include/portapy.h`.
