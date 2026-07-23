"""Complete the typed-truthiness normalization across imported Runtime code."""
from __future__ import annotations

import ast
from pathlib import Path

from tools import normalize_full_core_truthiness as base


REFERENCE_PATH = Path("src/portapy/reference_api.py")
ENTRY_PATH = Path("src/portapy/native_full_reference_entry.py")


class _ReferenceRewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.count = 0

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        self.generic_visit(node)
        if node.name != "Runtime":
            return node
        method = next(
            (
                item
                for item in node.body
                if isinstance(item, ast.FunctionDef) and item.name == "exec_utf8"
            ),
            None,
        )
        if method is None:
            raise RuntimeError("reference Runtime.exec_utf8 is missing")
        for statement in ast.walk(method):
            if not isinstance(statement, ast.Assign):
                continue
            call = statement.value
            if not (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "compile_source"
            ):
                continue
            call.args = [
                ast.Name(id="source", ctx=ast.Load()),
                ast.Name(id="filename", ctx=ast.Load()),
                ast.Constant("exec"),
                ast.Call(
                    func=ast.Name(id="getattr", ctx=ast.Load()),
                    args=[
                        ast.Name(id="self", ctx=ast.Load()),
                        ast.Constant("_native_kind_hints"),
                        ast.Dict(keys=[], values=[]),
                    ],
                    keywords=[],
                ),
            ]
            call.keywords = []
            self.count += 1
        return node


def _normalize_reference() -> int:
    module = ast.parse(REFERENCE_PATH.read_text(encoding="utf-8"))
    rewriter = _ReferenceRewrite()
    module = rewriter.visit(module)
    if rewriter.count != 1:
        raise RuntimeError(
            f"reference Runtime truth hints expected 1 compile call, found {rewriter.count}"
        )
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    REFERENCE_PATH.write_text(source, encoding="utf-8")
    expected = "compile_source(source, filename, 'exec', getattr(self, '_native_kind_hints', {}))"
    if expected not in source:
        raise RuntimeError("reference Runtime compile kind hints were not installed")
    return rewriter.count


class _EntryRewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.kind_sync_count = 0
        self.exec_order_count = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.generic_visit(node)
        if node.name == "_native_set_global_kind":
            node.body.extend(
                ast.parse(
                    """
instance = _runtime(runtime)
if instance is not None:
    hints = getattr(instance, "_native_kind_hints", None)
    if hints is None:
        hints = {}
        instance._native_kind_hints = hints
    hints[name] = kind
"""
                ).body
            )
            self.kind_sync_count += 1
        if node.name == "_portapy_exec_span_impl":
            record_index = next(
                (
                    index
                    for index, statement in enumerate(node.body)
                    if isinstance(statement, ast.Expr)
                    and isinstance(statement.value, ast.Call)
                    and isinstance(statement.value.func, ast.Name)
                    and statement.value.func.id == "_native_record_source_kinds"
                ),
                -1,
            )
            status_index = next(
                (
                    index
                    for index, statement in enumerate(node.body)
                    if isinstance(statement, ast.Assign)
                    and isinstance(statement.value, ast.Call)
                    and isinstance(statement.value.func, ast.Attribute)
                    and statement.value.func.attr == "exec_utf8"
                ),
                -1,
            )
            if record_index < 0 or status_index < 0:
                raise RuntimeError("native exec kind-recording shape changed")
            record = node.body.pop(record_index)
            if record_index < status_index:
                status_index -= 1
            node.body.insert(status_index, record)
            self.exec_order_count += 1
        return node


def _normalize_entry() -> tuple[int, int]:
    module = ast.parse(ENTRY_PATH.read_text(encoding="utf-8"))
    rewriter = _EntryRewrite()
    module = rewriter.visit(module)
    actual = (rewriter.kind_sync_count, rewriter.exec_order_count)
    if actual != (1, 1):
        raise RuntimeError(
            f"native truth-hint entry rewrite expected (1, 1), found {actual}"
        )
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    ENTRY_PATH.write_text(source, encoding="utf-8")
    set_kind = source.find("def _native_set_global_kind")
    runtime_sync = source.find("instance = _runtime(runtime)", set_kind)
    if set_kind < 0 or runtime_sync < set_kind:
        raise RuntimeError("native global kind hints were not synchronized")
    exec_start = source.find("def _portapy_exec_span_impl")
    record = source.find("_native_record_source_kinds(runtime, source_text)", exec_start)
    execute = source.find("status = instance.exec_utf8(source_text)", exec_start)
    if exec_start < 0 or record < exec_start or execute < exec_start or record > execute:
        raise RuntimeError("native source kinds are not recorded before compilation")
    return actual


def main() -> int:
    bytecode_count = base._normalize_bytecode()
    truth_count, assignment_count, constructor_count = base._normalize_frontend()
    vm_count = base._normalize_vm()
    reference_count = _normalize_reference()
    sync_count, order_count = _normalize_entry()
    print(
        "NORMALIZED NATIVE TRUTHINESS",
        bytecode_count,
        truth_count,
        assignment_count,
        constructor_count,
        vm_count,
        reference_count,
        sync_count,
        order_count,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
