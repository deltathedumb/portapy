"""Restore nested function definitions erased by the self-hosted parser IR.

The asmpython parser lifts nested functions into ``Module.funcs`` and leaves a
position-matched ``Pass`` marker in the parent body.  PortaPy's AST bridge now
turns that marker back into a nested ``FunctionDef`` so the full frontend can
perform its own closure analysis and emit MAKE_FUNCTION with captured cells.
"""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/native_ast.py")


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    old = '''def _convert_func(node: _npr_ast_nodes_FuncDef, lifted: dict[str, _npr_ast_nodes_FuncDef]) -> FunctionDef:
    body: list[stmt] = []
    for item in node.body:
        converted = _convert_stmt(item, lifted)
        if converted is not None:
            body.append(converted)
    return FunctionDef(node.name, _convert_arguments(node, lifted), body)
'''
    new = '''def _convert_func(node: _npr_ast_nodes_FuncDef, lifted: dict[str, _npr_ast_nodes_FuncDef]) -> FunctionDef:
    body: list[stmt] = []
    for item in node.body:
        nested_function = None
        if isinstance(item, _npr_ast_nodes_Pass):
            for candidate in lifted.values():
                if (
                    candidate.is_lifted
                    and candidate.pos.line == item.pos.line
                    and candidate.pos.col == item.pos.col
                ):
                    nested_function = candidate
                    break
        if nested_function is not None:
            body.append(_convert_func(nested_function, lifted))
        else:
            converted = _convert_stmt(item, lifted)
            if converted is not None:
                body.append(converted)
    return FunctionDef(node.name, _convert_arguments(node, lifted), body)
'''
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"expected one generated function converter, found {count}"
        )
    PATH.write_text(source.replace(old, new, 1), encoding="utf-8")
    print("RESTORED LIFTED NESTED FUNCTIONS", count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
