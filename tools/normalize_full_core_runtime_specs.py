"""Encode CALL_KW and MAKE_CLASS constants as fixed native-safe lists.

The pinned compiler infers heterogeneous tuple constants as strings when they are
read back through ``CodeObject.constants``. Keyword-call and class specs then use
``strlen`` and string indexing instead of tuple semantics. Emit fixed lists and
unpack their fields directly, matching the proven MAKE_FUNCTION normalization.

This pass runs after every text-sensitive normalization and therefore rewrites the
final Python AST rather than depending on an intermediate formatting shape.
"""
from __future__ import annotations

import ast
from pathlib import Path


FRONTEND_PATH = Path("src/portapy/core/frontend.py")
VM_PATH = Path("src/portapy/core/vm.py")


def _is_attribute(node: ast.AST, owner: str, name: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == name
        and isinstance(node.value, ast.Name)
        and node.value.id == owner
    )


def _is_self_method(node: ast.AST, name: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == name
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    )


def _assigned_name(node: ast.stmt) -> str | None:
    if not isinstance(node, ast.Assign) or len(node.targets) != 1:
        return None
    target = node.targets[0]
    return target.id if isinstance(target, ast.Name) else None


def _contains_text(node: ast.AST, text: str) -> bool:
    return any(
        isinstance(item, ast.Constant)
        and isinstance(item.value, str)
        and text in item.value
        for item in ast.walk(node)
    )


class _FrontendRewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.keyword_names = 0
        self.keyword_specs = 0
        self.class_specs = 0

    def visit_Assign(self, node: ast.Assign) -> ast.AST:
        self.generic_visit(node)
        name = _assigned_name(node)
        if (
            name == "names"
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "tuple"
            and len(node.value.args) == 1
            and isinstance(node.value.args[0], ast.Name)
            and node.value.args[0].id == "keyword_names"
        ):
            node.value = ast.Name(id="keyword_names", ctx=ast.Load())
            self.keyword_names += 1
        elif (
            name == "spec"
            and isinstance(node.value, ast.Tuple)
            and len(node.value.elts) == 4
            and ast.unparse(node.value.elts[0]) == "node.name"
            and ast.unparse(node.value.elts[1]) == "body.finish()"
            and ast.unparse(node.value.elts[2]) == "base_count"
            and ast.unparse(node.value.elts[3]) == "has_keywords"
        ):
            node.value = ast.List(elts=node.value.elts, ctx=ast.Load())
            self.class_specs += 1
        return node

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if not (
            _is_self_method(node.func, "emit")
            and len(node.args) >= 2
            and _is_attribute(node.args[0], "Op", "CALL_KW")
            and isinstance(node.args[1], ast.Call)
            and _is_self_method(node.args[1].func, "constant")
            and len(node.args[1].args) == 1
        ):
            return node
        node.args[1].args[0] = ast.List(
            elts=[
                ast.Name(id="arg_specs", ctx=ast.Load()),
                ast.Name(id="names", ctx=ast.Load()),
            ],
            ctx=ast.Load(),
        )
        self.keyword_specs += 1
        return node


def _is_opcode_branch(node: ast.If, opcode: str) -> bool:
    test = node.test
    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "op"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Is)
        and len(test.comparators) == 1
        and _is_attribute(test.comparators[0], "Op", opcode)
    )


def _annotation(name: str, type_name: str, index: int) -> ast.AnnAssign:
    return ast.AnnAssign(
        target=ast.Name(id=name, ctx=ast.Store()),
        annotation=ast.Name(id=type_name, ctx=ast.Load()),
        value=ast.Subscript(
            value=ast.Name(id="spec", ctx=ast.Load()),
            slice=ast.Constant(index),
            ctx=ast.Load(),
        ),
        simple=1,
    )


def _list_annotation(name: str, element_type: str, index: int) -> ast.AnnAssign:
    return ast.AnnAssign(
        target=ast.Name(id=name, ctx=ast.Store()),
        annotation=ast.Subscript(
            value=ast.Name(id="list", ctx=ast.Load()),
            slice=ast.Name(id=element_type, ctx=ast.Load()),
            ctx=ast.Load(),
        ),
        value=ast.Subscript(
            value=ast.Name(id="spec", ctx=ast.Load()),
            slice=ast.Constant(index),
            ctx=ast.Load(),
        ),
        simple=1,
    )


def _replace_validation_prefix(
    branch: ast.If,
    *,
    error_texts: tuple[str, ...],
    assignments: list[ast.stmt],
) -> None:
    spec_index = next(
        (index for index, statement in enumerate(branch.body) if _assigned_name(statement) == "spec"),
        -1,
    )
    if spec_index < 0:
        raise RuntimeError("native runtime spec branch has no spec assignment")
    matched = [
        index
        for index, statement in enumerate(branch.body)
        if any(_contains_text(statement, text) for text in error_texts)
    ]
    if not matched:
        raise RuntimeError(
            f"native runtime spec branch has no validation markers: {error_texts}"
        )
    end = max(matched)
    if end <= spec_index:
        raise RuntimeError("native runtime spec validation precedes spec assignment")
    branch.body = branch.body[: spec_index + 1] + assignments + branch.body[end + 1 :]


class _VMRewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.class_specs = 0
        self.keyword_specs = 0

    def visit_If(self, node: ast.If) -> ast.AST:
        self.generic_visit(node)
        if _is_opcode_branch(node, "MAKE_CLASS"):
            _replace_validation_prefix(
                node,
                error_texts=("invalid class constant",),
                assignments=[
                    _annotation("class_name", "str", 0),
                    _annotation("body", "CodeObject", 1),
                    _annotation("base_count", "int", 2),
                    _annotation("has_keywords", "bool", 3),
                ],
            )
            self.class_specs += 1
        elif _is_opcode_branch(node, "CALL_KW"):
            _replace_validation_prefix(
                node,
                error_texts=("invalid keyword call", "invalid positional call"),
                assignments=[
                    _list_annotation("positional_spec", "bool", 0),
                    _list_annotation("names", "object", 1),
                ],
            )
            self.keyword_specs += 1
        return node


def _write_rewritten(path: Path, tree: ast.Module) -> str:
    ast.fix_missing_locations(tree)
    source = ast.unparse(tree) + "\n"
    path.write_text(source, encoding="utf-8")
    return source


def main() -> int:
    frontend_tree = ast.parse(
        FRONTEND_PATH.read_text(encoding="utf-8"),
        filename=str(FRONTEND_PATH),
    )
    frontend_rewriter = _FrontendRewrite()
    frontend_tree = frontend_rewriter.visit(frontend_tree)
    frontend_counts = (
        frontend_rewriter.keyword_names,
        frontend_rewriter.keyword_specs,
        frontend_rewriter.class_specs,
    )
    if frontend_counts != (1, 1, 1):
        raise RuntimeError(
            "native frontend runtime specs expected one keyword-name, keyword-spec, "
            f"and class-spec rewrite; found {frontend_counts}"
        )
    frontend = _write_rewritten(FRONTEND_PATH, frontend_tree)

    vm_tree = ast.parse(VM_PATH.read_text(encoding="utf-8"), filename=str(VM_PATH))
    vm_rewriter = _VMRewrite()
    vm_tree = vm_rewriter.visit(vm_tree)
    vm_counts = (vm_rewriter.keyword_specs, vm_rewriter.class_specs)
    if vm_counts != (1, 1):
        raise RuntimeError(
            "native VM runtime specs expected one keyword and one class branch; "
            f"found {vm_counts}"
        )
    vm = _write_rewritten(VM_PATH, vm_tree)

    required = (
        "self.constant([arg_specs, names])",
        "spec = [node.name, body.finish(), base_count, has_keywords]",
        "positional_spec: list[bool] = spec[0]",
        "names: list[object] = spec[1]",
        "class_name: str = spec[0]",
        "body: CodeObject = spec[1]",
        "base_count: int = spec[2]",
        "has_keywords: bool = spec[3]",
    )
    joined = frontend + vm
    missing = [marker for marker in required if marker not in joined]
    if missing:
        raise RuntimeError(f"native runtime spec validation failed: {missing}")

    forbidden = (
        "invalid keyword call",
        "invalid positional call",
        "invalid class constant",
        "self.constant((tuple(arg_specs), names))",
        "spec = (node.name, body.finish(), base_count, has_keywords)",
    )
    remaining = [marker for marker in forbidden if marker in joined]
    if remaining:
        raise RuntimeError(f"unsafe native runtime specs remain: {remaining}")

    print("NORMALIZED NATIVE RUNTIME SPECS", *frontend_counts, *vm_counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
