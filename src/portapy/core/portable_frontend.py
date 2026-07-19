"""Lower PortaPy's own parser AST into portable bytecode.

This module is the CPython-independent replacement path for the bootstrap
``frontend.py``. It grows by exact syntax slices and raises a precise error for
every unsupported node. More nodes will move here until the host-``ast``
frontend can be deleted completely.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from portapy.parser import ast_nodes as A
from portapy.parser import parse_source

from .bytecode import CodeObject, Instruction, Op


class PortableFrontendError(Exception):
    """Source parsed successfully but is outside the portable lowering subset."""


_BINARY_OPS = {
    "+": Op.BINARY_ADD,
    "-": Op.BINARY_SUB,
    "*": Op.BINARY_MUL,
    "/": Op.BINARY_DIV,
    "//": Op.BINARY_FLOORDIV,
    "%": Op.BINARY_MOD,
    "**": Op.BINARY_POW,
    "&": Op.BINARY_BITAND,
    "|": Op.BINARY_BITOR,
    "^": Op.BINARY_BITXOR,
    "<<": Op.BINARY_LSHIFT,
    ">>": Op.BINARY_RSHIFT,
    "@": Op.BINARY_MATMUL,
}
_COMPARE_OPS = {
    "==": Op.COMPARE_EQ,
    "!=": Op.COMPARE_NE,
    "<": Op.COMPARE_LT,
    "<=": Op.COMPARE_LE,
    ">": Op.COMPARE_GT,
    ">=": Op.COMPARE_GE,
    "is": Op.COMPARE_IS,
    "is not": Op.COMPARE_IS_NOT,
    "in": Op.COMPARE_IN,
    "not in": Op.COMPARE_NOT_IN,
}
_UNARY_OPS = {
    "-": Op.UNARY_NEGATIVE,
    "+": Op.UNARY_POSITIVE,
    "~": Op.UNARY_INVERT,
    "not": Op.UNARY_NOT,
}


@dataclass
class _PortableLowerer:
    name: str
    arg_names: list[str] = field(default_factory=list)
    constants: list[object] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    instructions: list[Instruction] = field(default_factory=list)

    def constant(self, value: object) -> int:
        self.constants.append(value)
        return len(self.constants) - 1

    def name_index(self, value: str) -> int:
        try:
            return self.names.index(value)
        except ValueError:
            self.names.append(value)
            return len(self.names) - 1

    def emit(self, op: int, arg: int = 0) -> int:
        self.instructions.append(Instruction(op, arg))
        return len(self.instructions) - 1

    def patch(self, offset: int, target: int) -> None:
        instruction = self.instructions[offset]
        self.instructions[offset] = Instruction(instruction.op, target)

    def unsupported(self, node: object, detail: str | None = None) -> None:
        position = getattr(node, "pos", None)
        line = getattr(position, "line", 0)
        kind = detail or type(node).__name__
        raise PortableFrontendError(
            f"{self.name}:{line}: portable frontend does not support {kind}"
        )

    def expression(self, node: A.Expr) -> None:
        if isinstance(node, A.IntLit):
            if node.is_none:
                value: object = None
            elif node.is_bool:
                value = bool(node.value)
            else:
                value = node.value
            self.emit(Op.LOAD_CONST, self.constant(value))
            return
        if isinstance(node, A.FloatLit):
            self.emit(Op.LOAD_CONST, self.constant(node.value))
            return
        if isinstance(node, A.StrLit):
            self.emit(Op.LOAD_CONST, self.constant(node.value))
            return
        if isinstance(node, A.Name):
            self.emit(Op.LOAD_NAME, self.name_index(node.name))
            return
        if isinstance(node, A.BinOp):
            opcode = _BINARY_OPS.get(node.op)
            if opcode is None:
                self.unsupported(node, f"binary operator {node.op!r}")
            self.expression(node.left)
            self.expression(node.right)
            self.emit(opcode)
            return
        if isinstance(node, A.UnaryOp):
            opcode = _UNARY_OPS.get(node.op)
            if opcode is None:
                self.unsupported(node, f"unary operator {node.op!r}")
            self.expression(node.operand)
            self.emit(opcode)
            return
        if isinstance(node, A.BoolOp):
            self.expression(node.left)
            self.emit(Op.DUP_TOP)
            jump = self.emit(
                Op.JUMP_IF_FALSE_KEEP if node.op == "and" else Op.JUMP_IF_TRUE_KEEP
            )
            self.emit(Op.POP_TOP)
            self.expression(node.right)
            self.patch(jump, len(self.instructions))
            return
        if isinstance(node, A.Compare):
            if len(node.ops) + 1 != len(node.operands):
                self.unsupported(node, "malformed chained comparison")
            for index, operator in enumerate(node.ops):
                opcode = _COMPARE_OPS.get(operator)
                if opcode is None:
                    self.unsupported(node, f"comparison operator {operator!r}")
                self.expression(node.operands[index])
                self.expression(node.operands[index + 1])
                self.emit(opcode)
                if index:
                    self.emit(Op.BINARY_BOOL_AND)
            return
        if isinstance(node, A.IfExp):
            self.expression(node.test)
            otherwise = self.emit(Op.JUMP_IF_FALSE)
            self.expression(node.body)
            end = self.emit(Op.JUMP)
            self.patch(otherwise, len(self.instructions))
            self.expression(node.orelse)
            self.patch(end, len(self.instructions))
            return
        if isinstance(node, A.ListLit):
            for element in node.elems:
                self.expression(element)
            self.emit(Op.BUILD_LIST, len(node.elems))
            return
        if isinstance(node, A.TupleLit):
            for element in node.elems:
                self.expression(element)
            self.emit(Op.BUILD_TUPLE, len(node.elems))
            return
        if isinstance(node, A.SetLit):
            for element in node.elems:
                self.expression(element)
            self.emit(Op.BUILD_SET, len(node.elems))
            return
        if isinstance(node, A.DictLit):
            if any(key is None for key in node.keys):
                self.unsupported(node, "dictionary unpacking")
            for key, value in zip(node.keys, node.values):
                assert key is not None
                self.expression(key)
                self.expression(value)
            self.emit(Op.BUILD_DICT, len(node.keys))
            return
        if isinstance(node, A.Subscript):
            if isinstance(node.index, A.Slice):
                self.unsupported(node, "slicing")
            self.expression(node.obj)
            self.expression(node.index)
            self.emit(Op.GET_ITEM)
            return
        if isinstance(node, A.Call):
            if node.kwargs or node.dstar is not None:
                self.unsupported(node, "keyword or ** call arguments")
            self.emit(Op.LOAD_NAME, self.name_index(node.func))
            for argument in node.args:
                self.expression(argument)
            self.emit(Op.CALL, len(node.args))
            return
        self.unsupported(node)

    def statement(self, node: A.Stmt) -> None:
        if isinstance(node, A.Assign):
            self.expression(node.value)
            self.emit(Op.STORE_NAME, self.name_index(node.target))
            return
        if isinstance(node, A.AugAssign):
            opcode = _BINARY_OPS.get(node.op)
            if opcode is None:
                self.unsupported(node, f"augmented operator {node.op!r}")
            self.emit(Op.LOAD_NAME, self.name_index(node.target))
            self.expression(node.value)
            self.emit(opcode)
            self.emit(Op.STORE_NAME, self.name_index(node.target))
            return
        if isinstance(node, A.IndexAssign):
            if isinstance(node.target.index, A.Slice):
                self.unsupported(node, "slice assignment")
            self.expression(node.target.obj)
            self.expression(node.target.index)
            self.expression(node.value)
            self.emit(Op.SET_ITEM)
            return
        if isinstance(node, A.ExprStmt):
            self.expression(node.expr)
            self.emit(Op.POP_TOP)
            return
        if isinstance(node, A.Return):
            if node.value is not None:
                self.expression(node.value)
            self.emit(Op.RETURN)
            return
        if isinstance(node, A.If):
            self.expression(node.test)
            otherwise = self.emit(Op.JUMP_IF_FALSE)
            for statement in node.then:
                self.statement(statement)
            end = self.emit(Op.JUMP)
            self.patch(otherwise, len(self.instructions))
            for statement in node.orelse:
                self.statement(statement)
            self.patch(end, len(self.instructions))
            return
        if isinstance(node, A.While):
            start = len(self.instructions)
            self.expression(node.test)
            exit_jump = self.emit(Op.JUMP_IF_FALSE)
            for statement in node.body:
                self.statement(statement)
            self.emit(Op.JUMP, start)
            self.patch(exit_jump, len(self.instructions))
            for statement in node.orelse:
                self.statement(statement)
            return
        if isinstance(node, A.Pass):
            return
        self.unsupported(node)

    def function(self, node: A.FuncDef) -> None:
        if node.vararg is not None or node.kwarg is not None:
            self.unsupported(node, "*args or **kwargs")
        if any(default is not None for default in node.defaults):
            self.unsupported(node, "default arguments")
        nested = _PortableLowerer(node.name, list(node.params))
        for statement in node.body:
            nested.statement(statement)
        nested.emit(Op.RETURN)
        function_code = nested.finish()
        self.emit(
            Op.MAKE_FUNCTION,
            self.constant((function_code, 0, 0, {})),
        )
        self.emit(Op.STORE_NAME, self.name_index(node.name))

    def finish(self) -> CodeObject:
        code = CodeObject(
            name=self.name,
            instructions=self.instructions,
            constants=self.constants,
            names=self.names,
            arg_names=self.arg_names,
        )
        code.validate()
        return code


def compile_portable_source(
    source: str,
    filename: str = "<portapy>",
) -> CodeObject:
    """Parse and lower source without importing CPython's ``ast`` module."""
    module = parse_source(source)
    lowerer = _PortableLowerer(filename)
    for function in module.funcs:
        lowerer.function(function)
    for statement in module.body:
        lowerer.statement(statement)
    return lowerer.finish()
