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
    ast.fix_missing_locations(native_ast)

    imports = [
        ast.alias(name=names["lexer"]["Lexer"], asname="Lexer"),
        ast.alias(name=names["parser"]["Parser"], asname="Parser"),
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
