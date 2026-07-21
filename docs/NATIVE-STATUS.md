# Native 3.14 Status

This file records the boundary between verified build mechanics and a releasable
PortaPy interpreter. A probe library is not a PortaPy release.

## Verified or actively gated

- PortaPy owns a standalone fork of pyinbin's Python-authored bytecode, frontend,
  and VM modules.
- Hosted tests execute the fork without importing `asmpython.pyinbin`.
- asmpython's legacy backend generates the native NASM used for Windows and Linux
  shared libraries.
- The public native contract is a language-neutral C ABI.
- `portapy_environment` and `portapy_runtime` are the same opaque handle, allowing
  helper and fine-grained APIs to be mixed without conversion.
- `portapy_new`, `portapy_add`, `portapy_add_all`, `portapy_execute`,
  `portapy_evaluate`, and `portapy_destroy` are real library exports.
- Direct helper callbacks and raw `portapy_host_set_call_handler` callbacks can
  coexist inside one environment.
- Hosted Python, native Python, external C, and direct C# P/Invoke probes exercise
  the environment helper surface.
- Module loading belongs to the host language. PortaPy intentionally does not
  expose an embedding-level `import_module` helper.
- Native `import` and `from ... import ...` statements resolve host-added module
  objects, including aliases and dotted object paths.
- Missing native modules and members produce structured `ModuleNotFoundError` and
  `ImportError` state.
- The public traceback ABI exposes indexed filename, function, line, column, and
  source-line frames. Native Python exposes the same data as
  `NativeTracebackFrame` objects.
- Traceback frames are reset on new execution/evaluation, error clearing, and
  runtime destruction.
- Build-only passes are independently tested:
  - executable module initialization becomes an explicit returning library call,
  - public labels are declared from an explicit allowlist,
  - ELF external functions use PLT and external data uses GOT,
  - unsupported external memory forms fail closed,
  - ELF version scripts and Windows `.def` files limit public exports.
- Low-level external hosts invoke the generated module initializer explicitly;
  `portapy_new()` performs library initialization automatically.

## Release-blocking work

The remaining blockers for a final standalone `3.14` release are:

1. Replace the temporary standalone parser/executor path with the complete
   Python-authored frontend and bytecode VM.
2. Remove the compiled frontend's dependency on host `ast`; source parsing must
   be fully contained in PortaPy's compiled Python source.
3. Carry the mature hosted closure, class, descriptor, exception, generator, and
   async semantics through that standalone native frontend/VM path.
4. Complete broader native object syntax and object-model conformance.
5. Prove the final libraries execute without CPython or a Python installation.
6. Run the final release matrix, verify exact export tables and no Linux
   `TEXTREL`, and attach checksums, headers, examples, and build metadata.

Runtime handles, values, UTF-8 execution, functions, imports, callbacks,
containers, structured errors, and traceback frames are already implemented and
must remain gated while the architectural transition proceeds.

## Non-negotiable implementation rule

Parser, bytecode compiler, VM, object model, imports, exceptions, builtins, and
Python-level standard library remain Python source compiled by asmpython. NASM,
C, linker scripts, and `.def` files may only adapt the ABI/build boundary; they
must not implement interpreter semantics.
