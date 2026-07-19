# PortaPy Design and 3.14 Requirements

PortaPy is the separately versioned, embeddable distribution of pyinbin's reusable interpreter core. Its parser, bytecode compiler, virtual machine, object model, imports, exceptions, builtins, and Python-level standard library remain Python source compiled by asmpython.

PortaPy is not a CPython embedding wrapper and is not a C/C++/Rust interpreter. Handwritten native code may only expose symbols, adapt calling conventions, and perform unavoidable platform bootstrap. It may not implement interpreter semantics.

## Products

- `portapy.dll` on Windows x86-64.
- `libportapy.so` on Linux x86-64.
- `libportapy.dylib` when macOS library output becomes available.

## Relationship to pyinbin

pyinbin keeps asmpython-specific source bundles, static/native import handoff, project metadata, and fallback diagnostics. PortaPy forks the reusable Python-built core: bytecode model, frontend, VM, object model, import engine, builtins, and interpreter stdlib.

Until an intentional divergence is documented, fixes to shared interpreter semantics must remain portable between pyinbin and PortaPy.

## Public ABI

The ABI uses opaque runtime/value handles and fixed-width primitives. It includes version negotiation, runtime create/destroy, UTF-8 source and bytecode execution, value retain/release, checked conversions, structured errors, host callbacks, module registration, interruption, and deterministic teardown.

Every exported function returns a status. Strings and buffers carry explicit lengths. Internal object/frame/bytecode layouts are private.

## Release 3.14 gates

A release is valid only when:

1. both libraries are produced by asmpython from the Python interpreter sources;
2. neither binary imports or launches CPython;
3. an external C host executes source, calls a function, converts values, receives an exception, and destroys/recreates runtimes;
4. exported symbols exactly match the public header;
5. Windows and Linux hosts pass independently;
6. checksums and machine-readable build metadata are attached.

Placeholder libraries or native-language interpreter implementations are forbidden.
