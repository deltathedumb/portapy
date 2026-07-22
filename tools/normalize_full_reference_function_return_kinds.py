"""Stabilize native callable return-kind inference.

The structural expression-kind pass installs one callable return-kind ledger.
This pass makes that ledger distinguish three different states:

* no return kind has been observed yet;
* one concrete return kind has been observed;
* incompatible return kinds have been observed.

Using ``PORTAPY_VALUE_NONE`` as the initial/unknown state loses real bare-None
returns, while allowing a later return to overwrite ``OBJECT`` can accidentally
"unmix" a function after conflicting return types.  Both cases can cause the
native ABI to decode a value through the wrong getter.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/native_full_reference_entry.py")
_UNKNOWN_NAME = "_NATIVE_RETURN_KIND_UNKNOWN"
_MIXED_NAME = "_NATIVE_RETURN_KIND_MIXED"


_RETURN_KIND_BODY = '''
kind = _native_callable_return_kinds.get(
    _native_callable_key(runtime, name),
    _NATIVE_RETURN_KIND_UNKNOWN,
)
if kind < 0:
    return PORTAPY_VALUE_OBJECT
return kind
'''


_MERGE_BODY = '''
key = _native_callable_key(runtime, name)
existing = _native_callable_return_kinds.get(
    key,
    _NATIVE_RETURN_KIND_UNKNOWN,
)
if existing == _NATIVE_RETURN_KIND_MIXED:
    return
if existing == _NATIVE_RETURN_KIND_UNKNOWN:
    _native_callable_return_kinds[key] = kind
    return
if existing != kind:
    _native_callable_return_kinds[key] = _NATIVE_RETURN_KIND_MIXED
'''


class _Rewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.return_kind_rewritten = False
        self.merge_rewritten = False
        self.initializers_rewritten = 0
        self._in_callable_scanner = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        if node.name == "_native_callable_return_kind":
            node.body = ast.parse(_RETURN_KIND_BODY).body
            self.return_kind_rewritten = True
            return node
        if node.name == "_native_merge_callable_return_kind":
            node.body = ast.parse(_MERGE_BODY).body
            self.merge_rewritten = True
            return node
        previous = self._in_callable_scanner
        if node.name == "_native_record_callable_return_kinds":
            self._in_callable_scanner = True
        node = self.generic_visit(node)
        self._in_callable_scanner = previous
        return node

    def visit_Call(self, node: ast.Call) -> ast.AST:
        node = self.generic_visit(node)
        if not self._in_callable_scanner:
            return node
        if not (
            isinstance(node.func, ast.Name)
            and node.func.id == "_native_set_callable_return_kind"
            and len(node.args) == 3
            and isinstance(node.args[2], ast.Name)
            and node.args[2].id == "PORTAPY_VALUE_NONE"
        ):
            return node
        node.args[2] = ast.Name(id=_UNKNOWN_NAME, ctx=ast.Load())
        self.initializers_rewritten += 1
        return node


def _has_constant(module: ast.Module, name: str) -> bool:
    return any(
        isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
        for node in module.body
    )


def _insert_state_constants(module: ast.Module) -> None:
    if _has_constant(module, _UNKNOWN_NAME) or _has_constant(module, _MIXED_NAME):
        raise RuntimeError("native callable return-kind state constants already exist")
    insertion = next(
        (
            index
            for index, node in enumerate(module.body)
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "_native_callable_return_kinds"
        ),
        None,
    )
    if insertion is None:
        raise RuntimeError("native callable return-kind ledger is missing")
    constants = ast.parse(
        "_NATIVE_RETURN_KIND_UNKNOWN = -1\n"
        "_NATIVE_RETURN_KIND_MIXED = -2\n"
    ).body
    module.body[insertion:insertion] = constants


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    forbidden = {
        "_native_function_return_kinds",
        "_native_record_function_return_kinds",
        "_native_function_return_kind",
    }
    existing_forbidden = sorted(
        node.name
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in forbidden
    )
    if existing_forbidden:
        raise RuntimeError(
            "duplicate native return-kind tracker already installed: "
            + ", ".join(existing_forbidden)
        )

    _insert_state_constants(module)
    rewrite = _Rewrite()
    module = rewrite.visit(module)
    if not rewrite.return_kind_rewritten:
        raise RuntimeError("native callable return-kind getter is missing")
    if not rewrite.merge_rewritten:
        raise RuntimeError("native callable return-kind merger is missing")
    if rewrite.initializers_rewritten != 1:
        raise RuntimeError(
            "expected one callable unknown-state initializer, found "
            f"{rewrite.initializers_rewritten}"
        )

    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    verified = ast.unparse(ast.parse(source))
    required = (
        "_NATIVE_RETURN_KIND_UNKNOWN = -1",
        "_NATIVE_RETURN_KIND_MIXED = -2",
        "if kind < 0:",
        "if existing == _NATIVE_RETURN_KIND_MIXED:",
        "if existing == _NATIVE_RETURN_KIND_UNKNOWN:",
        "_native_set_callable_return_kind(runtime, function_name, _NATIVE_RETURN_KIND_UNKNOWN)",
    )
    missing = [marker for marker in required if marker not in verified]
    if missing:
        raise RuntimeError(
            "native callable return-kind stabilization failed: " + repr(missing)
        )
    if "_native_function_return_kinds" in verified:
        raise RuntimeError("duplicate native function return-kind ledger remains")
    print("STABILIZED NATIVE CALLABLE RETURN KINDS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
