"""Remove native VM host-introspection and container-identity hazards.

Native values are untagged pointers. Host-style ``type``/``callable`` predicates
and compiler-generated list-membership helpers can therefore reinterpret runtime
storage or reject valid native call targets. This final AST pass keeps operations
inside the native representations already established by the frontend and VM:

* iterate values directly with ``iter``;
* treat an import loader as configured whenever it is present, while preserving
  direct native loader calls;
* compare function parameter names with an explicit indexed string loop;
* remove the redundant class-keyword ``isinstance(dict)`` guard, because the
  frontend always pushes a dictionary when class keywords exist and the VM itself
  creates the empty dictionary otherwise.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/core/vm.py")
_NAME_LIST_FIELDS = {"arg_names", "posonly_names", "kwonly_names"}
_NAME_HELPER = "_full_core_native_name_in"
_NAME_HELPER_SOURCE = '''
def _full_core_native_name_in(items: list[str], wanted: str) -> bool:
    index = 0
    while index < len(items):
        if items[index] == wanted:
            return True
        index += 1
    return False
'''


def _is_attribute(node: ast.AST, owner: str, name: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == name
        and isinstance(node.value, ast.Name)
        and node.value.id == owner
    )


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


def _contains_text(node: ast.AST, text: str) -> bool:
    return any(
        isinstance(item, ast.Constant)
        and isinstance(item.value, str)
        and text in item.value
        for item in ast.walk(node)
    )


def _loader_presence_test() -> ast.Compare:
    return ast.Compare(
        left=ast.Name(id="loader", ctx=ast.Load()),
        ops=[ast.Is()],
        comparators=[ast.Constant(None)],
    )


def _target_code_name_list(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr in _NAME_LIST_FIELDS
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "code"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "target"
    )


def _name_membership_call(left: ast.expr, right: ast.expr) -> ast.Call:
    return ast.Call(
        func=ast.Name(id=_NAME_HELPER, ctx=ast.Load()),
        args=[right, left],
        keywords=[],
    )


class _ImportRewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.presence_checks = 0

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        self.generic_visit(node)
        if not isinstance(node.op, ast.Not) or not isinstance(node.operand, ast.Call):
            return node
        call = node.operand
        if (
            isinstance(call.func, ast.Name)
            and call.func.id == "callable"
            and len(call.args) == 1
            and isinstance(call.args[0], ast.Name)
            and call.args[0].id == "loader"
        ):
            self.presence_checks += 1
            return ast.copy_location(_loader_presence_test(), node)
        return node


class _Rewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.iteration = 0
        self.import_branches = 0
        self.presence_checks = 0
        self.class_guards = 0
        self.name_memberships = 0

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        self.generic_visit(node)
        if (
            len(node.ops) == 1
            and len(node.comparators) == 1
            and isinstance(node.left, ast.expr)
            and isinstance(node.comparators[0], ast.expr)
            and _target_code_name_list(node.comparators[0])
        ):
            call = _name_membership_call(node.left, node.comparators[0])
            if isinstance(node.ops[0], ast.In):
                self.name_memberships += 1
                return ast.copy_location(call, node)
            if isinstance(node.ops[0], ast.NotIn):
                self.name_memberships += 1
                return ast.copy_location(
                    ast.UnaryOp(op=ast.Not(), operand=call),
                    node,
                )
        return node

    def visit_If(self, node: ast.If) -> ast.AST:
        self.generic_visit(node)
        if _is_opcode_branch(node, "GET_ITER"):
            node.body = ast.parse(
                "value = frame.stack.pop()\n"
                "frame.stack.append(iter(value))\n"
            ).body
            self.iteration += 1
            return node
        if _is_opcode_branch(node, "MAKE_CLASS"):
            before = len(node.body)
            node.body = [
                statement
                for statement in node.body
                if not _contains_text(
                    statement,
                    "class keyword arguments must be a dict",
                )
            ]
            removed = before - len(node.body)
            if removed != 1:
                raise RuntimeError(
                    "native class keyword guard expected once, "
                    f"found {removed}"
                )
            self.class_guards += removed
        if any(
            _is_opcode_branch(node, opcode)
            for opcode in (
                "IMPORT_NAME",
                "IMPORT_FROM",
                "IMPORT_ROOT",
                "IMPORT_RELATIVE_FROM",
            )
        ):
            rewriter = _ImportRewrite()
            node.body = [rewriter.visit(statement) for statement in node.body]
            self.import_branches += 1
            self.presence_checks += rewriter.presence_checks
        return node


def _install_name_helper(tree: ast.Module) -> int:
    if any(
        isinstance(node, ast.FunctionDef) and node.name == _NAME_HELPER
        for node in tree.body
    ):
        raise RuntimeError("native name-membership helper already exists")
    tree.body.extend(ast.parse(_NAME_HELPER_SOURCE).body)
    return 1


def main() -> int:
    tree = ast.parse(PATH.read_text(encoding="utf-8"), filename=str(PATH))
    helper_count = _install_name_helper(tree)
    rewriter = _Rewrite()
    tree = rewriter.visit(tree)
    counts = (
        helper_count,
        rewriter.iteration,
        rewriter.import_branches,
        rewriter.presence_checks,
        rewriter.class_guards,
        rewriter.name_memberships,
    )
    if (
        helper_count != 1
        or rewriter.iteration != 1
        or rewriter.import_branches != 4
        or rewriter.class_guards != 1
    ):
        raise RuntimeError(
            "native runtime dispatch missed required branches; "
            f"found {counts}"
        )
    if rewriter.presence_checks < 4 or rewriter.name_memberships < 6:
        raise RuntimeError(
            "native runtime dispatch missed loader/name operations; "
            f"found {counts}"
        )

    ast.fix_missing_locations(tree)
    source = ast.unparse(tree) + "\n"
    PATH.write_text(source, encoding="utf-8")

    required = (
        "def _full_core_native_name_in(items: list[str], wanted: str) -> bool:",
        "frame.stack.append(iter(value))",
        "loader is None",
        "loader(imported)",
        "loader(top_level)",
        "_full_core_native_name_in(target.code.arg_names, name)",
    )
    missing = [marker for marker in required if marker not in source]
    forbidden = (
        'type(value).__name__ in {',
        "callable(loader)",
        "self._call(loader,",
        "class keyword arguments must be a dict",
        "name in target.code.arg_names",
        "name not in target.code.arg_names",
    )
    remaining = [marker for marker in forbidden if marker in source]
    if missing or remaining:
        raise RuntimeError(
            f"native runtime dispatch validation failed: missing={missing}, "
            f"remaining={remaining}"
        )

    print("NORMALIZED NATIVE RUNTIME DISPATCH", *counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
