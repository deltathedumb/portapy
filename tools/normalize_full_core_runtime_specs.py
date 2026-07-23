"""Encode CALL_KW and MAKE_CLASS constants as typed native-safe objects.

The pinned compiler cannot safely lower heterogeneous tuple/list constants. When
CALL_KW and MAKE_CLASS metadata is stored as a tuple, reads through
``CodeObject.constants`` are inferred as strings; a heterogeneous list is rejected
at compile time. Dedicated spec classes preserve the exact field types without
runtime tuple inspection or mixed-element containers.

This pass runs after every text-sensitive normalization and therefore rewrites the
final Python AST rather than depending on an intermediate formatting shape.
"""
from __future__ import annotations

import ast
from pathlib import Path


BYTECODE_PATH = Path("src/portapy/core/bytecode.py")
FRONTEND_PATH = Path("src/portapy/core/frontend.py")
VM_PATH = Path("src/portapy/core/vm.py")

_KEYWORD_SPEC = "_NativeKeywordCallSpec"
_CLASS_SPEC = "_NativeClassSpec"

_SPEC_CLASSES = '''
class _NativeKeywordCallSpec:
    def __init__(
        self,
        positional_spec: list[bool],
        names: list[object],
    ) -> None:
        self.positional_spec = positional_spec
        self.names = names


class _NativeClassSpec:
    def __init__(
        self,
        class_name: str,
        body: CodeObject,
        base_count: int,
        has_keywords: bool,
    ) -> None:
        self.class_name = class_name
        self.body = body
        self.base_count = base_count
        self.has_keywords = has_keywords
'''


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


def _add_imports(tree: ast.Module, names: tuple[str, ...]) -> int:
    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.level == 1
        and node.module == "bytecode"
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"native bytecode import expected once, found {len(matches)}"
        )
    statement = matches[0]
    existing = {alias.name for alias in statement.names}
    added = 0
    for name in names:
        if name not in existing:
            statement.names.append(ast.alias(name=name))
            added += 1
    return added


def _install_spec_classes(tree: ast.Module) -> int:
    existing = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name in {_KEYWORD_SPEC, _CLASS_SPEC}
    }
    if existing:
        raise RuntimeError(
            f"native opcode spec classes already exist: {sorted(existing)}"
        )
    classes = ast.parse(_SPEC_CLASSES).body
    tree.body.extend(classes)
    return len(classes)


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
            node.value = ast.Call(
                func=ast.Name(id=_CLASS_SPEC, ctx=ast.Load()),
                args=node.value.elts,
                keywords=[],
            )
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
        node.args[1].args[0] = ast.Call(
            func=ast.Name(id=_KEYWORD_SPEC, ctx=ast.Load()),
            args=[
                ast.Name(id="arg_specs", ctx=ast.Load()),
                ast.Name(id="names", ctx=ast.Load()),
            ],
            keywords=[],
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


def _typed_spec_assignment(type_name: str) -> ast.AnnAssign:
    return ast.AnnAssign(
        target=ast.Name(id="spec", ctx=ast.Store()),
        annotation=ast.Name(id=type_name, ctx=ast.Load()),
        value=ast.Subscript(
            value=ast.Attribute(
                value=ast.Attribute(
                    value=ast.Name(id="frame", ctx=ast.Load()),
                    attr="code",
                    ctx=ast.Load(),
                ),
                attr="constants",
                ctx=ast.Load(),
            ),
            slice=ast.Attribute(
                value=ast.Name(id="instr", ctx=ast.Load()),
                attr="arg",
                ctx=ast.Load(),
            ),
            ctx=ast.Load(),
        ),
        simple=1,
    )


def _field_assignment(name: str, field: str) -> ast.Assign:
    return ast.Assign(
        targets=[ast.Name(id=name, ctx=ast.Store())],
        value=ast.Attribute(
            value=ast.Name(id="spec", ctx=ast.Load()),
            attr=field,
            ctx=ast.Load(),
        ),
    )


def _replace_validation_prefix(
    branch: ast.If,
    *,
    error_texts: tuple[str, ...],
    replacements: list[ast.stmt],
) -> None:
    spec_index = next(
        (
            index
            for index, statement in enumerate(branch.body)
            if _assigned_name(statement) == "spec"
        ),
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
    branch.body = branch.body[:spec_index] + replacements + branch.body[end + 1 :]


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
                replacements=[
                    _typed_spec_assignment(_CLASS_SPEC),
                    _field_assignment("class_name", "class_name"),
                    _field_assignment("body", "body"),
                    _field_assignment("base_count", "base_count"),
                    _field_assignment("has_keywords", "has_keywords"),
                ],
            )
            self.class_specs += 1
        elif _is_opcode_branch(node, "CALL_KW"):
            _replace_validation_prefix(
                node,
                error_texts=("invalid keyword call", "invalid positional call"),
                replacements=[
                    _typed_spec_assignment(_KEYWORD_SPEC),
                    _field_assignment("positional_spec", "positional_spec"),
                    _field_assignment("names", "names"),
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
    bytecode_tree = ast.parse(
        BYTECODE_PATH.read_text(encoding="utf-8"),
        filename=str(BYTECODE_PATH),
    )
    installed = _install_spec_classes(bytecode_tree)
    if installed != 2:
        raise RuntimeError(f"native opcode spec class count changed: {installed}")
    bytecode = _write_rewritten(BYTECODE_PATH, bytecode_tree)

    frontend_tree = ast.parse(
        FRONTEND_PATH.read_text(encoding="utf-8"),
        filename=str(FRONTEND_PATH),
    )
    frontend_imports = _add_imports(frontend_tree, (_KEYWORD_SPEC, _CLASS_SPEC))
    frontend_rewriter = _FrontendRewrite()
    frontend_tree = frontend_rewriter.visit(frontend_tree)
    frontend_counts = (
        frontend_imports,
        frontend_rewriter.keyword_names,
        frontend_rewriter.keyword_specs,
        frontend_rewriter.class_specs,
    )
    if frontend_counts != (2, 1, 1, 1):
        raise RuntimeError(
            "native frontend runtime specs expected two imports and one of each "
            f"rewrite; found {frontend_counts}"
        )
    frontend = _write_rewritten(FRONTEND_PATH, frontend_tree)

    vm_tree = ast.parse(VM_PATH.read_text(encoding="utf-8"), filename=str(VM_PATH))
    vm_imports = _add_imports(vm_tree, (_KEYWORD_SPEC, _CLASS_SPEC))
    vm_rewriter = _VMRewrite()
    vm_tree = vm_rewriter.visit(vm_tree)
    vm_counts = (vm_imports, vm_rewriter.keyword_specs, vm_rewriter.class_specs)
    if vm_counts != (2, 1, 1):
        raise RuntimeError(
            "native VM runtime specs expected two imports and one keyword/class "
            f"branch; found {vm_counts}"
        )
    vm = _write_rewritten(VM_PATH, vm_tree)

    joined = bytecode + frontend + vm
    required = (
        "class _NativeKeywordCallSpec:",
        "class _NativeClassSpec:",
        "_NativeKeywordCallSpec(arg_specs, names)",
        "_NativeClassSpec(node.name, body.finish(), base_count, has_keywords)",
        "spec: _NativeKeywordCallSpec = frame.code.constants[instr.arg]",
        "positional_spec = spec.positional_spec",
        "names = spec.names",
        "spec: _NativeClassSpec = frame.code.constants[instr.arg]",
        "class_name = spec.class_name",
        "body = spec.body",
        "base_count = spec.base_count",
        "has_keywords = spec.has_keywords",
    )
    missing = [marker for marker in required if marker not in joined]
    if missing:
        raise RuntimeError(f"native runtime spec validation failed: {missing}")

    forbidden = (
        "invalid keyword call",
        "invalid positional call",
        "invalid class constant",
        "self.constant((tuple(arg_specs), names))",
        "spec = (node.name, body.finish(), base_count, has_keywords)",
        "[node.name, body.finish(), base_count, has_keywords]",
    )
    remaining = [marker for marker in forbidden if marker in joined]
    if remaining:
        raise RuntimeError(f"unsafe native runtime specs remain: {remaining}")

    print(
        "NORMALIZED NATIVE RUNTIME SPECS",
        installed,
        *frontend_counts,
        *vm_counts,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
