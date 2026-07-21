# Native 3.14 Status

This file records the boundary between verified build mechanics and a releasable
PortaPy interpreter. A probe library is not a PortaPy release.

## Verified or actively gated

- PortaPy owns Python-authored bytecode, frontend, VM, lexer, parser, AST-node,
  and diagnostic modules.
- The standalone frontend parses and lowers source without importing host `ast`.
- Portable lowering now preserves module source order and covers:
  - scalar and container expressions, slicing, mutation, deletion, and unpacking,
  - functions, defaults, decorators, keyword calls, `*args`, and `**kwargs`,
  - lexical closures, captured free variables, persistent `nonlocal` state, and
    isolated closure instances,
  - classes, class variables, inheritance, constructors, attributes, and methods,
  - `if`, `while`, ordinary and unpacking `for`, loop `else`, break, and continue,
  - imports supplied by the host, context managers, raised exceptions, typed
    `try` handlers, `else`, and `finally`,
  - generators, comprehensions, lambdas, f-strings, walrus expressions, and
    structural pattern matching.
- The full-core native transition probe compiles the mature
  `portapy.core.frontend` and `VirtualMachine` together on Windows and Linux.
- The full-core probe generates its private parser runtime from
  `src/portapy/parser`; asmpython remains the compiler rather than the parser
  implementation being embedded.
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
- Returned native lexical closures capture cells, preserve isolated closure
  instances, and observe later mutation of captured state.
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
  - ELF relocatable constant tables are moved out of read-only data,
  - ELF version scripts and Windows `.def` files limit public exports.
- Low-level external hosts invoke the generated module initializer explicitly;
  `portapy_new()` performs library initialization automatically.

## Release-blocking work

The remaining blockers for a final standalone `3.14` release are:

1. Replace the incremental native parser/executor behind exported
   `portapy_execute` and `portapy_evaluate` with the standalone frontend and VM.
2. Complete the remaining semantic edges needed by the final path, especially
   async/coroutines, descriptor-heavy class behavior, and unsupported parser
   corner cases.
3. Prove the final Windows and Linux libraries execute without CPython or a
   Python installation.
4. Run the final release matrix, verify exact export tables and no Linux
   `TEXTREL`, and attach checksums, headers, examples, and build metadata.

Runtime handles, values, UTF-8 execution, functions, closures, classes, imports,
callbacks, containers, structured errors, traceback frames, and the
language-neutral embedding API are implemented and must remain gated during the
final native architectural transition.

## Non-negotiable implementation rule

Parser, bytecode compiler, VM, object model, imports, exceptions, builtins, and
Python-level standard library remain Python source compiled by asmpython. NASM,
C, linker scripts, and `.def` files may only adapt the ABI/build boundary; they
must not implement interpreter semantics.
