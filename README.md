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

from somnia import env

environment = portapy.new()
environment.expose(env)
environment.execute("""
http_provider = game.provider.HttpProvider
""")

snapshot = environment.snapshot()
http_provider = snapshot.var["http_provider"]
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

The native C ABI now provides the data bridge required by the Somnia-shaped example:

- `portapy_value_from_host_object()` creates an opaque object value from a stable host ID.
- `portapy_set_global_utf8()` injects retained globals such as `game`.
- `portapy_host_set_attr_utf8()` builds host-owned attribute graphs.
- PortaPy source can traverse paths such as `game.provider.HttpProvider`.
- `portapy_value_get_host_id()` maps evaluated or snapshotted object handles back to host objects.

Artifact metadata records `new`, `Environment`, `EnvironmentSnapshot`, `Snapshot`, and the public exception/status types as the stable Python-module surface. The remaining binary-module adapter work is mapping `add_modules()` and `expose()` onto this C ABI automatically. Calling host functions such as `math.floor()` additionally requires the synchronous host-call dispatch gate.

## 3.14 Developer Preview 1

`3.14-dev.1` is the first genuine native-library preview. Its runtime state, value ownership, text storage, source parsing, UTF-8 validation, structured error state, control flow, positional functions, and host-object graph are Python-authored and compiled by asmpython. Linux and Windows artifacts are loaded and exercised from independent C processes before publication.

Implemented native ABI and source surface:

- isolated runtime handles
- `None`, normalized `bool`, signed 64-bit integer, bit-exact binary64, string, bytes, callable, and opaque object handles
- stable 64-bit host IDs and host-ID recovery
- retained native global injection
- host attribute graph registration, replacement, lookup, and dotted traversal
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

This preview is **not** the final standalone Python 3.14 interpreter release. Remaining gates include compound statements inside functions, defaults/keyword arguments, closures, classes, broader object/container syntax, synchronous host-call dispatch, automatic binary-module environment adaptation, full traceback-frame retrieval, and native module imports.

## Relationship to pyinbin

`pyinbin` remains tailored to asmpython's native/static import pipeline and packaged-source fallback. PortaPy forks the reusable interpreter core and exposes it as a separately versioned embeddable product.

See `docs/DESIGN.md`, `RELEASE_STATUS.json`, and `include/portapy.h`.
