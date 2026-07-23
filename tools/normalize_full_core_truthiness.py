"""Install kind-aware truth-value lowering in the full native runtime.

Native PortaPy values intentionally use compact raw representations.  A raw
pointer is sufficient for ordinary object transport, but generic native
``bool(value)`` cannot distinguish an empty string/container from a non-empty
one.  The ABI already maintains source-derived value-kind hints; this pass
threads those hints into the frontend and emits one typed ``TO_BOOL`` opcode at
all user-code truth-test sites.
"""
from __future__ import annotations

import ast
from pathlib import Path


BYTECODE_PATH = Path("src/portapy/core/bytecode.py")
FRONTEND_PATH = Path("src/portapy/core/frontend.py")
VM_PATH = Path("src/portapy/core/vm.py")
ENTRY_PATH = Path("src/portapy/native_full_reference_entry.py")

TRUTH_UNKNOWN = 0
TRUTH_BOOL = 1
TRUTH_INT = 2
TRUTH_FLOAT = 3
TRUTH_STRING = 4
TRUTH_BYTES = 5
TRUTH_CONTAINER = 6
TRUTH_NONE = 7


_KIND_CONSTANTS = ast.parse(
    """
_TRUTH_UNKNOWN = 0
_TRUTH_BOOL = 1
_TRUTH_INT = 2
_TRUTH_FLOAT = 3
_TRUTH_STRING = 4
_TRUTH_BYTES = 5
_TRUTH_CONTAINER = 6
_TRUTH_NONE = 7
"""
).body

_KIND_METHODS = ast.parse(
    """
def expression_kind(self, node: ast.expr) -> int:
    if isinstance(node, ast.Name):
        return self.kind_hints.get(node.id, _TRUTH_UNKNOWN)
    if isinstance(node, ast.Compare):
        return _TRUTH_BOOL
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _TRUTH_BOOL
    if isinstance(node, ast.BoolOp):
        if not node.values:
            return _TRUTH_UNKNOWN
        result = self.expression_kind(node.values[0])
        index = 1
        while index < len(node.values):
            candidate = self.expression_kind(node.values[index])
            if candidate != result:
                return _TRUTH_UNKNOWN
            index += 1
        return result
    if isinstance(node, ast.IfExp):
        body_kind = self.expression_kind(node.body)
        other_kind = self.expression_kind(node.orelse)
        return body_kind if body_kind == other_kind else _TRUTH_UNKNOWN
    if isinstance(node, ast.JoinedStr):
        return _TRUTH_STRING
    if isinstance(node, (ast.List, ast.Tuple, ast.Dict, ast.Set)):
        return _TRUTH_CONTAINER
    if isinstance(node, ast.Constant):
        value = node.value
        if value is None:
            return _TRUTH_NONE
        if value is True or value is False:
            return _TRUTH_BOOL
        if isinstance(value, str):
            return _TRUTH_STRING
        if isinstance(value, bytes):
            return _TRUTH_BYTES
        if isinstance(value, float):
            return _TRUTH_FLOAT
        if isinstance(value, int):
            return _TRUTH_INT
    if isinstance(node, ast.BinOp):
        left = self.expression_kind(node.left)
        right = self.expression_kind(node.right)
        if isinstance(node.op, ast.Add) and left == _TRUTH_STRING and right == _TRUTH_STRING:
            return _TRUTH_STRING
        if isinstance(node.op, ast.Div) or left == _TRUTH_FLOAT or right == _TRUTH_FLOAT:
            return _TRUTH_FLOAT
        if left == _TRUTH_INT and right == _TRUTH_INT:
            return _TRUTH_INT
    return _TRUTH_UNKNOWN


def emit_truth(self, node: ast.expr) -> None:
    self.emit(Op.TO_BOOL, self.expression_kind(node))
"""
).body

_TRUTH_HELPER = ast.parse(
    """
def _full_core_probe_truthy(value: object, kind: int) -> bool:
    if kind == 7:
        return False
    if kind == 1 or kind == 2:
        return value != 0
    if kind == 3:
        return value != 0.0
    if kind == 4 or kind == 5 or kind == 6:
        return len(value) != 0
    return bool(value)
"""
).body[0]


def _is_self_call(statement: ast.stmt, method: str) -> ast.Call | None:
    if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
        return None
    call = statement.value
    if (
        isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "self"
        and call.func.attr == method
    ):
        return call
    return None


def _op_member(call: ast.Call, name: str) -> bool:
    return (
        isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "self"
        and call.func.attr == "emit"
        and bool(call.args)
        and isinstance(call.args[0], ast.Attribute)
        and isinstance(call.args[0].value, ast.Name)
        and call.args[0].value.id == "Op"
        and call.args[0].attr == name
    )


def _emit_truth_statement(expression: ast.expr) -> ast.Expr:
    return ast.Expr(
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="self", ctx=ast.Load()),
                attr="emit_truth",
                ctx=ast.Load(),
            ),
            args=[expression],
            keywords=[],
        )
    )


def _kind_assignment(name: ast.expr, value: ast.expr) -> ast.Assign:
    return ast.Assign(
        targets=[
            ast.Subscript(
                value=ast.Attribute(
                    value=ast.Name(id="self", ctx=ast.Load()),
                    attr="kind_hints",
                    ctx=ast.Load(),
                ),
                slice=name,
                ctx=ast.Store(),
            )
        ],
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="self", ctx=ast.Load()),
                attr="expression_kind",
                ctx=ast.Load(),
            ),
            args=[value],
            keywords=[],
        ),
    )


class _TruthSiteRewriter(ast.NodeTransformer):
    """Insert ``emit_truth`` between expression evaluation and truth consumers."""

    def __init__(self) -> None:
        self.count = 0
        self.assignment_count = 0

    def _rewrite_sequence(self, body: list[ast.stmt]) -> list[ast.stmt]:
        rewritten: list[ast.stmt] = []
        index = 0
        while index < len(body):
            statement = body[index]
            rewritten.append(statement)
            expr_call = _is_self_call(statement, "expr")
            if expr_call is not None and expr_call.args:
                expression = expr_call.args[0]
                next_statement = body[index + 1] if index + 1 < len(body) else None
                next_call = _is_self_call(next_statement, "emit") if next_statement is not None else None
                if next_call is not None and any(
                    _op_member(next_call, name)
                    for name in ("JUMP_IF_FALSE", "JUMP_IF_TRUE")
                ):
                    rewritten.append(_emit_truth_statement(expression))
                    self.count += 1
                elif (
                    next_call is not None
                    and _op_member(next_call, "DUP_TOP")
                    and index + 2 < len(body)
                ):
                    third = body[index + 2]
                    jump_calls = [
                        node
                        for node in ast.walk(third)
                        if isinstance(node, ast.Call)
                        and any(
                            _op_member(node, name)
                            for name in ("JUMP_IF_FALSE_KEEP", "JUMP_IF_TRUE_KEEP")
                        )
                    ]
                    if jump_calls:
                        rewritten.append(next_statement)
                        rewritten.append(_emit_truth_statement(expression))
                        self.count += 1
                        index += 1
            index += 1
        return rewritten

    def _rewrite_assign_branch(self, node: ast.If) -> None:
        test_text = ast.unparse(node.test)
        if "isinstance(node, ast.Assign)" in test_text:
            for branch in ast.walk(node):
                if not isinstance(branch, ast.If):
                    continue
                branch_text = ast.unparse(branch.test)
                if (
                    "len(node.targets) == 1" not in branch_text
                    or "ast.Name" not in branch_text
                ):
                    continue
                for index, statement in enumerate(branch.body):
                    call = _is_self_call(statement, "store")
                    if call is None:
                        continue
                    branch.body.insert(
                        index + 1,
                        _kind_assignment(
                            ast.Attribute(
                                value=ast.Subscript(
                                    value=ast.Attribute(
                                        value=ast.Name(id="node", ctx=ast.Load()),
                                        attr="targets",
                                        ctx=ast.Load(),
                                    ),
                                    slice=ast.Constant(0),
                                    ctx=ast.Load(),
                                ),
                                attr="id",
                                ctx=ast.Load(),
                            ),
                            ast.Attribute(
                                value=ast.Name(id="node", ctx=ast.Load()),
                                attr="value",
                                ctx=ast.Load(),
                            ),
                        ),
                    )
                    self.assignment_count += 1
                    return
        if "isinstance(node, ast.AnnAssign)" in test_text and "node.value is not None" in test_text:
            for index, statement in enumerate(node.body):
                call = _is_self_call(statement, "store")
                if call is None:
                    continue
                name = ast.Attribute(
                    value=ast.Attribute(
                        value=ast.Name(id="node", ctx=ast.Load()),
                        attr="target",
                        ctx=ast.Load(),
                    ),
                    attr="id",
                    ctx=ast.Load(),
                )
                value = ast.Attribute(
                    value=ast.Name(id="node", ctx=ast.Load()),
                    attr="value",
                    ctx=ast.Load(),
                )
                guarded = ast.If(
                    test=ast.Call(
                        func=ast.Name(id="isinstance", ctx=ast.Load()),
                        args=[
                            ast.Attribute(
                                value=ast.Name(id="node", ctx=ast.Load()),
                                attr="target",
                                ctx=ast.Load(),
                            ),
                            ast.Attribute(
                                value=ast.Name(id="ast", ctx=ast.Load()),
                                attr="Name",
                                ctx=ast.Load(),
                            ),
                        ],
                        keywords=[],
                    ),
                    body=[_kind_assignment(name, value)],
                    orelse=[],
                )
                node.body.insert(index + 1, guarded)
                self.assignment_count += 1
                return

    def visit_If(self, node: ast.If) -> ast.AST:
        self.generic_visit(node)
        self._rewrite_assign_branch(node)
        test_text = ast.unparse(node.test)
        if (
            "isinstance(node, ast.UnaryOp)" in test_text
            and "ast.Not" in test_text
            and node.body
        ):
            first = _is_self_call(node.body[0], "expr")
            if first is not None and first.args:
                node.body.insert(1, _emit_truth_statement(first.args[0]))
                self.count += 1
        if "isinstance(node, ast.Assert)" in test_text and node.body:
            first = _is_self_call(node.body[0], "expr")
            if first is not None and first.args:
                node.body.insert(1, _emit_truth_statement(first.args[0]))
                self.count += 1
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.generic_visit(node)
        node.body = self._rewrite_sequence(node.body)
        for child in ast.walk(node):
            if isinstance(child, (ast.For, ast.While, ast.If, ast.With, ast.Try)):
                child.body = self._rewrite_sequence(child.body)
                if isinstance(child, (ast.For, ast.While, ast.If, ast.Try)):
                    child.orelse = self._rewrite_sequence(child.orelse)
                if isinstance(child, ast.Try):
                    child.finalbody = self._rewrite_sequence(child.finalbody)
                    for handler in child.handlers:
                        handler.body = self._rewrite_sequence(handler.body)
        return node


class _LowererConstructorHints(ast.NodeTransformer):
    def __init__(self) -> None:
        self.count = 0
        self.in_lowerer = False

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        previous = self.in_lowerer
        self.in_lowerer = node.name == "_Lowerer"
        self.generic_visit(node)
        self.in_lowerer = previous
        return node

    def _rewrite_body(self, body: list[ast.stmt]) -> list[ast.stmt]:
        if not self.in_lowerer:
            return body
        result: list[ast.stmt] = []
        for statement in body:
            result.append(statement)
            if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
                continue
            target = statement.targets[0]
            value = statement.value
            if (
                not isinstance(target, ast.Name)
                or not isinstance(value, ast.Call)
                or not isinstance(value.func, ast.Name)
                or value.func.id != "_Lowerer"
            ):
                continue
            result.append(
                ast.Expr(
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Attribute(
                                value=ast.Name(id=target.id, ctx=ast.Load()),
                                attr="kind_hints",
                                ctx=ast.Load(),
                            ),
                            attr="update",
                            ctx=ast.Load(),
                        ),
                        args=[
                            ast.Attribute(
                                value=ast.Name(id="self", ctx=ast.Load()),
                                attr="kind_hints",
                                ctx=ast.Load(),
                            )
                        ],
                        keywords=[],
                    )
                )
            )
            self.count += 1
        return result

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.generic_visit(node)
        node.body = self._rewrite_body(node.body)
        return node


def _normalize_bytecode() -> int:
    module = ast.parse(BYTECODE_PATH.read_text(encoding="utf-8"))
    op_class = next(
        node for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "Op"
    )
    if any(
        isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "TO_BOOL" for target in node.targets)
        for node in op_class.body
    ):
        raise RuntimeError("TO_BOOL opcode already exists")
    op_class.body.append(
        ast.Assign(
            targets=[ast.Name(id="TO_BOOL", ctx=ast.Store())],
            value=ast.Constant(115),
        )
    )
    valid = next(
        node for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "_VALID_OPS" for target in node.targets)
    )
    if not isinstance(valid.value, ast.Tuple):
        raise RuntimeError("_VALID_OPS is not a tuple")
    valid.value.elts.append(
        ast.Attribute(
            value=ast.Name(id="Op", ctx=ast.Load()),
            attr="TO_BOOL",
            ctx=ast.Load(),
        )
    )
    ast.fix_missing_locations(module)
    BYTECODE_PATH.write_text(ast.unparse(module) + "\n", encoding="utf-8")
    return 2


def _normalize_frontend() -> tuple[int, int, int]:
    module = ast.parse(FRONTEND_PATH.read_text(encoding="utf-8"))
    if any(
        isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "_TRUTH_UNKNOWN" for target in node.targets)
        for node in module.body
    ):
        raise RuntimeError("frontend truth kinds already exist")
    lowerer = next(
        node for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "_Lowerer"
    )
    field_insert = next(
        (index for index, node in enumerate(lowerer.body)
         if isinstance(node, ast.FunctionDef)),
        len(lowerer.body),
    )
    lowerer.body.insert(
        field_insert,
        ast.AnnAssign(
            target=ast.Name(id="kind_hints", ctx=ast.Store()),
            annotation=ast.Subscript(
                value=ast.Name(id="dict", ctx=ast.Load()),
                slice=ast.Tuple(
                    elts=[
                        ast.Name(id="str", ctx=ast.Load()),
                        ast.Name(id="int", ctx=ast.Load()),
                    ],
                    ctx=ast.Load(),
                ),
                ctx=ast.Load(),
            ),
            value=ast.Call(
                func=ast.Name(id="field", ctx=ast.Load()),
                args=[],
                keywords=[
                    ast.keyword(
                        arg="default_factory",
                        value=ast.Name(id="dict", ctx=ast.Load()),
                    )
                ],
            ),
            simple=1,
        ),
    )
    expr_index = next(
        index for index, node in enumerate(lowerer.body)
        if isinstance(node, ast.FunctionDef) and node.name == "expr"
    )
    lowerer.body[expr_index:expr_index] = _KIND_METHODS

    constants_at = next(
        index for index, node in enumerate(module.body)
        if isinstance(node, ast.FunctionDef) and node.name == "_defer_annotation"
    )
    module.body[constants_at:constants_at] = _KIND_CONSTANTS

    constructor_rewriter = _LowererConstructorHints()
    module = constructor_rewriter.visit(module)
    truth_rewriter = _TruthSiteRewriter()
    module = truth_rewriter.visit(module)

    compile_function = next(
        node for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "compile_source"
    )
    compile_function.args.args.append(ast.arg(arg="kind_hints", annotation=None))
    compile_function.args.defaults.append(ast.Constant(None))
    lowerer_assign = next(
        index for index, node in enumerate(compile_function.body)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "lowerer" for target in node.targets)
    )
    compile_function.body.insert(
        lowerer_assign + 1,
        ast.If(
            test=ast.Compare(
                left=ast.Name(id="kind_hints", ctx=ast.Load()),
                ops=[ast.IsNot()],
                comparators=[ast.Constant(None)],
            ),
            body=[
                ast.Expr(
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Attribute(
                                value=ast.Name(id="lowerer", ctx=ast.Load()),
                                attr="kind_hints",
                                ctx=ast.Load(),
                            ),
                            attr="update",
                            ctx=ast.Load(),
                        ),
                        args=[ast.Name(id="kind_hints", ctx=ast.Load())],
                        keywords=[],
                    )
                )
            ],
            orelse=[],
        ),
    )

    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    FRONTEND_PATH.write_text(source, encoding="utf-8")
    if "Op.TO_BOOL" not in source:
        raise RuntimeError("frontend did not emit TO_BOOL")
    if "def expression_kind" not in source:
        raise RuntimeError("frontend kind inference was not installed")
    return truth_rewriter.count, truth_rewriter.assignment_count, constructor_rewriter.count


class _VmOpcodeInsert(ast.NodeTransformer):
    def __init__(self) -> None:
        self.count = 0

    def visit_If(self, node: ast.If) -> ast.AST:
        self.generic_visit(node)
        test = node.test
        if not (
            isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and test.left.id == "op"
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Is)
            and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Attribute)
            and isinstance(test.comparators[0].value, ast.Name)
            and test.comparators[0].value.id == "Op"
            and test.comparators[0].attr == "TRY_BEGIN"
        ):
            return node
        self.count += 1
        return ast.copy_location(
            ast.If(
                test=ast.Compare(
                    left=ast.Name(id="op", ctx=ast.Load()),
                    ops=[ast.Is()],
                    comparators=[
                        ast.Attribute(
                            value=ast.Name(id="Op", ctx=ast.Load()),
                            attr="TO_BOOL",
                            ctx=ast.Load(),
                        )
                    ],
                ),
                body=[
                    ast.Assign(
                        targets=[ast.Name(id="value", ctx=ast.Store())],
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Attribute(
                                    value=ast.Name(id="frame", ctx=ast.Load()),
                                    attr="stack",
                                    ctx=ast.Load(),
                                ),
                                attr="pop",
                                ctx=ast.Load(),
                            ),
                            args=[],
                            keywords=[],
                        ),
                    ),
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Attribute(
                                    value=ast.Name(id="frame", ctx=ast.Load()),
                                    attr="stack",
                                    ctx=ast.Load(),
                                ),
                                attr="append",
                                ctx=ast.Load(),
                            ),
                            args=[
                                ast.Call(
                                    func=ast.Name(id="_full_core_probe_truthy", ctx=ast.Load()),
                                    args=[
                                        ast.Name(id="value", ctx=ast.Load()),
                                        ast.Attribute(
                                            value=ast.Name(id="instr", ctx=ast.Load()),
                                            attr="arg",
                                            ctx=ast.Load(),
                                        ),
                                    ],
                                    keywords=[],
                                )
                            ],
                            keywords=[],
                        )
                    ),
                ],
                orelse=[node],
            ),
            node,
        )


def _normalize_vm() -> int:
    module = ast.parse(VM_PATH.read_text(encoding="utf-8"))
    if any(
        isinstance(node, ast.FunctionDef) and node.name == "_full_core_probe_truthy"
        for node in module.body
    ):
        raise RuntimeError("VM truth helper already exists")
    insert_at = next(
        index for index, node in enumerate(module.body)
        if isinstance(node, ast.ClassDef) and node.name == "VirtualMachine"
    )
    module.body.insert(insert_at, _TRUTH_HELPER)
    rewriter = _VmOpcodeInsert()
    module = rewriter.visit(module)
    if rewriter.count != 1:
        raise RuntimeError(
            f"TO_BOOL VM handler expected one insertion, found {rewriter.count}"
        )
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    VM_PATH.write_text(source, encoding="utf-8")
    return rewriter.count


class _EntryRewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.compile_count = 0
        self.kind_sync_count = 0
        self.exec_order_count = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.generic_visit(node)
        if node.name == "exec_utf8":
            for statement in node.body:
                if not isinstance(statement, ast.Try):
                    continue
                for inner in statement.body:
                    if not isinstance(inner, ast.Assign):
                        continue
                    if not isinstance(inner.value, ast.Call):
                        continue
                    call = inner.value
                    if isinstance(call.func, ast.Name) and call.func.id == "compile_source":
                        call.args = [
                            ast.Name(id="source", ctx=ast.Load()),
                            ast.Name(id="filename", ctx=ast.Load()),
                            ast.Constant("exec"),
                            ast.Call(
                                func=ast.Name(id="getattr", ctx=ast.Load()),
                                args=[
                                    ast.Name(id="self", ctx=ast.Load()),
                                    ast.Constant("_native_kind_hints"),
                                    ast.Dict(keys=[], values=[]),
                                ],
                                keywords=[],
                            ),
                        ]
                        call.keywords = []
                        self.compile_count += 1
        if node.name == "_native_set_global_kind":
            node.body.extend(
                ast.parse(
                    """
instance = _runtime(runtime)
if instance is not None:
    hints = getattr(instance, "_native_kind_hints", None)
    if hints is None:
        hints = {}
        instance._native_kind_hints = hints
    hints[name] = kind
"""
                ).body
            )
            self.kind_sync_count += 1
        if node.name == "_portapy_exec_span_impl":
            record_index = next(
                (index for index, statement in enumerate(node.body)
                 if isinstance(statement, ast.Expr)
                 and isinstance(statement.value, ast.Call)
                 and isinstance(statement.value.func, ast.Name)
                 and statement.value.func.id == "_native_record_source_kinds"),
                -1,
            )
            status_index = next(
                (index for index, statement in enumerate(node.body)
                 if isinstance(statement, ast.Assign)
                 and isinstance(statement.value, ast.Call)
                 and isinstance(statement.value.func, ast.Attribute)
                 and statement.value.func.attr == "exec_utf8"),
                -1,
            )
            if record_index < 0 or status_index < 0:
                raise RuntimeError("native exec kind-recording shape changed")
            record = node.body.pop(record_index)
            if record_index < status_index:
                status_index -= 1
            node.body.insert(status_index, record)
            self.exec_order_count += 1
        return node


def _normalize_entry() -> tuple[int, int, int]:
    module = ast.parse(ENTRY_PATH.read_text(encoding="utf-8"))
    rewriter = _EntryRewrite()
    module = rewriter.visit(module)
    expected = (1, 1, 1)
    actual = (rewriter.compile_count, rewriter.kind_sync_count, rewriter.exec_order_count)
    if actual != expected:
        raise RuntimeError(
            f"native truth-hint entry rewrite expected {expected}, found {actual}"
        )
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    ENTRY_PATH.write_text(source, encoding="utf-8")
    if "compile_source(source, filename, 'exec', getattr(self, '_native_kind_hints', {}))" not in source:
        raise RuntimeError("Runtime compile_source kind hints were not installed")
    return actual


def main() -> int:
    bytecode_count = _normalize_bytecode()
    truth_count, assignment_count, constructor_count = _normalize_frontend()
    vm_count = _normalize_vm()
    compile_count, sync_count, order_count = _normalize_entry()
    print(
        "NORMALIZED NATIVE TRUTHINESS",
        bytecode_count,
        truth_count,
        assignment_count,
        constructor_count,
        vm_count,
        compile_count,
        sync_count,
        order_count,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
