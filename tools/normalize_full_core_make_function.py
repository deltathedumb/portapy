"""Normalize MAKE_FUNCTION for the native compiler.

The compiled VM represents user-class values as compact native class values.
A runtime ``isinstance(nested, CodeObject)`` therefore dereferences that value
as an object dictionary and crashes.  Give ``nested`` an explicit static
CodeObject type instead and trust the frontend-produced constant.

The original block also uses list slices and comprehensions while native slice
objects are intentionally disabled during bootstrap.  Replace those operations
with index-based loops so defaults, keyword defaults, and closure cells retain
full semantics without unsupported runtime shapes.
"""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/vm.py")

_START = "                elif op is Op.MAKE_FUNCTION:\n"
_END = "                elif op is Op.MAKE_CLASS:\n"

_REPLACEMENT = '''                elif op is Op.MAKE_FUNCTION:
                     spec = frame.code.constants[instr.arg]
                     nested: CodeObject = spec
                     default_count = 0
                     kw_default_count = 0
                     annotations: dict[str, object] = {}
                     if isinstance(spec, tuple) and len(spec) == 4:
                         nested, default_count, kw_default_count, annotations = spec
                     elif isinstance(spec, tuple) and len(spec) == 2:
                         nested, default_count = spec
                     elif isinstance(spec, tuple) and len(spec) == 3:
                         nested, default_count, kw_default_count = spec
                     else:
                         nested = spec
                     if nested is None:
                         _raise_typed("TypeError: invalid function constant")
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
        "if not isinstance(nested, CodeObject)",
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
        "nested: CodeObject = spec",
        "if nested is None:",
        "while default_index < default_count:",
        "while kw_index < kw_default_count:",
        "for name in nested.free_names:",
        "discarded_default = frame.stack.pop()",
    )
    absent = [marker for marker in validation if marker not in installed]
    if absent:
        raise RuntimeError(f"native MAKE_FUNCTION validation failed: {absent}")
    forbidden = (
        "isinstance(nested, CodeObject)",
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
