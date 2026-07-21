"""Vendor the pinned asmpython parser into PortaPy's native build graph.

The whole-program backend flattens imported definitions, so raw compiler-module
names collide with PortaPy's AST/VM classes. This generator prefixes every
parser definition, rewrites internal references, and adapts ``native_ast`` to
use direct imports from the generated private runtime module.
"""
from __future__ import annotations

import ast
from pathlib import Path

import asmpython._compiler as compiler_package
from asmpython._compiler.lexer import Lexer as HostLexer
from asmpython._compiler.parser import Parser as HostParser


MODULES = ("errors", "ast_nodes", "extensions", "lexer", "parser")
CORE = Path("src/portapy/core")
RUNTIME_PATH = CORE / "native_parser_runtime.py"
NATIVE_AST_PATH = CORE / "native_ast.py"


def _targets(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        result: list[str] = []
        for item in node.elts:
            result.extend(_targets(item))
        return result
    return []


def _definition_maps(parsed: dict[str, ast.Module]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for module_name, module in parsed.items():
        names: set[str] = set()
        for node in module.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    names.update(_targets(target))
            elif isinstance(node, ast.AnnAssign):
                names.update(_targets(node.target))
        result[module_name] = {
            name: f"_npr_{module_name}_{name}"
            for name in names
            if name != "__all__"
        }
    return result


class _NamespaceModule(ast.NodeTransformer):
    def __init__(
        self,
        module_name: str,
        parsed: dict[str, ast.Module],
        names: dict[str, dict[str, str]],
    ) -> None:
        self.module_name = module_name
        self.local = names[module_name]
        self.names = names
        self.imported: dict[str, str] = {}
        self.module_aliases: dict[str, str] = {}

        for node in parsed[module_name].body:
            if not isinstance(node, ast.ImportFrom) or not node.level:
                continue
            target = node.module
            if target is None:
                for item in node.names:
                    if item.name in names:
                        self.module_aliases[item.asname or item.name] = item.name
            elif target in names:
                for item in node.names:
                    if item.name == "*":
                        continue
                    self.imported[item.asname or item.name] = names[target].get(
                        item.name,
                        item.name,
                    )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.AST | None:
        if node.module == "__future__":
            return None
        if node.module == "typing":
            kept = [item for item in node.names if item.name != "Optional"]
            if not kept:
                return None
            node.names = kept
            return node
        if node.level:
            return None
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        node.name = self.local.get(node.name, node.name)
        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        node.name = self.local.get(node.name, node.name)
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        node.name = self.local.get(node.name, node.name)
        self.generic_visit(node)
        return node

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id == "Optional":
            return ast.copy_location(ast.Name(id="object", ctx=node.ctx), node)
        renamed = self.local.get(node.id, self.imported.get(node.id, node.id))
        if renamed != node.id:
            return ast.copy_location(ast.Name(id=renamed, ctx=node.ctx), node)
        return node

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        node = self.generic_visit(node)
        if isinstance(node.value, ast.Name):
            target = self.module_aliases.get(node.value.id)
            if target is not None:
                renamed = self.names[target].get(node.attr)
                if renamed is not None:
                    return ast.copy_location(
                        ast.Name(id=renamed, ctx=node.ctx),
                        node,
                    )
        return node

    def visit_Subscript(self, node: ast.Subscript) -> ast.AST:
        node = self.generic_visit(node)
        if isinstance(node.value, ast.Name) and node.value.id == "object":
            return ast.copy_location(ast.Name(id="object", ctx=ast.Load()), node)
        return node


class _AdaptNativeAst(ast.NodeTransformer):
    def __init__(self, names: dict[str, dict[str, str]]) -> None:
        self.names = names

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.AST | None:
        if node.module and node.module.startswith("asmpython._compiler"):
            return None
        return node

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        node = self.generic_visit(node)
        if isinstance(node.value, ast.Name) and node.value.id == "A":
            renamed = self.names["ast_nodes"].get(node.attr)
            if renamed is not None:
                return ast.copy_location(ast.Name(id=renamed, ctx=node.ctx), node)
        return node


def _rename_ast_arg_class(module: ast.Module) -> None:
    class_count = 0
    call_count = 0

    class _AnnotationRenamer(ast.NodeTransformer):
        def visit_Name(self, node: ast.Name) -> ast.AST:
            if node.id == "arg":
                return ast.copy_location(ast.Name(id="AstArg", ctx=node.ctx), node)
            return node

    annotation_renamer = _AnnotationRenamer()
    for node in ast.walk(module):
        if isinstance(node, ast.ClassDef) and node.name == "arg":
            node.name = "AstArg"
            class_count += 1
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "arg":
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
                    argument.annotation = annotation_renamer.visit(argument.annotation)
            if node.returns is not None:
                node.returns = annotation_renamer.visit(node.returns)
        elif isinstance(node, ast.AnnAssign):
            node.annotation = annotation_renamer.visit(node.annotation)

    if class_count != 1:
        raise RuntimeError(f"native AST arg class: expected 1, found {class_count}")
    if call_count < 1:
        raise RuntimeError("native AST arg constructor calls were not found")
    print("RENAMED NATIVE AST ARG CLASS", class_count, call_count)


def _expand_parser_bootstrap(
    module: ast.Module,
    lexer_name: str,
    parser_name: str,
) -> None:
    matches = [
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "parse"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"native AST parse function: expected 1, found {len(matches)}")
    function = matches[0]
    if not function.body:
        raise RuntimeError("native AST parse function has no body")
    first = function.body[0]
    if not (
        isinstance(first, ast.Assign)
        and len(first.targets) == 1
        and isinstance(first.targets[0], ast.Name)
        and first.targets[0].id == "parsed"
    ):
        raise RuntimeError("native AST parse bootstrap has an unexpected shape")
    bootstrap = ast.parse(
        f"lexer = {lexer_name}(source)\n"
        "tokens = lexer.tokenize()\n"
        f"parser = {parser_name}(tokens)\n"
        "parsed = parser.parse()\n"
    ).body
    function.body[:1] = bootstrap
    print("EXPANDED NATIVE PARSER BOOTSTRAP", 1)


def _remove_integer_exception_table(
    module: ast.Module,
    exception_table_name: str,
) -> None:
    matches = 0
    for node in module.body:
        target: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        elif isinstance(node, ast.AnnAssign):
            target = node.target
        if isinstance(target, ast.Name) and target.id == exception_table_name:
            node.value = ast.Dict(keys=[], values=[])
            if isinstance(node, ast.AnnAssign):
                node.annotation = ast.parse("dict[str, str]", mode="eval").body
            matches += 1
    if matches != 1:
        raise RuntimeError(
            f"parser exception-name table: expected 1, found {matches}"
        )
    print("REMOVED INTEGER PARSER EXCEPTION TABLE", matches)


def _strip_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        return body[1:]
    return body


def vendor_native_parser() -> tuple[int, int]:
    source_root = Path(compiler_package.__file__).resolve().parent
    parsed = {
        name: ast.parse((source_root / f"{name}.py").read_text(encoding="utf-8"))
        for name in MODULES
    }
    names = _definition_maps(parsed)

    runtime_body: list[ast.stmt] = []
    for module_name in MODULES:
        transformed = _NamespaceModule(module_name, parsed, names).visit(
            parsed[module_name]
        )
        ast.fix_missing_locations(transformed)
        runtime_body.extend(_strip_docstring(transformed.body))

    runtime = ast.Module(body=runtime_body, type_ignores=[])
    _remove_integer_exception_table(
        runtime,
        names["errors"]["_PYTHON_EXCEPTION_NAME"],
    )
    ast.fix_missing_locations(runtime)
    RUNTIME_PATH.write_text(
        "from __future__ import annotations\n\n" + ast.unparse(runtime) + "\n",
        encoding="utf-8",
    )

    native_ast = ast.parse(NATIVE_AST_PATH.read_text(encoding="utf-8"))
    ast_node_names = sorted(
        {
            node.attr
            for node in ast.walk(native_ast)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "A"
        }
    )
    native_ast = _AdaptNativeAst(names).visit(native_ast)
    _rename_ast_arg_class(native_ast)
    _expand_parser_bootstrap(
        native_ast,
        names["lexer"]["Lexer"],
        names["parser"]["Parser"],
    )
    ast.fix_missing_locations(native_ast)

    imports = [
        ast.alias(name=names["lexer"]["Lexer"], asname=None),
        ast.alias(name=names["parser"]["Parser"], asname=None),
    ]
    for name in ast_node_names:
        renamed = names["ast_nodes"].get(name)
        if renamed is not None:
            imports.append(ast.alias(name=renamed, asname=None))
    direct_import = ast.ImportFrom(
        module="native_parser_runtime",
        names=imports,
        level=1,
    )

    insert_at = 0
    for index, node in enumerate(native_ast.body):
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            insert_at = index + 1
    native_ast.body.insert(insert_at, direct_import)
    ast.fix_missing_locations(native_ast)
    NATIVE_AST_PATH.write_text(ast.unparse(native_ast) + "\n", encoding="utf-8")

    for path in (RUNTIME_PATH, NATIVE_AST_PATH):
        HostParser(HostLexer(path.read_text(encoding="utf-8")).tokenize()).parse()

    definition_count = sum(len(mapping) for mapping in names.values())
    print("VENDORED PRIVATE NATIVE PARSER", definition_count, len(ast_node_names))
    return definition_count, len(ast_node_names)


def main() -> int:
    vendor_native_parser()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
