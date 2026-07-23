"""Normalize MAKE_FUNCTION for the native compiler.

The frontend is normalized to emit one canonical four-field native list for
all functions and lambdas: ``[code, default_count, kw_default_count,
annotations]``. Unpack those fields directly. Runtime tuple/list introspection
is unsafe here because the pinned compiler lowers ``len(spec)`` to ``strlen``.

The block also avoids slices and comprehensions because native slice objects are
intentionally disabled during bootstrap.
"""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/vm.py")

_START = "                elif op is Op.MAKE_FUNCTION:\n"
_END = "                elif op is Op.MAKE_CLASS:\n"

_REPLACEMENT = '''                elif op is Op.MAKE_FUNCTION:
                     spec = frame.code.constants[instr.arg]
                     nested: CodeObject = spec[0]
                     default_count = spec[1]
                     kw_default_count = spec[2]
                     annotations: dict[str, object] = spec[3]
                     count = default_count + kw_default_count
                     if len(frame.stack) < count:
                         _raise_typed("RuntimeError: default stack underflow")
                     values: list[object] = []
                     if count:
                         value_index = len(frame.stack) - count
                         while value_index < len(frame.stack):
                             values.append(frame.stack[value_index])
                             value_index += 1
                         removed = 0
                         while removed < count:
                             discarded_default = frame.stack.pop()
                             removed += 1
                     defaults: list[object] = []
                     default_index = 0
                     while default_index < default_count:
                         defaults.append(values[default_index])
                         default_index += 1
                     kw_defaults: dict[str, object] = {}
                     kw_index = 0
                     kw_name_start = len(nested.kwonly_names) - kw_default_count
                     while kw_index < kw_default_count:
                         kw_name = nested.kwonly_names[kw_name_start + kw_index]
                         kw_defaults[kw_name] = values[default_count + kw_index]
                         kw_index += 1
                     closure: dict[str, object] = {}
                     for name in nested.free_names:
                         if name in frame.locals:
                             closure[name] = frame.locals[name]
                         elif frame.closure is not None and name in frame.closure:
                             closure[name] = frame.closure[name]
                     nested.validate()
                     function = Function(nested, frame.globals, defaults, kw_defaults, closure, self)
                     if annotations:
                         function._metadata["__annotations__"] = dict(annotations)
                     frame.stack.append(function)
'''

_LEGACY_DEFAULTS_SHAPE = (
    "values = frame.stack[-count:] if count else []",
    "defaults = values[:default_count]",
    "kw_defaults = {",
)

_NATIVE_SEMANTICS_DEFAULTS_SHAPE = (
    "values = _full_core_probe_pop_tail(frame.stack, count)",
    "defaults = _full_core_probe_copy_range(values, 0, default_count)",
    "kw_defaults: dict[str, object] = {}",
    "while kw_index < kw_default_count:",
)


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    start = source.find(_START)
    if start < 0:
        raise RuntimeError("native MAKE_FUNCTION handler start not found")
    end = source.find(_END, start + len(_START))
    if end < 0:
        raise RuntimeError("native MAKE_FUNCTION handler end not found")
    if source.find(_START, start + len(_START)) >= 0:
        raise RuntimeError("native MAKE_FUNCTION handler is not unique")

    block = source[start:end]
    required = (
        "spec = frame.code.constants[instr.arg]",
        "count = default_count + kw_default_count",
        "closure = {",
        "function = Function(nested, frame.globals, defaults, kw_defaults, closure, self)",
        "frame.stack.append(function)",
    )
    missing = [marker for marker in required if marker not in block]
    if missing:
        raise RuntimeError(f"native MAKE_FUNCTION source shape changed: {missing}")

    defaults_shapes = (_LEGACY_DEFAULTS_SHAPE, _NATIVE_SEMANTICS_DEFAULTS_SHAPE)
    if not any(all(marker in block for marker in shape) for shape in defaults_shapes):
        raise RuntimeError("native MAKE_FUNCTION source shape changed: default extraction")

    source = source[:start] + _REPLACEMENT + source[end:]
    PATH.write_text(source, encoding="utf-8")

    installed = source[start:start + len(_REPLACEMENT)]
    validation = (
        "nested: CodeObject = spec[0]",
        "default_count = spec[1]",
        "kw_default_count = spec[2]",
        "annotations: dict[str, object] = spec[3]",
        "while default_index < default_count:",
        "while kw_index < kw_default_count:",
        "for name in nested.free_names:",
        "discarded_default = frame.stack.pop()",
    )
    absent = [marker for marker in validation if marker not in installed]
    if absent:
        raise RuntimeError(f"native MAKE_FUNCTION validation failed: {absent}")
    forbidden = (
        "len(spec)",
        "spec_size",
        "isinstance(spec, tuple)",
        "isinstance(nested, CodeObject)",
        "nested: CodeObject = spec\n",
        "frame.stack[-count:]",
        "values[:default_count]",
    )
    remaining = [marker for marker in forbidden if marker in installed]
    if remaining:
        raise RuntimeError(f"native MAKE_FUNCTION unsafe forms remain: {remaining}")
    print("NORMALIZED NATIVE MAKE_FUNCTION", 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
