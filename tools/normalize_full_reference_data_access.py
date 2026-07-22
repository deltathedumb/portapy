"""Expose native string/bytes payloads without ``str.encode``.

The native runtime safely retains source-created ``str`` and ``bytes`` values, but
the pinned compiler's generic encoding path is not usable. Public size/copy helpers
therefore calculate UTF-8 widths and bytes directly from Unicode code points, while
builder and bytes payloads are read from their native storage unchanged.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/native_full_reference_entry.py")

_HELPERS = '''
def _native_utf8_width(codepoint: int) -> int:
    if codepoint < 0 or codepoint > 1114111:
        return 0
    if codepoint >= 55296 and codepoint <= 57343:
        return 0
    if codepoint <= 127:
        return 1
    if codepoint <= 2047:
        return 2
    if codepoint <= 65535:
        return 3
    return 4


def _native_data_size(value: object) -> int:
    if isinstance(value, _DataBuilder):
        if value.written != value.size:
            return -1
        return value.size
    if type(value) is bytes:
        return len(value)
    if type(value) is str:
        total = 0
        index = 0
        while index < len(value):
            width = _native_utf8_width(ord(value[index]))
            if width == 0:
                return -1
            total += width
            index += 1
        return total
    return -1


def _native_string_byte(value: str, wanted: int) -> int:
    offset = 0
    index = 0
    while index < len(value):
        codepoint = ord(value[index])
        width = _native_utf8_width(codepoint)
        if width == 0:
            return -1
        if wanted < offset + width:
            within = wanted - offset
            if width == 1:
                return codepoint
            if width == 2:
                if within == 0:
                    return 192 + codepoint // 64
                return 128 + codepoint % 64
            if width == 3:
                if within == 0:
                    return 224 + codepoint // 4096
                if within == 1:
                    return 128 + codepoint // 64 % 64
                return 128 + codepoint % 64
            if within == 0:
                return 240 + codepoint // 262144
            if within == 1:
                return 128 + codepoint // 4096 % 64
            if within == 2:
                return 128 + codepoint // 64 % 64
            return 128 + codepoint % 64
        offset += width
        index += 1
    return -1


def _native_data_byte(value: object, index: int) -> int:
    if isinstance(value, _DataBuilder):
        if value.written != value.size or index < 0 or index >= value.size:
            return -1
        return _native_byte_data[value.start + index]
    if type(value) is bytes:
        if index < 0 or index >= len(value):
            return -1
        return value[index]
    if type(value) is str:
        return _native_string_byte(value, index)
    return -1
'''

_GET_SIZE = '''
instance = _runtime(runtime)
if instance is None:
    _set_status(Status.INVALID_HANDLE)
    return 0
status, raw = instance.unbox(value)
if status is not Status.OK:
    _set_status(status)
    return 0
size = _native_data_size(raw)
if size < 0:
    _set_status(Status.TYPE_ERROR)
    return 0
_set_status(Status.OK)
return size
'''

_GET_BYTE = '''
instance = _runtime(runtime)
if instance is None:
    _set_status(Status.INVALID_HANDLE)
    return 0
status, raw = instance.unbox(value)
if status is not Status.OK:
    _set_status(status)
    return 0
size = _native_data_size(raw)
if size < 0:
    _set_status(Status.TYPE_ERROR)
    return 0
if index < 0 or index >= size:
    _set_status(Status.INVALID_ARGUMENT)
    return 0
result = _native_data_byte(raw, index)
if result < 0:
    _set_status(Status.TYPE_ERROR)
    return 0
_set_status(Status.OK)
return result
'''

_REPLACEMENTS = {
    "_portapy_value_get_size_impl": _GET_SIZE,
    "_portapy_value_get_byte_impl": _GET_BYTE,
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
    if any(
        isinstance(node, ast.FunctionDef) and node.name == "_native_data_size"
        for node in module.body
    ):
        raise RuntimeError("native data access helpers are already installed")
    rewriter = _Rewrite()
    module = rewriter.visit(module)
    missing = sorted(set(_REPLACEMENTS) - rewriter.replaced)
    if missing:
        raise RuntimeError(f"native data access functions missing: {missing}")
    module.body.extend(ast.parse(_HELPERS).body)
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    verified = ast.parse(source)
    text = ast.unparse(verified)
    required = (
        "_native_utf8_width(ord(value[index]))",
        "_native_string_byte(value, index)",
        "return value[index]",
        "size = _native_data_size(raw)",
        "result = _native_data_byte(raw, index)",
    )
    absent = [marker for marker in required if marker not in text]
    functions = "\n".join(
        ast.unparse(node)
        for node in verified.body
        if isinstance(node, ast.FunctionDef)
        and node.name in _REPLACEMENTS
    )
    if absent or ".encode(" in functions or "_data_bytes(" in functions:
        raise RuntimeError(f"native data access validation failed: absent={absent}")
    print("NORMALIZED NATIVE DATA ACCESS", len(_REPLACEMENTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
