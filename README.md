# PortaPy

PortaPy is a fully Python-built embeddable Python interpreter derived from the reusable core of asmpython's `pyinbin` interpreter.

Its parser, bytecode compiler, virtual machine, object model, imports, exceptions, builtins, and Python-level standard library are written in Python source and compiled by asmpython into native shared libraries:

- `portapy.dll` on Windows
- `libportapy.so` on Linux
- `libportapy.dylib` on macOS when the target is available

The public C ABI is only a thin host boundary around that generated interpreter. PortaPy is not a CPython embedding wrapper and does not implement interpreter semantics in C, C++, Rust, or assembly.

## Version 3.14 status

The standalone repository and provisional ABI are being established first. A `3.14` binary release must not be published until the libraries are genuine asmpython-produced artifacts and pass the external C host conformance suite without CPython present at runtime.

## Relationship to pyinbin

`pyinbin` remains tailored to asmpython's native/static import pipeline and packaged-source fallback. PortaPy forks the reusable Python interpreter core and exposes it as a separately versioned embeddable product.

See `docs/DESIGN.md` and `include/portapy.h`.
