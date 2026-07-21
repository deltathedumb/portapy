"""Make native text/bytes builders safe for the pinned compiler runtime.

Native local empty lists expose a sentinel slot in the pinned compiler runtime, so
``len([])`` is not a safe byte cursor. Builders instead append to one module-owned
byte arena and retain a start/size pair. Materialization uses a one-item seed list,
which avoids both indexed writes and the empty-list sentinel while preserving every
byte exactly.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/native_full_reference_entry.py")

_STORAGE_SOURCE = "_native_byte_data: list[int] = [0]\n"

_BUILDER_INIT = '''
self.kind = kind
self.size = size
self.start = len(_native_byte_data)
self.written = 0
'''

_DATA_BYTES = '''
if isinstance(value, _DataBuilder):
    if value.written != value.size:
        raise TypeError("data builder is incomplete")
    if value.size == 0:
        return b""
    data: list[int] = [_native_byte_data[value.start]]
    index = 1
    while index < value.size:
        data.append(_native_byte_data[value.start + index])
        index += 1
    return bytes(data)
if type(value) is str:
    return value.encode("utf-8")
if type(value) is bytes:
    return value
raise TypeError("value is not text or bytes")
'''

_SET_BYTE = '''
instance = _runtime(runtime)
if instance is None:
    return _set_status_code(PORTAPY_INVALID_HANDLE)
status, target = instance.unbox(value)
if status is not Status.OK:
    return _set_status(status)
if not isinstance(target, _DataBuilder):
    return _set_status_code(PORTAPY_TYPE_ERROR)
if index < 0 or index >= target.size or byte < 0 or byte > 255:
    return _set_status_code(PORTAPY_INVALID_ARGUMENT)
if index != target.written:
    return _set_status_code(PORTAPY_INVALID_ARGUMENT)
_native_byte_data.append(byte)
target.written += 1
return _set_status_code(PORTAPY_OK)
'''

_VALIDATE_UTF8 = '''
instance = _runtime(runtime)
if instance is None:
    return _set_status(Status.INVALID_HANDLE)
status, raw = instance.unbox(value)
if status is not Status.OK:
    return _set_status(status)
try:
    _data_bytes(raw).decode("utf-8")
except UnicodeDecodeError:
    status = instance._capture_native(
        Status.TYPE_ERROR,
        "UnicodeDecodeError",
        "invalid UTF-8",
        0,
        1,
    )
    return _set_status(status)
except TypeError:
    return _set_status(Status.TYPE_ERROR)
return _set_status(Status.OK)
'''


def _map_builder_store_kind(node: ast.FunctionDef) -> int:
    count = 0
    for item in ast.walk(node):
        if (
            isinstance(item, ast.Call)
            and isinstance(item.func, ast.Attribute)
            and isinstance(item.func.value, ast.Name)
            and item.func.value.id == "instance"
            and item.func.attr == "_store"
            and len(item.args) == 2
            and isinstance(item.args[1], ast.Name)
            and item.args[1].id == "kind"
        ):
            item.args[1] = ast.Call(
                func=ast.Name(id="_native_kind_member", ctx=ast.Load()),
                args=[ast.Name(id="kind", ctx=ast.Load())],
                keywords=[],
            )
            count += 1
    return count


class _Rewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.builder = 0
        self.functions: set[str] = set()

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        self.generic_visit(node)
        if node.name != "_DataBuilder":
            return node
        initializers = [
            item
            for item in node.body
            if isinstance(item, ast.FunctionDef) and item.name == "__init__"
        ]
        if len(initializers) != 1:
            raise RuntimeError(
                f"native data builder expected one initializer, found {len(initializers)}"
            )
        initializers[0].body = ast.parse(_BUILDER_INIT).body
        self.builder += 1
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.generic_visit(node)
        if node.name == "_data_bytes":
            node.body = ast.parse(_DATA_BYTES).body
            self.functions.add(node.name)
        elif node.name == "_portapy_value_from_data_begin_impl":
            count = _map_builder_store_kind(node)
            if count != 1:
                raise RuntimeError(
                    f"native data builder store expected one raw kind, found {count}"
                )
            self.functions.add(node.name)
        elif node.name == "_portapy_value_set_data_byte_impl":
            node.body = ast.parse(_SET_BYTE).body
            self.functions.add(node.name)
        elif node.name == "_portapy_value_validate_utf8_impl":
            node.body = ast.parse(_VALIDATE_UTF8).body
            self.functions.add(node.name)
        return node


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    if any(
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "_native_byte_data"
        for node in module.body
    ):
        raise RuntimeError("native byte arena is already installed")
    rewriter = _Rewrite()
    module = rewriter.visit(module)
    expected = {
        "_data_bytes",
        "_portapy_value_from_data_begin_impl",
        "_portapy_value_set_data_byte_impl",
        "_portapy_value_validate_utf8_impl",
    }
    if rewriter.builder != 1 or rewriter.functions != expected:
        raise RuntimeError(
            "native data-builder normalization missed expected shapes; "
            f"builder={rewriter.builder}, functions={sorted(rewriter.functions)}"
        )
    module.body.extend(ast.parse(_STORAGE_SOURCE).body)
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    verified = ast.parse(source)
    text = ast.unparse(verified)
    required = (
        "_native_byte_data: list[int] = [0]",
        "self.start = len(_native_byte_data)",
        "self.written = 0",
        "instance._store(_DataBuilder(kind, size), _native_kind_member(kind))",
        "index != target.written",
        "_native_byte_data.append(byte)",
        "data: list[int] = [_native_byte_data[value.start]]",
        "_data_bytes(raw).decode('utf-8')",
    )
    absent = [marker for marker in required if marker not in text]
    if absent:
        raise RuntimeError(f"native data-builder validation failed: {absent}")
    print("NORMALIZED NATIVE DATA BUILDERS", 5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
