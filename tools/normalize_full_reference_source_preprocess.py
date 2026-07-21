"""Install native runtime source preprocessing for compact statement suites."""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/native_full_reference_entry.py")

_HELPER_SOURCE = r'''
def _native_spaces(count: int) -> str:
    result = ""
    index = 0
    while index < count:
        result += " "
        index += 1
    return result


def _native_is_compound_prefix(text: str) -> bool:
    stripped = text.strip()
    return (
        stripped.startswith("if ")
        or stripped.startswith("elif ")
        or stripped == "else"
        or stripped.startswith("for ")
        or stripped.startswith("while ")
        or stripped == "try"
        or stripped.startswith("except")
        or stripped == "finally"
        or stripped.startswith("with ")
        or stripped.startswith("async with ")
        or stripped.startswith("async for ")
        or stripped.startswith("def ")
        or stripped.startswith("async def ")
        or stripped.startswith("class ")
        or stripped.startswith("match ")
        or stripped.startswith("case ")
    )


def _native_expand_runtime_source(source: str) -> str:
    result = ""
    quote = ""
    escaped = False
    comment = False
    depth = 0
    line_indent = 0
    line_prefix = ""
    line_start = True
    suite_indent = -1
    index = 0
    while index < len(source):
        char = source[index]
        if comment:
            result += char
            if char == "\n":
                comment = False
                line_indent = 0
                line_prefix = ""
                line_start = True
                suite_indent = -1
            index += 1
            continue
        if quote != "":
            result += char
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
        elif char == "'" or char == '"':
            quote = char
            result += char
            line_prefix += char
            line_start = False
        elif char == "#":
            comment = True
            result += char
        elif char == "(" or char == "[" or char == "{":
            depth += 1
            result += char
            line_prefix += char
            line_start = False
        elif char == ")" or char == "]" or char == "}":
            depth -= 1
            result += char
            line_prefix += char
        elif char == ":" and depth == 0:
            if _native_is_compound_prefix(line_prefix):
                suite_indent = line_indent + 4
            result += char
            line_prefix += char
            line_start = False
        elif char == ";" and depth == 0:
            indent = suite_indent if suite_indent >= 0 else line_indent
            result += "\n" + _native_spaces(indent)
            line_prefix = ""
            line_start = False
            index += 1
            while index < len(source) and (
                source[index] == " " or source[index] == "\t"
            ):
                index += 1
            continue
        elif char == "\n":
            result += char
            line_indent = 0
            line_prefix = ""
            line_start = True
            suite_indent = -1
        else:
            result += char
            if line_start and (char == " " or char == "\t"):
                line_indent += 1
            else:
                line_start = False
                line_prefix += char
        index += 1
    return result
'''


class _Rewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.replaced: set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.generic_visit(node)
        if node.name not in {"_portapy_exec_span_impl", "_portapy_eval_span_impl"}:
            return node
        count = 0
        for statement in node.body:
            if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
                continue
            target = statement.targets[0]
            if isinstance(target, ast.Name) and target.id == "source_text":
                statement.value = ast.Call(
                    func=ast.Name(id="_native_expand_runtime_source", ctx=ast.Load()),
                    args=[statement.value],
                    keywords=[],
                )
                count += 1
        if count != 1:
            raise RuntimeError(
                f"native source preprocessing for {node.name}: expected one source_text assignment, found {count}"
            )
        self.replaced.add(node.name)
        return node


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    if any(
        isinstance(node, ast.FunctionDef) and node.name == "_native_expand_runtime_source"
        for node in module.body
    ):
        raise RuntimeError("native runtime source preprocessing is already installed")
    rewriter = _Rewrite()
    module = rewriter.visit(module)
    expected = {"_portapy_exec_span_impl", "_portapy_eval_span_impl"}
    if rewriter.replaced != expected:
        raise RuntimeError(
            "native source preprocessing missed ABI functions; "
            f"replaced={sorted(rewriter.replaced)}"
        )
    module.body.extend(ast.parse(_HELPER_SOURCE).body)
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")
    if source.count("_native_expand_runtime_source(source[0:source_size])") != 2:
        raise RuntimeError("native runtime source preprocessing validation failed")
    print("NORMALIZED NATIVE RUNTIME SOURCE", len(expected))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
