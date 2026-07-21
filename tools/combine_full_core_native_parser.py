"""Embed the generated private parser runtime into the native AST bridge.

The pinned whole-program compiler cannot construct or call imported classes and
functions reliably. The vendor pass gives every compiler-parser definition a
private ``_npr_`` name; this pass places those definitions and the AST adapter
in one module so every parser call is local and collision-free.
"""
from __future__ import annotations

import ast
from pathlib import Path

from asmpython._compiler.lexer import Lexer as HostLexer
from asmpython._compiler.parser import Parser as HostParser


CORE = Path("src/portapy/core")
RUNTIME_PATH = CORE / "native_parser_runtime.py"
NATIVE_AST_PATH = CORE / "native_ast.py"


def _strip_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        return body[1:]
    return body


def _assignment_target(node: ast.stmt) -> ast.expr | None:
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        return node.targets[0]
    if isinstance(node, ast.AnnAssign):
        return node.target
    return None


def _prepare_runtime(module: ast.Module) -> list[ast.stmt]:
    output: list[ast.stmt] = []
    removed_exception_table = 0
    removed_statement_alias = 0
    stubbed_closure_scan = 0

    for node in _strip_docstring(module.body):
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            continue
        target = _assignment_target(node)
        if isinstance(target, ast.Name):
            if target.id == "_npr_errors__PYTHON_EXCEPTION_NAME":
                node.value = ast.Dict(keys=[], values=[])
                if isinstance(node, ast.AnnAssign):
                    node.annotation = ast.parse("dict[str, str]", mode="eval").body
                removed_exception_table += 1
            if target.id == "_npr_ast_nodes_Stmt":
                removed_statement_alias += 1
                continue
        if isinstance(node, ast.ClassDef) and node.name == "_npr_parser_Parser":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "_find_free_vars":
                    item.body = ast.parse("return [], []").body
                    stubbed_closure_scan += 1
        output.append(node)

    if removed_exception_table != 1:
        raise RuntimeError(
            "private parser exception table: expected 1, "
            f"found {removed_exception_table}"
        )
    if removed_statement_alias not in (0, 1):
        raise RuntimeError(
            "private parser statement alias: expected at most 1, "
            f"found {removed_statement_alias}"
        )
    if stubbed_closure_scan != 1:
        raise RuntimeError(
            "private parser closure scan: expected 1, "
            f"found {stubbed_closure_scan}"
        )
    print("PREPARED EMBEDDED PARSER RUNTIME", len(output))
    return output


def _rename_ast_arg_class(module: ast.Module) -> None:
    class_count = 0
    call_count = 0

    class _AnnotationRenamer(ast.NodeTransformer):
        def visit_Name(self, node: ast.Name) -> ast.AST:
            if node.id == "arg":
                return ast.copy_location(ast.Name(id="AstArg", ctx=node.ctx), node)
            return node

    renamer = _AnnotationRenamer()
    for node in ast.walk(module):
        if isinstance(node, ast.ClassDef) and node.name == "arg":
            node.name = "AstArg"
            class_count += 1
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "arg"
        ):
            node.func.id = "AstArg"
            call_count += 1

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments = [
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
            ]
            if node.args.vararg is not None:
                arguments.append(node.args.vararg)
            if node.args.kwarg is not None:
                arguments.append(node.args.kwarg)
            for argument in arguments:
                if argument.annotation is not None:
                    argument.annotation = renamer.visit(argument.annotation)
            if node.returns is not None:
                node.returns = renamer.visit(node.returns)
        elif isinstance(node, ast.AnnAssign):
            node.annotation = renamer.visit(node.annotation)

    if class_count != 1 or call_count < 1:
        raise RuntimeError(
            "native AST arg rename failed: "
            f"classes={class_count}, calls={call_count}"
        )
    print("RENAMED NATIVE AST ARG CLASS", class_count, call_count)


def _prepare_bridge(module: ast.Module) -> list[ast.stmt]:
    _rename_ast_arg_class(module)
    parse_functions = [
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "parse"
    ]
    if len(parse_functions) != 1:
        raise RuntimeError(
            f"native AST parse function: expected 1, found {len(parse_functions)}"
        )
    function = parse_functions[0]

    first_index = -1
    parsed_index = -1
    for index, statement in enumerate(function.body):
        target = _assignment_target(statement)
        if not isinstance(target, ast.Name):
            continue
        if first_index < 0 and target.id in {"lexer", "parsed"}:
            first_index = index
        if target.id == "parsed":
            parsed_index = index
            break
    if first_index < 0 or parsed_index < first_index:
        raise RuntimeError("native AST parse bootstrap has an unexpected shape")
    function.body[first_index:parsed_index + 1] = ast.parse(
        "lexer = _npr_lexer_Lexer(source)\n"
        "tokens = lexer.tokenize()\n"
        "parser = _npr_parser_Parser(tokens)\n"
        "parsed = parser.parse()\n"
    ).body

    top_rewrites = 0
    for statement in function.body:
        target = _assignment_target(statement)
        if isinstance(target, ast.Name) and target.id == "top":
            statement.value = ast.Attribute(
                value=ast.Name(id="parsed", ctx=ast.Load()),
                attr="body",
                ctx=ast.Load(),
            )
            top_rewrites += 1
    if top_rewrites != 1:
        raise RuntimeError(
            f"native AST parsed-body copy: expected 1, found {top_rewrites}"
        )

    output: list[ast.stmt] = []
    removed_runtime_import = 0
    for node in _strip_docstring(module.body):
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            continue
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "native_parser_runtime"
        ):
            removed_runtime_import += 1
            continue
        output.append(node)
    if removed_runtime_import != 1:
        raise RuntimeError(
            "private parser bridge import: expected 1, "
            f"found {removed_runtime_import}"
        )
    print("PREPARED EMBEDDED NATIVE AST", len(output))
    return output


def main() -> int:
    runtime = ast.parse(RUNTIME_PATH.read_text(encoding="utf-8"))
    bridge = ast.parse(NATIVE_AST_PATH.read_text(encoding="utf-8"))
    combined = ast.Module(
        body=[*_prepare_runtime(runtime), *_prepare_bridge(bridge)],
        type_ignores=[],
    )
    ast.fix_missing_locations(combined)
    source = (
        '"""Standalone AST and private parser runtime for the native build."""\n'
        "from __future__ import annotations\n\n"
        + ast.unparse(combined)
        + "\n"
    )
    HostParser(HostLexer(source).tokenize()).parse()
    NATIVE_AST_PATH.write_text(source, encoding="utf-8")
    print("COMBINED PRIVATE NATIVE PARSER", len(combined.body))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
