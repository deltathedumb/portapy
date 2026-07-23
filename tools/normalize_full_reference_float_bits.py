"""Use integer bit payloads at the native binary64 ABI boundary.

The generic Runtime handle table stores Python object-shaped values through general
purpose registers. Native ``float`` parameters use XMM registers, so passing them
directly into the generic ``_store`` method loses both payload and kind metadata.
The public C ABI still accepts and returns ordinary ``double`` values; the assembly
adapter moves their IEEE-754 bits into integer registers before entering these
Python-authored implementation functions.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/native_full_reference_entry.py")

_FROM_BITS_SOURCE = '''
instance = _runtime(runtime)
if instance is None:
    _set_status(Status.INVALID_HANDLE)
    return 0
result = instance._store(bits, ValueKind.FLOAT)
_set_status(Status.OK)
return result
'''

_AS_BITS_SOURCE = '''
instance = _runtime(runtime)
if instance is None:
    _set_status(Status.INVALID_HANDLE)
    return 0
status, kind = instance.value_kind(value)
if status is not Status.OK:
    _set_status(status)
    return 0
if kind is not ValueKind.FLOAT:
    _set_status(Status.TYPE_ERROR)
    return 0
status, result = instance.unbox(value)
_set_status(status)
return result
'''


class _Rewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.replaced: set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.generic_visit(node)
        if node.name == "_portapy_value_from_f64_impl":
            if len(node.args.args) != 2:
                raise RuntimeError("native float constructor has unexpected signature")
            node.name = "_portapy_value_from_f64_bits_impl"
            node.args.args[1].arg = "bits"
            node.args.args[1].annotation = ast.Name(id="int", ctx=ast.Load())
            node.returns = ast.Name(id="int", ctx=ast.Load())
            node.body = ast.parse(_FROM_BITS_SOURCE).body
            self.replaced.add("from")
        elif node.name == "_portapy_value_as_f64_impl":
            if len(node.args.args) != 2:
                raise RuntimeError("native float conversion has unexpected signature")
            node.name = "_portapy_value_as_f64_bits_impl"
            node.returns = ast.Name(id="int", ctx=ast.Load())
            node.body = ast.parse(_AS_BITS_SOURCE).body
            self.replaced.add("as")
        return node


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    rewriter = _Rewrite()
    module = rewriter.visit(module)
    if rewriter.replaced != {"from", "as"}:
        raise RuntimeError(
            "native float-bit normalization expected constructor and conversion; "
            f"replaced={sorted(rewriter.replaced)}"
        )
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    verified = ast.parse(source)
    definitions = {
        node.name: node
        for node in verified.body
        if isinstance(node, ast.FunctionDef)
    }
    stale = {
        "_portapy_value_from_f64_impl",
        "_portapy_value_as_f64_impl",
    } & definitions.keys()
    from_text = ast.unparse(definitions["_portapy_value_from_f64_bits_impl"])
    as_text = ast.unparse(definitions["_portapy_value_as_f64_bits_impl"])
    ready = (
        not stale
        and "instance._store(bits, ValueKind.FLOAT)" in from_text
        and "instance.value_kind(value)" in as_text
        and "kind is not ValueKind.FLOAT" in as_text
        and "instance.unbox(value)" in as_text
    )
    if not ready:
        raise RuntimeError("native float-bit normalization validation failed")
    print("NORMALIZED NATIVE FLOAT BIT PAYLOADS", 2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
