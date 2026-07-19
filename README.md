# PortaPy

PortaPy is a separately versioned, embeddable interpreter project derived from the reusable Python-written core of asmpython's `pyinbin` interpreter.

The interpreter implementation is required to remain Python source compiled by asmpython. The public C ABI and generated assembly passes are only host/build boundaries; they do not implement parsing, evaluation, objects, imports, or exception semantics.

Native artifact names:

- `portapy.dll` on Windows
- `libportapy.so` on Linux
- `libportapy.dylib` on macOS when that asmpython target becomes available

## 3.14 Developer Preview 1

`3.14-dev.1` is the first genuine native-library preview. Its runtime state and value ownership are Python-authored and compiled by asmpython. Linux and Windows artifacts are loaded and exercised from independent C processes before publication.

Implemented native ABI surface:

- isolated runtime handles
- `None`, normalized `bool`, signed 64-bit integer, and bit-exact binary64 value handles
- checked value-kind/conversion operations
- retain/release and runtime-owned teardown
- exact public export allowlists
- Linux position-independent linking with no text relocations

This preview is **not** the final standalone Python 3.14 interpreter release. The vendored bootstrap frontend still uses host Python's `ast` module to parse source. Final source execution remains gated until PortaPy's own Python-written lexer/parser, native VM execution entry points, structured errors, callbacks, imports, strings, and bytes are complete.

## Relationship to pyinbin

`pyinbin` remains tailored to asmpython's native/static import pipeline and packaged-source fallback. PortaPy forks the reusable interpreter core and exposes it as a separately versioned embeddable product.

See `docs/DESIGN.md`, `RELEASE_STATUS.json`, and `include/portapy.h`.
