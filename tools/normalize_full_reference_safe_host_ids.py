"""Make native value access and nested container writes compiler-safe."""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/native_full_reference_entry.py")

_HOST_OBJECT_ID_SOURCE = '''
instance = _runtime(runtime)
if instance is None:
    _set_status(Status.INVALID_HANDLE)
    return 0
status, kind = instance.value_kind(value)
if status is not Status.OK:
    _set_status(status)
    return 0
if _native_value_kind_code(kind) != PORTAPY_VALUE_OBJECT:
    _set_status(Status.TYPE_ERROR)
    return 0
status, result = instance.unbox(value)
_set_status(status)
if status is not Status.OK:
    return 0
return result
'''

_HOST_CALLABLE_ID_SOURCE = '''
instance = _runtime(runtime)
if instance is None:
    _set_status(Status.INVALID_HANDLE)
    return 0
status, kind = instance.value_kind(value)
if status is not Status.OK:
    _set_status(status)
    return 0
if _native_value_kind_code(kind) != PORTAPY_VALUE_CALLABLE:
    _set_status(Status.TYPE_ERROR)
    return 0
status, result = instance.unbox(value)
_set_status(status)
if status is not Status.OK:
    return 0
return result
'''

_REPLACEMENTS = {
    "_portapy_value_get_host_id_impl": _HOST_OBJECT_ID_SOURCE,
    "_portapy_value_get_host_callable_id_impl": _HOST_CALLABLE_ID_SOURCE,
}


def _is_slot_value_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_slot_value"
        and len(node.args) == 2
        and not node.keywords
    )


class _LegacyValueLookupRewriter(ast.NodeTransformer):
    """Use Runtime._value_slot after the native runtime switches to a list."""

    def __init__(self) -> None:
        self.replaced = 0

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "_values"
            and isinstance(node.func.value.value, ast.Name)
            and node.func.value.value.id == "instance"
            and len(node.args) == 1
            and not node.keywords
        ):
            self.replaced += 1
            return ast.copy_location(
                ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="instance", ctx=ast.Load()),
                        attr="_value_slot",
                        ctx=ast.Load(),
                    ),
                    args=node.args,
                    keywords=[],
                ),
                node,
            )
        return node


class _NestedSlotValueHoister(ast.NodeTransformer):
    """Keep asmpython from emitting an odd push across a nested native call."""

    def __init__(self) -> None:
        self.hoisted = 0

    def _name(self) -> str:
        name = f"_native_slot_value_{self.hoisted}"
        self.hoisted += 1
        return name

    def visit_Assign(self, node: ast.Assign) -> ast.AST | list[ast.stmt]:
        self.generic_visit(node)
        if (
            len(node.targets) != 1
            or not isinstance(node.targets[0], ast.Subscript)
            or not _is_slot_value_call(node.value)
        ):
            return node
        name = self._name()
        value = node.value
        node.value = ast.copy_location(ast.Name(id=name, ctx=ast.Load()), value)
        temporary = ast.copy_location(
            ast.Assign(
                targets=[ast.Name(id=name, ctx=ast.Store())],
                value=value,
            ),
            node,
        )
        return [temporary, node]

    def visit_Expr(self, node: ast.Expr) -> ast.AST | list[ast.stmt]:
        self.generic_visit(node)
        call = node.value
        if (
            not isinstance(call, ast.Call)
            or not isinstance(call.func, ast.Attribute)
            or call.func.attr != "append"
            or len(call.args) != 1
            or call.keywords
            or not _is_slot_value_call(call.args[0])
        ):
            return node
        name = self._name()
        value = call.args[0]
        call.args[0] = ast.copy_location(ast.Name(id=name, ctx=ast.Load()), value)
        temporary = ast.copy_location(
            ast.Assign(
                targets=[ast.Name(id=name, ctx=ast.Store())],
                value=value,
            ),
            node,
        )
        return [temporary, node]


class _Rewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.replaced: set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        replacement = _REPLACEMENTS.get(node.name)
        if replacement is None:
            return self.generic_visit(node)
        node.body = ast.parse(replacement).body
        self.replaced.add(node.name)
        return node


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    rewrite = _Rewrite()
    module = rewrite.visit(module)
    value_lookup = _LegacyValueLookupRewriter()
    module = value_lookup.visit(module)
    hoister = _NestedSlotValueHoister()
    module = hoister.visit(module)
    missing = sorted(set(_REPLACEMENTS) - rewrite.replaced)
    if missing or value_lookup.replaced != 1 or hoister.hoisted != 4:
        raise RuntimeError(
            "native host ABI normalization missed shapes; "
            f"missing={missing}, value_lookups={value_lookup.replaced}, "
            f"nested_slot_calls={hoister.hoisted}"
        )
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")
    verified = ast.unparse(ast.parse(source))
    required = (
        "slot = instance._value_slot(handle)",
        "_native_value_kind_code(kind) != PORTAPY_VALUE_OBJECT",
        "_native_value_kind_code(kind) != PORTAPY_VALUE_CALLABLE",
        "status, result = instance.unbox(value)",
        "_native_slot_value_0 = _slot_value(instance, item)",
        "_native_slot_value_3 = _slot_value(instance, item)",
    )
    absent = [marker for marker in required if marker not in verified]
    if absent:
        raise RuntimeError(f"native host ABI validation failed: {absent}")
    print(
        "NORMALIZED SAFE NATIVE HOST ABI",
        len(_REPLACEMENTS),
        "VALUE LOOKUPS",
        value_lookup.replaced,
        "HOISTED SLOT CALLS",
        hoister.hoisted,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
