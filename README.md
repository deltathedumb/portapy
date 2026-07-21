# PortaPy

PortaPy is a separately versioned, embeddable interpreter project derived from the reusable Python-written core of asmpython's `pyinbin` interpreter.

The interpreter implementation is required to remain Python source compiled by asmpython. The public C ABI and generated assembly passes are only host/build boundaries; they do not implement parsing, evaluation, objects, imports, or exception semantics.

Native artifact names:

- `portapy.dll` on Windows
- `libportapy.so` on Linux
- `libportapy.dylib` on macOS when that asmpython target becomes available

## High-level API

The intended binary-module interface is environment-oriented:

```python
portapy = import_binary("portapy.dll")

import math
from somnia import env

environment = portapy.new()
environment.add_modules(math)
environment.expose(env)
environment.execute("""
http_provider = game.provider.HttpProvider
answer = math.floor(41.9) + 1
""")

snapshot = environment.snapshot()
http_provider = snapshot.var["http_provider"]
answer = snapshot.var["answer"]
```

`add_modules()` preserves qualified access such as `math.floor`. `expose()` is the flattened-namespace operation: it makes public values from a module, object, or mapping available directly. `add_builtin()` remains a compatibility alias, but `expose()` is the preferred name.

Snapshots capture a shallow, detached set of global bindings. `snapshot.var` is a read-only mapping, while `snapshot.restore()` restores those bindings to the originating environment. Mutations inside referenced host objects are intentionally not deep-rolled back.

The same API is available from the hosted package today:

```python
import portapy

environment = portapy.new()
environment.expose({"seed": 41})
environment.execute("answer = seed + 1")
assert environment.snapshot().var["answer"] == 42
```

The native C ABI now provides the object and callable bridge required by the same model:

- `portapy_value_from_host_object()` creates an opaque object value from a stable host ID.
- `portapy_value_from_host_callable()` creates a callable value from a stable callable ID.
- `portapy_set_global_utf8()` injects retained globals such as `game` or `math`.
- `portapy_host_set_attr_utf8()` builds host-owned attribute graphs.
- PortaPy source can traverse paths such as `game.provider.HttpProvider`.
- `portapy_host_set_call_handler()` installs one synchronous dispatcher per runtime.
- Callback arguments are borrowed PortaPy handles; callback results transfer one owned handle back to the interpreter.
- Qualified and flattened calls, including nested calls, work on Linux and Windows.
- `portapy_value_get_host_id()` maps evaluated or snapshotted object handles back to host objects.

Artifact metadata records `new`, `Environment`, `EnvironmentSnapshot`, `Snapshot`, and the public exception/status types as the stable Python-module surface. The remaining adapter work is making `import_binary()` automatically map `add_modules()` and `expose()` onto the C object/callable bridge.

## 3.14 Developer Preview 1

`3.14-dev.1` is the first genuine native-library preview. Its runtime state, value ownership, text storage, source parsing, UTF-8 validation, structured error state, control flow, positional functions, host-object graph, and host-call parser are Python-authored and compiled by asmpython. Linux and Windows artifacts are loaded and exercised from independent C processes before publication.

Implemented native ABI and source surface:

- isolated runtime handles
- `None`, normalized `bool`, signed 64-bit integer, bit-exact binary64, string, bytes, callable, and opaque object handles
- stable 64-bit host object and callable IDs
- retained native global injection
- host attribute graph registration, replacement, lookup, and dotted traversal
- synchronous qualified, flattened, and nested host calls
- borrowed callback arguments, owned callback results, and structured callback failures
- checked value-kind/conversion and buffer-copy operations
- per-runtime structured error status, type, message, line, and column
- retain/release and runtime-owned teardown
- precedence-aware integer arithmetic, powers, shifts, and bitwise expressions
- string/bytes concatenation and repetition
- native `None`, boolean, quoted string, and bytes literals
- equality, ordering, `is`, and `is not` comparisons
- `not`, `and`, and `or` with Python-style truthiness and operand returns
- typed global assignment, lookup, aliasing, augmented assignment, and `eval`
- newline/semicolon statement blocks, bare expressions, and `pass`
- indented `if`/`else`, nested blocks, and `while`
- `break` and `continue`
- positional `def` functions, zero/multi-argument calls, nested calls, and `return`
- callable value handles and cross-`exec` function persistence
- local call-frame save/restore without leaking local bindings
- quote-aware comments and separators
- exact public export allowlists
- Linux position-independent linking with no text relocations
- independent Linux and Windows C conformance hosts
- reproducible native builds pinned to a verified asmpython compiler commit

This preview is **not** the final standalone Python 3.14 interpreter release. Remaining gates include compound statements inside functions, defaults/keyword arguments, closures, classes, broader object/container syntax, automatic binary-module environment adaptation, full traceback-frame retrieval, and native module imports.

## Relationship to pyinbin

`pyinbin` remains tailored to asmpython's native/static import pipeline and packaged-source fallback. PortaPy forks the reusable interpreter core and exposes it as a separately versioned embeddable product.

See `docs/DESIGN.md`, `RELEASE_STATUS.json`, and `include/portapy.h`.
