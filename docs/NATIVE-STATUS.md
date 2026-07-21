# Native 3.14 Status

This file records the boundary between implemented runtime architecture, verified
build mechanics, and a releasable PortaPy interpreter. A probe library is not a
release, and queued CI is not treated as a passing result.

## Implemented and actively gated

- PortaPy owns Python-authored bytecode, frontend, VM, lexer, parser, AST-node,
  diagnostic, object-model, import, exception, and builtin modules.
- The standalone frontend parses and lowers source without importing host `ast`.
- Portable lowering preserves module source order and covers:
  - scalar and container expressions, slicing, mutation, deletion, and unpacking,
  - functions, defaults, decorators, keyword calls, `*args`, and `**kwargs`,
  - lexical closures, captured free variables, persistent `nonlocal` state, and
    isolated closure instances,
  - classes, class variables, inheritance, constructors, descriptors, attributes,
    methods, static methods, class methods, and properties,
  - `if`, `while`, ordinary and unpacking `for`, loop `else`, break, and continue,
  - imports supplied by the host, context managers, raised exceptions, typed
    `try` handlers, `else`, and `finally`,
  - generators, async functions, `await`, async generators, comprehensions,
    lambdas, f-strings, walrus expressions, and structural pattern matching.
- The generated native environment now has a canonical full-runtime adapter:
  - the existing public ABI handle tables remain the marshalling representation,
  - values are recursively unboxed into the standalone VM and boxed back,
  - VM namespaces persist independently per runtime,
  - PortaPy-owned functions, closures, classes, and instances use opaque retained
    handles without being misreported as host objects,
  - host objects and host callables are exposed to the VM through proxies using
    the existing callback protocol,
  - host-added modules remain the source for native import resolution,
  - VM frame metadata is published through the existing traceback ABI.
- `tools/build_native_typed.py` prepares and selects the standalone frontend and
  full VM by default. Focused compiler probes may still pass `--source`.
- The generated standalone source is parsed by the pinned asmpython parser before
  native compilation and is also executed directly in hosted tests.
- The canonical Linux and Windows jobs run one artifact through advanced VM,
  environment, callback, import, traceback, float, tuple, dictionary, and list
  conformance hosts.
- asmpython's legacy backend generates the native NASM used for Windows and Linux
  shared libraries.
- The public native contract remains a language-neutral C ABI.
- `portapy_environment` and `portapy_runtime` are the same opaque handle, allowing
  helper and fine-grained APIs to be mixed without conversion.
- `portapy_new`, `portapy_add`, `portapy_add_all`, `portapy_execute`,
  `portapy_evaluate`, and `portapy_destroy` are real library exports.
- Direct helper callbacks and raw `portapy_host_set_call_handler` callbacks can
  coexist inside one environment.
- Module loading belongs to the host language. PortaPy intentionally does not
  expose an embedding-level `import_module` helper.
- The public traceback ABI exposes indexed filename, function, line, column, and
  source-line frames. Native Python exposes the same data as
  `NativeTracebackFrame` objects.
- Build-only passes remain independently tested:
  - executable module initialization becomes an explicit returning library call,
  - public labels are declared from an explicit allowlist,
  - ELF external functions use PLT and external data uses GOT,
  - unsupported external memory forms fail closed,
  - ELF relocatable constant tables are moved out of read-only data,
  - ELF version scripts and Windows `.def` files limit public exports.

## Release-blocking verification

The runtime architecture is implemented. The remaining blockers for declaring a
final standalone `3.14.0` release are verification and packaging gates:

1. Obtain green hosted and pinned-compiler results for the canonical generated
   adapter.
2. Build and execute the final Windows and Linux shared libraries through the
   complete C matrix without loading or linking CPython.
3. Verify exact export tables, no Linux `TEXTREL`, artifact metadata, headers,
   examples, and checksums.
4. Change release status/version metadata from developer preview to final only
   after those gates pass.

## Non-negotiable implementation rule

Parser, bytecode compiler, VM, object model, imports, exceptions, builtins, and
Python-level standard library remain Python source compiled by asmpython. NASM,
C, linker scripts, and `.def` files may only adapt the ABI/build boundary; they
must not implement interpreter semantics.
