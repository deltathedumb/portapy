"""Preserve default-argument AST nodes through the standalone native bridge.

``A.FuncDef.defaults`` is an opaque external list to the pinned compiler.  A bare
``node.defaults[index]`` therefore receives the compiler's scalar fallback type;
conversion of a real ``IntLit``/``StrLit`` can collapse to a null AST pointer.
The frontend later calls ``_Lowerer.expr(None)`` while defining a function with
defaults and crashes in its unsupported-expression formatter.

Read the field dynamically and pin list elements to the native AST's dict-backed
representation before passing them to ``_convert_expr``.
"""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/native_ast.py")

_OLD = '''def _convert_arguments(node: A.FuncDef, lifted: dict[str, A.FuncDef]) -> arguments:
    all_args = [arg(name) for name in node.params]
    defaults: list[expr] = []
    first_default = len(node.defaults)
    index = 0
    while index < len(node.defaults):
        if node.defaults[index] is not None:
            first_default = index
            break
        index += 1
    if first_default < len(node.defaults):
        index = first_default
        while index < len(node.defaults):
            defaults.append(_convert_expr(node.defaults[index], lifted))
            index += 1
    return arguments([], all_args, None if node.vararg is None else arg(node.vararg), [], [], None if node.kwarg is None else arg(node.kwarg), defaults)
'''

_NEW = '''def _convert_arguments(node: A.FuncDef, lifted: dict[str, A.FuncDef]) -> arguments:
    all_args = [arg(name) for name in node.params]
    defaults: list[expr] = []
    native_defaults: list[dict] = getattr(node, "defaults")
    first_default = len(native_defaults)
    index = 0
    while index < len(native_defaults):
        default_node: dict = native_defaults[index]
        if default_node is not None:
            first_default = index
            break
        index += 1
    if first_default < len(native_defaults):
        index = first_default
        while index < len(native_defaults):
            default_node: dict = native_defaults[index]
            defaults.append(_convert_expr(default_node, lifted))
            index += 1
    return arguments([], all_args, None if node.vararg is None else arg(node.vararg), [], [], None if node.kwarg is None else arg(node.kwarg), defaults)
'''


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    old_count = source.count(_OLD)
    new_count = source.count(_NEW)
    if old_count == 1 and new_count == 0:
        source = source.replace(_OLD, _NEW, 1)
        changed = 1
    elif old_count == 0 and new_count == 1:
        changed = 0
    else:
        raise RuntimeError(
            "native default argument bridge source shape changed: "
            f"old={old_count}, normalized={new_count}"
        )
    PATH.write_text(source, encoding="utf-8")

    required = (
        'native_defaults: list[dict] = getattr(node, "defaults")',
        "default_node: dict = native_defaults[index]",
        "defaults.append(_convert_expr(default_node, lifted))",
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        raise RuntimeError(f"native default argument validation failed: {missing}")
    forbidden = (
        "first_default = len(node.defaults)",
        "_convert_expr(node.defaults[index], lifted)",
    )
    remaining = [marker for marker in forbidden if marker in source]
    if remaining:
        raise RuntimeError(f"unsafe native default extraction remains: {remaining}")
    print("NORMALIZED NATIVE DEFAULT ARGUMENT NODES", changed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
