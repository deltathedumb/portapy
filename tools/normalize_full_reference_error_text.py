"""Expose native structured-error text without allocating encoded bytes.

The pinned compiler runtime can safely access the native ``ErrorInfo`` fields, but
its generic ``str.encode`` lowering dereferences an invalid runtime object. The C
adapter already requests text one byte at a time, so size and byte helpers operate
directly on the ASCII error strings produced by the native capture paths.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/native_full_reference_entry.py")

_TYPE_SIZE = '''
instance = _runtime(runtime)
if instance is None:
    _set_status_code(PORTAPY_INVALID_HANDLE)
    return 0
error = instance.last_error()
_set_status_code(PORTAPY_OK)
if error is None:
    return 0
return len(error.type_name)
'''

_MESSAGE_SIZE = '''
instance = _runtime(runtime)
if instance is None:
    _set_status_code(PORTAPY_INVALID_HANDLE)
    return 0
error = instance.last_error()
_set_status_code(PORTAPY_OK)
if error is None:
    return 0
return len(error.message)
'''

_TYPE_BYTE = '''
instance = _runtime(runtime)
if instance is None:
    _set_status_code(PORTAPY_INVALID_HANDLE)
    return 0
error = instance.last_error()
if error is None or index < 0 or index >= len(error.type_name):
    _set_status_code(PORTAPY_INVALID_ARGUMENT)
    return 0
_set_status_code(PORTAPY_OK)
return ord(error.type_name[index])
'''

_MESSAGE_BYTE = '''
instance = _runtime(runtime)
if instance is None:
    _set_status_code(PORTAPY_INVALID_HANDLE)
    return 0
error = instance.last_error()
if error is None or index < 0 or index >= len(error.message):
    _set_status_code(PORTAPY_INVALID_ARGUMENT)
    return 0
_set_status_code(PORTAPY_OK)
return ord(error.message[index])
'''

_REPLACEMENTS = {
    "_portapy_error_type_size_impl": _TYPE_SIZE,
    "_portapy_error_message_size_impl": _MESSAGE_SIZE,
    "_portapy_error_type_byte_impl": _TYPE_BYTE,
    "_portapy_error_message_byte_impl": _MESSAGE_BYTE,
}


class _Rewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.replaced: set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.generic_visit(node)
        replacement = _REPLACEMENTS.get(node.name)
        if replacement is None:
            return node
        node.body = ast.parse(replacement).body
        self.replaced.add(node.name)
        return node


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    rewriter = _Rewrite()
    module = rewriter.visit(module)
    missing = sorted(set(_REPLACEMENTS) - rewriter.replaced)
    if missing:
        raise RuntimeError(f"native error text functions missing: {missing}")
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    verified = ast.parse(source)
    functions = {
        node.name: ast.unparse(node)
        for node in verified.body
        if isinstance(node, ast.FunctionDef)
        and node.name in _REPLACEMENTS
    }
    text = "\n".join(functions.values())
    required = (
        "len(error.type_name)",
        "len(error.message)",
        "ord(error.type_name[index])",
        "ord(error.message[index])",
    )
    absent = [marker for marker in required if marker not in text]
    if absent or ".encode(" in text or "_error_bytes(" in text:
        raise RuntimeError(
            f"native error text validation failed: absent={absent}"
        )
    print("NORMALIZED NATIVE ERROR TEXT", len(_REPLACEMENTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
