# PortaPy

PortaPy is a separately versioned, embeddable interpreter project derived from the reusable Python-written core of asmpython's `pyinbin` interpreter.

The interpreter implementation is required to remain Python source compiled by asmpython. The public C ABI and generated assembly passes are only host/build boundaries; they do not implement parsing, evaluation, objects, imports, or exception semantics.

Native artifact names:

- `portapy.dll` on Windows
- `libportapy.so` on Linux
- `libportapy.dylib` on macOS when that asmpython target becomes available

## Public embedding API

The hosted Python package and the future `import_binary` module-object bridge share one public shape:

```python
portapy = import_binary("portapy.dll")

import math
from somnia import env

environment = portapy.new()
environment.add_modules(math)
environment.expose(env)
environment.execute("""
http_service = game.provider.HttpProvider
root = math.sqrt(81)
""")
snapshot = environment.snapshot()
```

`add_modules(...)` keeps each module under its normal module name. `expose(...)` flattens public members into the executed environment, which is how `env.game` becomes plain `game`. `add_builtin(...)` remains an alias for compatibility, but `expose(...)` is the preferred name.

Snapshots are shallow binding snapshots: restoring one restores the environment's global names and referenced objects, but it does not reverse mutations made inside arbitrary host objects, services, or native handles.

The same API is available from the hosted package with `import portapy` while the native module-object bridge is completed.

## 3.14 Developer Preview 1

`3.14-dev.1` is the first genuine native-library preview. Its runtime state, value ownership, text storage, source parsing, UTF-8 validation, and structured error state are Python-authored and compiled by asmpython. Linux and Windows artifacts are loaded and exercised from independent C processes before publication.

Implemented native ABI and source surface:

- isolated runtime handles
- `None`, normalized `bool`, signed 64-bit integer, and bit-exact binary64 value handles
- UTF-8 string handles and arbitrary byte handles, including embedded NUL bytes
- checked value-kind/conversion and buffer-copy operations
- per-runtime structured error status, type, message, line, and column
- retain/release and runtime-owned teardown
- integer arithmetic expressions
- native `None`, boolean, quoted string, and bytes literals
- equality, ordering, `is`, and `is not` comparisons
- `not`, `and`, and `or` with Python-style truthiness and operand returns
- typed global assignment, lookup, aliasing, and `eval`
- newline/semicolon statement blocks with quote-aware comments and separators
- indented `if`/`else` and nested blocks
- `while`, `pass`, `break`, `continue`, and expression statements
- exact public export allowlists
- Linux position-independent linking with no text relocations
- independent Linux and Windows C conformance hosts
- reproducible native builds pinned to a verified asmpython compiler commit

This preview is **not** the final standalone Python 3.14 interpreter release. Final source execution remains gated on functions and calls in the standalone native parser, broader object/container syntax, full traceback-frame retrieval, the native host-object bridge, and module imports.

## Relationship to pyinbin

`pyinbin` remains tailored to asmpython's native/static import pipeline and packaged-source fallback. PortaPy forks the reusable interpreter core and exposes it as a separately versioned embeddable product.

See `docs/DESIGN.md`, `RELEASE_STATUS.json`, and `include/portapy.h`.
