# Native 3.14 Status

This file records the boundary between verified build mechanics and a releasable
PortaPy interpreter. A probe library is not a PortaPy release.

## Verified or actively gated

- PortaPy owns a standalone fork of pyinbin's Python-authored bytecode, frontend,
  and VM modules.
- Hosted tests execute the fork without importing `asmpython.pyinbin`.
- asmpython's legacy backend generates the native NASM used for Windows and Linux
  shared libraries.
- Build-only passes are independently tested:
  - executable module initialization becomes an explicit returning library call,
  - public labels are declared from an explicit allowlist,
  - ELF external functions use PLT and external data uses GOT,
  - unsupported external memory forms fail closed,
  - ELF version scripts and Windows `.def` files limit public exports.
- External C hosts load the produced libraries and must invoke the generated
  module initializer before any API call.

## Release-blocking work

The `3.14` release workflow must remain blocked until all of these are true:

1. `portapy.dll` and `libportapy.so` contain the complete Python-built interpreter,
   not only the bytecode/native-build probe.
2. The frontend no longer imports host `ast`; source parsing must be part of the
   compiled PortaPy Python source.
3. Runtime create/destroy and opaque value handles are implemented through the
   public header.
4. UTF-8 source execution and evaluation work through external C hosts.
5. Function calls, checked primitive conversions, structured errors, and
   retain/release work through the public ABI.
6. The libraries execute on machines without CPython or a Python installation.
7. Export tables exactly match the documented ABI.
8. Linux has no `TEXTREL`; Windows and Linux hosts pass independently.
9. Checksums, header, examples, and machine-readable build metadata are attached.

## Non-negotiable implementation rule

Parser, bytecode compiler, VM, object model, imports, exceptions, builtins, and
Python-level standard library remain Python source compiled by asmpython. NASM,
C, linker scripts, and `.def` files may only adapt the ABI/build boundary; they
must not implement interpreter semantics.
