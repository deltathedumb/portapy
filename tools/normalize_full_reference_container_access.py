"""Give opaque native containers statically typed length accessors.

The reference ABI deliberately unboxes values as ``object``.  Without a typed
boundary the pinned compiler lowers ``len(target)`` to ``strlen``, even when
the runtime value is a list, tuple, or dictionary.  Route only the public
container ABI length checks through typed helpers so native sequence metadata
is read instead of scanning arbitrary memory as a C string.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/native_full_reference_entry.py")

_HELPERS = '''
def _native_sequence_size(values: list[object]) -> int:
    return len(values)


def _native_dict_size(values: dict[str, object]) -> int:
    return len(values)
'''

_REPLACEMENTS = {
    "_portapy_tuple_set_item_impl": ("target.items", "_native_sequence_size"),
    "_portapy_tuple_get_size_impl": ("target", "_native_sequence_size"),
    "_portapy_tuple_get_item_impl": ("target", "_native_sequence_size"),
    "_portapy_dict_get_size_impl": ("target", "_native_dict_size"),
    "_portapy_list_get_size_impl": ("target", "_native_sequence_size"),
    "_portapy_list_get_item_impl": ("target", "_native_sequence_size"),
    "_portapy_list_set_item_impl": ("values", "_native_sequence_size"),
}


class _Rewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.function = ""
        self.replaced = {name: 0 for name in _REPLACEMENTS}

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        previous = self.function
        self.function = node.name
        self.generic_visit(node)
        self.function = previous
        return node

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        replacement = _REPLACEMENTS.get(self.function)
        if replacement is None:
            return node
        expression, helper = replacement
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "len"
            and len(node.args) == 1
            and not node.keywords
            and ast.unparse(node.args[0]) == expression
        ):
            self.replaced[self.function] += 1
            return ast.copy_location(
                ast.Call(
                    func=ast.Name(id=helper, ctx=ast.Load()),
                    args=node.args,
                    keywords=[],
                ),
                node,
            )
        return node


def _function_source(module: ast.Module, name: str) -> str:
    matches = [
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {name} function, found {len(matches)}")
    return ast.unparse(matches[0])


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"), filename=str(PATH))
    existing = [
        name
        for name in ("_native_sequence_size", "_native_dict_size")
        if any(
            isinstance(node, ast.FunctionDef) and node.name == name
            for node in module.body
        )
    ]
    if existing:
        raise RuntimeError(f"native container helpers are already installed: {existing}")

    rewriter = _Rewrite()
    module = rewriter.visit(module)
    missed = {
        name: count
        for name, count in rewriter.replaced.items()
        if count != 1
    }
    if missed:
        raise RuntimeError(
            "native container normalization missed expected length calls: "
            f"{missed}"
        )

    module.body.extend(ast.parse(_HELPERS).body)
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    verified = ast.parse(source, filename=str(PATH))
    for name, (_, helper) in _REPLACEMENTS.items():
        function_source = _function_source(verified, name)
        if f"{helper}(" not in function_source or "len(" in function_source:
            raise RuntimeError(f"native container repair was lost in {name}")

    print("NORMALIZED NATIVE CONTAINER LENGTH ACCESS", len(_REPLACEMENTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
