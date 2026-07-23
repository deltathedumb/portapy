"""Lower direct ``len`` calls with the native value-kind hint.

The pinned compiler specializes ``len(value: object)`` as ``strlen``. That works
for text, but it dereferences tuple/list/dict/bytes values as C strings and crashes
for empty containers. Direct builtin calls already pass through the frontend, where
PortaPy's truthiness pipeline can classify literals and tracked names. Thread that
kind into a two-argument native builtin and use statically typed aliases for the
actual string/container length operations.
"""
from __future__ import annotations

import ast
from pathlib import Path


LOADER_PATH = Path("src/portapy/core/loader.py")
FRONTEND_PATH = Path("src/portapy/core/frontend.py")


_LEN_FUNCTION = '''def _builtin_len(value: object, kind: int = 0) -> int:
    if kind == 4:
        text_value: str = value
        return len(text_value)
    if kind == 5 or kind == 6:
        container_value: list = value
        return len(container_value)
    raise TypeError("object has no len")
'''


_SPECIAL_CALL = '''if (
    isinstance(node, ast.Call)
    and isinstance(node.func, ast.Name)
    and node.func.id == "len"
    and node.func.id not in self.bound_names
    and len(node.args) == 1
    and not isinstance(node.args[0], ast.Starred)
    and not node.keywords
):
    self.expr(node.func)
    self.expr(node.args[0])
    self.emit(Op.LOAD_CONST, self.constant(self.expression_kind(node.args[0])))
    self.emit(Op.CALL, 2)
'''


def _normalize_loader() -> int:
    module = ast.parse(
        LOADER_PATH.read_text(encoding="utf-8"),
        filename=str(LOADER_PATH),
    )
    matches = [
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "_builtin_len"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"native len builtin expected once, found {len(matches)}")
    function = matches[0]
    original = ast.unparse(function)
    if "return len(value)" not in original or len(function.args.args) != 1:
        raise RuntimeError("native len builtin no longer has the unsafe object shape")

    replacement = ast.parse(_LEN_FUNCTION).body[0]
    replacement.decorator_list = function.decorator_list
    module.body[module.body.index(function)] = replacement
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    LOADER_PATH.write_text(source, encoding="utf-8")

    required = (
        "def _builtin_len(value: object, kind: int=0) -> int:",
        "text_value: str = value",
        "container_value: list = value",
        "kind == 5 or kind == 6",
        "raise TypeError('object has no len')",
    )
    missing = [marker for marker in required if marker not in source]
    if missing or "def _builtin_len(value: object)" in source:
        raise RuntimeError(f"native len builtin repair was lost: {missing}")
    return 1


def _is_simple_call_branch(node: ast.If) -> bool:
    text = ast.unparse(node.test)
    return (
        "isinstance(node, ast.Call)" in text
        and "not node.keywords" in text
        and "all((not isinstance(arg, ast.Starred) for arg in node.args))" in text
    )


def _normalize_frontend() -> int:
    module = ast.parse(
        FRONTEND_PATH.read_text(encoding="utf-8"),
        filename=str(FRONTEND_PATH),
    )
    lowerer = next(
        (
            node
            for node in module.body
            if isinstance(node, ast.ClassDef) and node.name == "_Lowerer"
        ),
        None,
    )
    if lowerer is None:
        raise RuntimeError("native len frontend lost the _Lowerer class")
    method = next(
        (
            node
            for node in lowerer.body
            if isinstance(node, ast.FunctionDef) and node.name == "expr"
        ),
        None,
    )
    if method is None:
        raise RuntimeError("native len frontend lost _Lowerer.expr")
    branches = [node for node in ast.walk(method) if isinstance(node, ast.If) and _is_simple_call_branch(node)]
    if len(branches) != 1:
        raise RuntimeError(
            f"native len expected one simple-call branch, found {len(branches)}"
        )
    branch = branches[0]
    original = ast.If(
        test=branch.test,
        body=branch.body,
        orelse=branch.orelse,
    )
    special = ast.parse(_SPECIAL_CALL).body[0]
    branch.test = special.test
    branch.body = special.body
    branch.orelse = [original]

    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    FRONTEND_PATH.write_text(source, encoding="utf-8")
    required = (
        "node.func.id == 'len'",
        "node.func.id not in self.bound_names",
        "self.constant(self.expression_kind(node.args[0]))",
        "self.emit(Op.CALL, 2)",
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        raise RuntimeError(f"native len frontend repair was lost: {missing}")
    if source.count("self.constant(self.expression_kind(node.args[0]))") != 1:
        raise RuntimeError("native len frontend kind transport is not unique")
    return 1


def main() -> int:
    loader_count = _normalize_loader()
    frontend_count = _normalize_frontend()
    print("NORMALIZED NATIVE LEN", loader_count, frontend_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
