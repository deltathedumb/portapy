# PortaPy

PortaPy is a separately versioned, embeddable interpreter project derived from the reusable Python-written core of asmpython's `pyinbin` interpreter.

The interpreter implementation is required to remain Python source compiled by asmpython. The public C ABI and generated assembly passes are only host/build boundaries; they do not implement parsing, evaluation, objects, imports, or exception semantics.

Native artifact names:

- `portapy.dll` on Windows
- `libportapy.so` on Linux
- `libportapy.dylib` on macOS when that asmpython target becomes available

## High-level API

The native binary interface is environment-oriented and available through a real Python facade:

```python
import math

from portapy import import_binary
from somnia import env

portapy = import_binary("portapy.dll")
environment = portapy.new()
environment.add_modules(math)
environment.expose(env)
environment.set("requested_value", 41.9)
environment.execute("""
http_provider = game.provider.HttpProvider
floor_value = math.floor(requested_value)
answer = floor_value + 1
""")

snapshot = environment.snapshot()
http_provider = snapshot.var["http_provider"]
answer = snapshot.var["answer"]
```

`add_modules()` preserves qualified access such as `math.floor`. `expose()` is the flattened-namespace operation: it makes public values from a module, object, or mapping available directly. `add_builtin()` remains a compatibility alias, but `expose()` is the preferred name.

The adapter automatically converts Python `None`, booleans, signed 64-bit integers, floats, strings, bytes, modules, objects, mappings, and callables into native PortaPy values. Object members become host attribute graphs, while callables are routed through the synchronous callback ABI.

Snapshots capture a shallow, detached set of global bindings. `snapshot.var` is a read-only mapping, while `snapshot.restore()` restores those bindings to the originating environment and deletes globals created after the snapshot. Mutations inside referenced host objects are intentionally not deep-rolled back.

The hosted implementation uses the same API:

```python
import portapy

environment = portapy.new()
environment.expose({"seed": 41})
environment.execute("answer = seed + 1")
assert environment.snapshot().var["answer"] == 42
```

The native C ABI underneath the facade provides:

- `portapy_value_from_host_object()` for opaque objects with stable host IDs.
- `portapy_value_from_host_callable()` for callables with stable callable IDs.
- `portapy_set_global_utf8()` and `portapy_delete_global_utf8()` for namespace management.
- `portapy_global_count()` and `portapy_global_name_copy_utf8()` for exact snapshot enumeration.
- `portapy_host_set_attr_utf8()` for host-owned attribute graphs.
- dotted traversal such as `game.provider.HttpProvider`.
- `portapy_host_set_call_handler()` for one synchronous dispatcher per runtime.
- borrowed callback arguments and one owned callback result.
- qualified and flattened calls, including nested calls, on Linux and Windows.
- `portapy_value_get_host_id()` for mapping evaluated values back to Python objects.

## 3.14 Developer Preview 1

`3.14-dev.1` is the first genuine native-library preview. Its runtime state, value ownership, text storage, source parsing, UTF-8 validation, structured error state, control flow, functions, host-object graph, host-call parser, and namespace management are Python-authored and compiled by asmpython. Linux and Windows artifacts are exercised from independent C hosts and from the high-level Python binary facade before publication.

Implemented native ABI and source surface:

- isolated runtime handles
- `None`, normalized `bool`, signed 64-bit integer, bit-exact binary64, string, bytes, callable, and opaque object handles
- stable 64-bit host object and callable IDs
- retained native global injection, enumeration, replacement, and deletion
- host attribute graph registration, replacement, lookup, and dotted traversal
- synchronous qualified, flattened, and nested host calls
- borrowed callback arguments, owned callback results, and structured callback failures
- `import_binary()` / `load_native()` module facades
- native `new()`, `add_modules()`, `expose()`, `set()`, `get()`, `remove()`, `execute()`, `evaluate()`, and snapshots
- automatic Python scalar, module, object, mapping, and callable adaptation
- exact native snapshot restoration with post-snapshot global cleanup
- checked value-kind/conversion and buffer-copy operations
- per-runtime structured error status, type, message, line, and column
- retain/release and runtime-owned teardown
- precedence-aware integer arithmetic, powers, shifts, and bitwise expressions
- string/bytes concatenation and repetition
- native `None`, boolean, quoted string, bytes, and immutable tuple literals
- empty, single-item, multi-item, and nested tuples
- positive, negative, and chained tuple indexing
- tuple-aware `len()`, truthiness, and recursive structural equality
- UTF-8 source literals across hosted Unicode and native byte-oriented source boundaries
- tuple values passed through native functions and control flow
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
- missing, duplicate, unexpected, parameter-kind, and positional-after-keyword argument errors
- callable value handles and cross-`exec` function persistence
- local call-frame save/restore without leaking local bindings
- quote-aware comments and separators
- exact public export allowlists
- Linux position-independent linking with no text relocations
- independent Linux and Windows C and Python conformance hosts
- reproducible native builds pinned to a verified asmpython compiler commit

This preview is **not** the final standalone Python 3.14 interpreter release. Tuple support in this slice is source-facing; public tuple extraction and automatic high-level tuple boxing remain separate ABI work. Other remaining gates include variadic parameters, native list/dict containers, closures, classes, broader object/container syntax, full traceback-frame retrieval, and native module imports.

## Relationship to pyinbin

`pyinbin` remains tailored to asmpython's native/static import pipeline and packaged-source fallback. PortaPy forks the reusable interpreter core and exposes it as a separately versioned embeddable product.

See `docs/DESIGN.md`, `RELEASE_STATUS.json`, and `include/portapy.h`.
