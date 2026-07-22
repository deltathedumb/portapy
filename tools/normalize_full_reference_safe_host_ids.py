"""Make host ID getters return status errors without unsafe value dereferences."""
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
    missing = sorted(set(_REPLACEMENTS) - rewrite.replaced)
    if missing:
        raise RuntimeError(f"native host ID getters missing: {missing}")
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")
    verified = ast.unparse(ast.parse(source))
    required = (
        "_native_value_kind_code(kind) != PORTAPY_VALUE_OBJECT",
        "_native_value_kind_code(kind) != PORTAPY_VALUE_CALLABLE",
        "status, result = instance.unbox(value)",
    )
    absent = [marker for marker in required if marker not in verified]
    if absent:
        raise RuntimeError(f"native host ID getter validation failed: {absent}")
    print("NORMALIZED SAFE NATIVE HOST ID GETTERS", len(_REPLACEMENTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
