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
    loop_starts: list[int] = field(default_factory=list)
    loop_breaks: list[list[int]] = field(default_factory=list)
    loop_has_iterator: list[bool] = field(default_factory=list)

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

    def load_dotted_name(self, value: str) -> None:
        """Load a decorator or other parser-provided dotted name."""
        pieces = value.split(".")
        self.emit(Op.LOAD_NAME, self.name_index(pieces[0]))
        for piece in pieces[1:]:
            self.emit(Op.GET_ATTR, self.name_index(piece))

    def call(
        self,
        args: list[A.Expr],
        kwargs: list,
        dstar: A.Expr | None = None,
    ) -> None:
        if dstar is not None:
            self.unsupported(dstar, "** call arguments")
        for argument in args:
            if isinstance(argument, A.Starred):
                self.unsupported(argument, "* call arguments")
            self.expression(argument)
        if not kwargs:
            self.emit(Op.CALL, len(args))
            return
        keyword_names: list[str] = []
        for item in kwargs:
            if not isinstance(item, tuple) or len(item) != 2:
                self.unsupported(item, "malformed keyword argument")
            keyword_name, value = item
            if not isinstance(keyword_name, str):
                self.unsupported(item, "keyword argument name")
            keyword_names.append(keyword_name)
            self.expression(value)
        self.emit(
            Op.CALL_KW,
            self.constant((tuple(False for _ in args), tuple(keyword_names))),
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
        if isinstance(node, A.Attr):
            self.expression(node.obj)
            self.emit(Op.GET_ATTR, self.name_index(node.name))
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
            self.emit(Op.LOAD_NAME, self.name_index(node.func))
            self.call(node.args, node.kwargs, node.dstar)
            return
        if isinstance(node, A.MethodCall):
            self.expression(node.obj)
            self.emit(Op.GET_ATTR, self.name_index(node.method))
            self.call(node.args, node.kwargs)
            return
        self.unsupported(node)

    def begin_loop(self, start: int, has_iterator: bool) -> None:
        self.loop_starts.append(start)
        self.loop_breaks.append([])
        self.loop_has_iterator.append(has_iterator)

    def finish_loop(self, after_else: int) -> None:
        for jump in self.loop_breaks.pop():
            self.patch(jump, after_else)
        self.loop_starts.pop()
        self.loop_has_iterator.pop()

    def statement(self, node: A.Stmt) -> None:
        if isinstance(node, A.Assign):
            self.expression(node.value)
            self.emit(Op.STORE_NAME, self.name_index(node.target))
            return
        if isinstance(node, A.AttrAssign):
            self.expression(node.obj)
            self.expression(node.value)
            self.emit(Op.SET_ATTR, self.name_index(node.name))
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
            self.begin_loop(start, False)
            self.expression(node.test)
            exit_jump = self.emit(Op.JUMP_IF_FALSE)
            for statement in node.body:
                self.statement(statement)
            self.emit(Op.JUMP, start)
            self.patch(exit_jump, len(self.instructions))
            for statement in node.orelse:
                self.statement(statement)
            self.finish_loop(len(self.instructions))
            return
        if isinstance(node, A.For):
            if node.targets:
                self.unsupported(node, "tuple-unpack for target")
            if node.iter is not None:
                self.expression(node.iter)
            else:
                self.emit(Op.LOAD_NAME, self.name_index("range"))
                for argument in node.range_args:
                    self.expression(argument)
                self.emit(Op.CALL, len(node.range_args))
            self.emit(Op.GET_ITER)
            start = len(self.instructions)
            exit_jump = self.emit(Op.FOR_ITER)
            self.emit(Op.STORE_NAME, self.name_index(node.var))
            self.begin_loop(start, True)
            for statement in node.body:
                self.statement(statement)
            self.emit(Op.JUMP, start)
            self.patch(exit_jump, len(self.instructions))
            for statement in node.orelse:
                self.statement(statement)
            self.finish_loop(len(self.instructions))
            return
        if isinstance(node, A.Break):
            if not self.loop_starts:
                self.unsupported(node, "break outside loop")
            if self.loop_has_iterator[-1]:
                self.emit(Op.POP_TOP)
            self.loop_breaks[-1].append(self.emit(Op.JUMP))
            return
        if isinstance(node, A.Continue):
            if not self.loop_starts:
                self.unsupported(node, "continue outside loop")
            self.emit(Op.JUMP, self.loop_starts[-1])
            return
        if isinstance(node, A.Pass):
            return
        self.unsupported(node)

    def function(self, node: A.FuncDef) -> None:
        if node.vararg is not None or node.kwarg is not None:
            self.unsupported(node, "*args or **kwargs")
        nested = _PortableLowerer(node.name, list(node.params))
        for statement in node.body:
            nested.statement(statement)
        nested.emit(Op.RETURN)
        function_code = nested.finish()

        defaults = list(node.defaults)
        if len(defaults) < len(node.params):
            defaults = [None] * (len(node.params) - len(defaults)) + defaults
        first_default = len(defaults)
        for index, default in enumerate(defaults):
            if default is not None:
                first_default = index
                break
        if any(default is None for default in defaults[first_default:]):
            self.unsupported(node, "non-trailing default arguments")
        default_count = len(defaults) - first_default
        for default in defaults[first_default:]:
            assert default is not None
            self.expression(default)

        self.emit(
            Op.MAKE_FUNCTION,
            self.constant((function_code, default_count, 0, {})),
        )
        for decorator in reversed(node.decorators):
            self.load_dotted_name(decorator)
            self.emit(Op.SWAP)
            self.emit(Op.CALL, 1)
        self.emit(Op.STORE_NAME, self.name_index(node.name))

    def class_definition(self, node: A.ClassDef) -> None:
        body = _PortableLowerer(f"{self.name}.{node.name}")
        for class_name, _annotation, value in node.class_vars:
            if value is None:
                continue
            body.expression(value)
            body.emit(Op.STORE_NAME, body.name_index(class_name))
        for method in node.methods:
            body.function(method)
        body.emit(Op.RETURN)

        base_count = 0
        if node.parent is not None:
            self.emit(Op.LOAD_NAME, self.name_index(node.parent))
            base_count = 1
        self.emit(
            Op.MAKE_CLASS,
            self.constant((node.name, body.finish(), base_count, False)),
        )
        for decorator in reversed(node.decorators):
            self.load_dotted_name(decorator)
            self.emit(Op.SWAP)
            self.emit(Op.CALL, 1)
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
    for class_definition in module.classes:
        lowerer.class_definition(class_definition)
    for function in module.funcs:
        lowerer.function(function)
    for statement in module.body:
        lowerer.statement(statement)
    return lowerer.finish()
