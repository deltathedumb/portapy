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

`add_modules()` preserves qualified access such as `math.floor`. `expose()` is the flattened-namespace operation: it makes public values from a module, object, or mapping available directly, which is the role previously described as `add_builtin`. Snapshots are detached, read-only shallow views exposed through `snapshot.var`.

The same API is available from the hosted package today:

```python
import portapy

environment = portapy.new()
environment.expose({"seed": 41})
environment.execute("answer = seed + 1")
assert environment.snapshot().var["answer"] == 42
```

The artifact metadata records `new`, `Environment`, `Snapshot`, and the public exception/status types as the stable Python-module export surface. Native arbitrary-object injection still depends on the host-callback ABI gate; scalar execution continues to use the existing opaque-handle C ABI.

## 3.14 Developer Preview 1

`3.14-dev.1` is the first genuine native-library preview. Its runtime state, value ownership, text storage, source parsing, UTF-8 validation, and structured error state are Python-authored and compiled by asmpython. Linux and Windows artifacts are loaded and exercised from independent C processes before publication.

Implemented native ABI and source surface:

- isolated runtime handles
- `None`, normalized `bool`, signed 64-bit integer, and bit-exact binary64 value handles
- UTF-8 string handles and arbitrary byte handles, including embedded NUL bytes
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
- quote-aware comments and separators
- exact public export allowlists
- Linux position-independent linking with no text relocations
- independent Linux and Windows C conformance hosts
- reproducible native builds pinned to a verified asmpython compiler commit

This preview is **not** the final standalone Python 3.14 interpreter release. Final source execution remains gated on compound statements, functions and calls, full traceback-frame retrieval, native host callbacks, and module imports.

## Relationship to pyinbin

`pyinbin` remains tailored to asmpython's native/static import pipeline and packaged-source fallback. PortaPy forks the reusable interpreter core and exposes it as a separately versioned embeddable product.

See `docs/DESIGN.md`, `RELEASE_STATUS.json`, and `include/portapy.h`.
