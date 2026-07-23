"""Use compiler-only source directives to transport cross-call truth kinds.

Passing the hint dictionary as an additional native function argument crosses a
still-opaque container calling boundary.  Instead, the ABI prepends reserved
assignments which the frontend consumes as compile-time metadata and never emits
as runtime bytecode.  This keeps the typed ``TO_BOOL`` implementation while
avoiding native object transport entirely.
"""
from __future__ import annotations

import ast
from pathlib import Path

from tools.normalize_full_core_truthiness_compiler_safe import (
    main as normalize_truthiness,
)


FRONTEND_PATH = Path("src/portapy/core/frontend.py")
REFERENCE_PATH = Path("src/portapy/reference_api.py")
ENTRY_PATH = Path("src/portapy/native_full_reference_entry.py")

_DIRECTIVE_PREFIX = "__portapy_internal_kind_"
_EVAL_MARKER = "# __portapy_eval_expression__\n"


def _directive_guard() -> ast.If:
    return ast.parse(
        f'''if (
    isinstance(statement, ast.Assign)
    and len(statement.targets) == 1
    and isinstance(statement.targets[0], ast.Name)
    and statement.targets[0].id.startswith("{_DIRECTIVE_PREFIX}")
    and isinstance(statement.value, ast.Constant)
):
    hint_name = statement.targets[0].id[len("{_DIRECTIVE_PREFIX}"):]
    lowerer.kind_hints[hint_name] = statement.value.value
    continue
'''
    ).body[0]


def _normalize_frontend() -> int:
    module = ast.parse(FRONTEND_PATH.read_text(encoding="utf-8"))
    function = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "compile_source"
    )

    if not function.args.args or function.args.args[-1].arg != "kind_hints":
        raise RuntimeError("compile_source native hint argument is missing")
    function.args.args.pop()
    if not function.args.defaults:
        raise RuntimeError("compile_source native hint default is missing")
    function.args.defaults.pop()

    removed = 0
    new_body: list[ast.stmt] = []
    for statement in function.body:
        if (
            isinstance(statement, ast.If)
            and isinstance(statement.test, ast.Compare)
            and isinstance(statement.test.left, ast.Name)
            and statement.test.left.id == "kind_hints"
        ):
            removed += 1
            continue
        new_body.append(statement)
    function.body = new_body
    if removed != 1:
        raise RuntimeError(
            f"compile_source hint dictionary bootstrap expected 1 block, found {removed}"
        )

    loops = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.For)
        and isinstance(node.target, ast.Name)
        and node.target.id == "statement"
        and isinstance(node.iter, ast.Attribute)
        and isinstance(node.iter.value, ast.Name)
        and node.iter.value.id == "module"
        and node.iter.attr == "body"
    ]
    if len(loops) != 1:
        raise RuntimeError(
            f"compile_source statement loop expected 1 match, found {len(loops)}"
        )
    loops[0].body.insert(0, _directive_guard())

    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    FRONTEND_PATH.write_text(source, encoding="utf-8")
    if "kind_hints=None" in source:
        raise RuntimeError("compile_source still accepts a native hint dictionary")
    if _DIRECTIVE_PREFIX not in source:
        raise RuntimeError("compile-time kind directives were not installed")
    return 1


class _ReferenceRewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.compile_count = 0
        self.eval_count = 0

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        self.generic_visit(node)
        if node.name != "Runtime":
            return node

        exec_method = next(
            item
            for item in node.body
            if isinstance(item, ast.FunctionDef) and item.name == "exec_utf8"
        )
        for statement in ast.walk(exec_method):
            if not isinstance(statement, ast.Assign):
                continue
            call = statement.value
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "compile_source"
            ):
                call.args = [
                    ast.Name(id="source", ctx=ast.Load()),
                    ast.Name(id="filename", ctx=ast.Load()),
                ]
                call.keywords = []
                self.compile_count += 1

        eval_method = next(
            item
            for item in node.body
            if isinstance(item, ast.FunctionDef) and item.name == "eval_utf8"
        )
        insert_at = next(
            index
            for index, statement in enumerate(eval_method.body)
            if isinstance(statement, ast.AugAssign)
            and isinstance(statement.target, ast.Attribute)
            and statement.target.attr == "_eval_counter"
        )
        setup = ast.parse(
            f'''prefix = ""
marker = {_EVAL_MARKER!r}
marker_at = expression.find(marker)
if marker_at >= 0:
    prefix = expression[0:marker_at]
    expression = expression[marker_at + len(marker):]
'''
        ).body
        eval_method.body[insert_at:insert_at] = setup

        for statement in ast.walk(eval_method):
            if not isinstance(statement, ast.Assign):
                continue
            call = statement.value
            if not (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "self"
                and call.func.attr == "exec_utf8"
                and call.args
            ):
                continue
            call.args[0] = ast.BinOp(
                left=ast.Name(id="prefix", ctx=ast.Load()),
                op=ast.Add(),
                right=call.args[0],
            )
            self.eval_count += 1
        return node


def _normalize_reference() -> tuple[int, int]:
    module = ast.parse(REFERENCE_PATH.read_text(encoding="utf-8"))
    rewriter = _ReferenceRewrite()
    module = rewriter.visit(module)
    actual = (rewriter.compile_count, rewriter.eval_count)
    if actual != (1, 1):
        raise RuntimeError(
            f"reference truth directive rewrite expected (1, 1), found {actual}"
        )
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    REFERENCE_PATH.write_text(source, encoding="utf-8")
    if "getattr(self, '_native_kind_hints'" in source:
        raise RuntimeError("reference Runtime still transports a native hint dictionary")
    if _EVAL_MARKER.strip() not in source:
        raise RuntimeError("reference eval directive marker was not installed")
    return actual


_HELPER = ast.parse(
    f'''def _native_source_with_kind_hints(runtime: int, source: str) -> str:
    result = ""
    wanted = str(runtime) + ":"
    for key, kind in _native_global_kinds.items():
        if key.startswith(wanted):
            name = key[len(wanted):]
            if _native_is_identifier(name):
                result += "{_DIRECTIVE_PREFIX}" + name + " = " + str(kind) + "\\n"
    return result + {_EVAL_MARKER!r} + source
'''
).body[0]


class _EntryRewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.kind_reset = 0
        self.exec_count = 0
        self.eval_count = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.generic_visit(node)
        if node.name == "_native_set_global_kind":
            if len(node.body) < 2:
                raise RuntimeError("native global-kind dictionary transport is missing")
            node.body = node.body[:1]
            self.kind_reset += 1
            return node

        if node.name not in {"_portapy_exec_span_impl", "_portapy_eval_span_impl"}:
            return node
        call_name = "exec_utf8" if node.name == "_portapy_exec_span_impl" else "eval_utf8"
        status_index = -1
        for index, statement in enumerate(node.body):
            if not isinstance(statement, ast.Assign):
                continue
            call = statement.value
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == call_name
                and call.args
            ):
                status_index = index
                call.args[0] = ast.Name(id="compiled_source", ctx=ast.Load())
                break
        if status_index < 0:
            raise RuntimeError(f"native {call_name} source call was not found")
        node.body.insert(
            status_index,
            ast.Assign(
                targets=[ast.Name(id="compiled_source", ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Name(id="_native_source_with_kind_hints", ctx=ast.Load()),
                    args=[
                        ast.Name(id="runtime", ctx=ast.Load()),
                        ast.Name(id="source_text", ctx=ast.Load()),
                    ],
                    keywords=[],
                ),
            ),
        )
        if call_name == "exec_utf8":
            self.exec_count += 1
        else:
            self.eval_count += 1
        return node


def _normalize_entry() -> tuple[int, int, int]:
    module = ast.parse(ENTRY_PATH.read_text(encoding="utf-8"))
    if any(
        isinstance(node, ast.FunctionDef)
        and node.name == "_native_source_with_kind_hints"
        for node in module.body
    ):
        raise RuntimeError("native source kind directive helper already exists")
    rewriter = _EntryRewrite()
    module = rewriter.visit(module)
    actual = (rewriter.kind_reset, rewriter.exec_count, rewriter.eval_count)
    if actual != (1, 1, 1):
        raise RuntimeError(
            f"native truth directive entry rewrite expected (1, 1, 1), found {actual}"
        )
    insert_at = next(
        index
        for index, node in enumerate(module.body)
        if isinstance(node, ast.FunctionDef) and node.name == "_native_expression_kind"
    )
    module.body.insert(insert_at, _HELPER)
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    ENTRY_PATH.write_text(source, encoding="utf-8")
    if "_native_kind_hints" in source:
        raise RuntimeError("native Runtime attribute hint transport survived")
    if source.count("_native_source_with_kind_hints(runtime, source_text)") != 2:
        raise RuntimeError("native source directives were not applied to exec and eval")
    return actual


def main() -> int:
    normalize_truthiness()
    frontend_count = _normalize_frontend()
    compile_count, reference_eval_count = _normalize_reference()
    reset_count, entry_exec_count, entry_eval_count = _normalize_entry()
    print(
        "NORMALIZED NATIVE TRUTH DIRECTIVES",
        frontend_count,
        compile_count,
        reference_eval_count,
        reset_count,
        entry_exec_count,
        entry_eval_count,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
