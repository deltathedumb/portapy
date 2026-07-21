"""Final scope, async, and loop-target layer for the standalone PortaPy frontend."""
from __future__ import annotations

from portapy.parser import ast_nodes as A

from . import portable_frontend_unpacking as _unpacking
from .bytecode import CodeObject, Op
from .portable_parser import parse_portable_source


PortableFrontendError = _unpacking.PortableFrontendError


def _position_key(node: object) -> tuple[int, int]:
    position = getattr(node, "pos", None)
    return (
        int(getattr(position, "line", 0)),
        int(getattr(position, "column", 0)),
    )


class _PortableLowerer(_unpacking._PortableLowerer):
    """Add exact lifted binding, coroutine lowering, and source metadata."""

    lifted_functions_by_position: dict[tuple[int, int], A.FuncDef] = {}
    source_filename = "<portapy>"
    source_lines: list[str] = []

    def mark_position(self, node: object) -> None:
        position = getattr(node, "pos", None)
        self.current_line = int(getattr(position, "line", 0))
        self.current_column = int(getattr(position, "column", 0))

    def emit(self, op: int, arg: int = 0) -> int:
        offset = super().emit(op, arg)
        lines = getattr(self, "instruction_lines", None)
        columns = getattr(self, "instruction_columns", None)
        if lines is None:
            lines = []
            self.instruction_lines = lines
        if columns is None:
            columns = []
            self.instruction_columns = columns
        lines.append(int(getattr(self, "current_line", 0)))
        columns.append(int(getattr(self, "current_column", 0)))
        return offset

    def compile_function_code(self, node: A.FuncDef) -> CodeObject:
        code = super().compile_function_code(node)
        code.definition_line = int(getattr(node.pos, "line", 0))
        code.definition_column = int(getattr(node.pos, "column", 0))
        if getattr(node, "is_async", False):
            code.is_coroutine = True
            code.is_async_generator = bool(code.is_generator)
            code.validate()
        return code

    def function(self, node: A.FuncDef) -> None:
        self.mark_position(node)
        super().function(node)

    def class_definition(self, node: A.ClassDef) -> None:
        self.mark_position(node)
        super().class_definition(node)

    def expression(self, node: A.Expr) -> None:
        self.mark_position(node)
        if isinstance(node, A.UnaryOp) and node.op == "await":
            self.expression(node.operand)
            self.emit(Op.AWAIT)
            return
        super().expression(node)

    def lower_unpacking_for(self, node: A.For) -> None:
        self.mark_position(node)
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
        self.store_comprehension_target(node.var, node.targets)
        self.begin_loop(start, True)
        for statement in node.body:
            self.statement(statement)
        self.emit(Op.JUMP, start)
        self.patch(exit_jump, len(self.instructions))
        for statement in node.orelse:
            self.statement(statement)
        self.finish_loop(len(self.instructions))

    def statement(self, node: A.Stmt) -> None:
        self.mark_position(node)
        if isinstance(node, A.ClosureBind):
            definition = self.lifted_functions_by_position.get(_position_key(node))
            if definition is None:
                self.unsupported(node, f"unknown lifted function {node.func_name!r}")
            self.emit_function(definition, node.func_name)
            return
        if isinstance(node, A.Pass):
            # The parser historically emits Pass for a nested function with no
            # free variables. Its source position still identifies the lifted
            # FuncDef exactly, so bind the function instead of dropping it.
            definition = self.lifted_functions_by_position.get(_position_key(node))
            if definition is not None:
                self.emit_function(definition, definition.name)
                return
        if isinstance(node, A.For) and node.targets:
            self.lower_unpacking_for(node)
            return
        super().statement(node)

    def finish(self) -> CodeObject:
        code = super().finish()
        code.filename = self.source_filename
        code.source_lines = list(self.source_lines)
        code.instruction_lines = list(getattr(self, "instruction_lines", []))
        code.instruction_columns = list(getattr(self, "instruction_columns", []))
        nonzero = [line for line in code.instruction_lines if line > 0]
        code.first_line = min(nonzero) if nonzero else 1
        return code


_unpacking._PortableLowerer = _PortableLowerer
_unpacking._comprehensions._PortableLowerer = _PortableLowerer
_unpacking._comprehensions._control._PortableLowerer = _PortableLowerer
_unpacking._comprehensions._control._base._PortableLowerer = _PortableLowerer


def _configure_lowerer(
    parsed: A.Module,
    filename: str,
    source: str,
) -> _PortableLowerer:
    _PortableLowerer.function_definitions = {
        function.name: function for function in parsed.funcs
    }
    _PortableLowerer.function_code_cache = {}
    _PortableLowerer.lifted_functions_by_position = {
        _position_key(function): function
        for function in parsed.funcs
        if function.is_lifted
    }
    _PortableLowerer.source_filename = filename
    _PortableLowerer.source_lines = source.splitlines()
    return _PortableLowerer(filename)


def _lower_module(parsed: A.Module, lowerer: _PortableLowerer) -> None:
    ordered: list[tuple[int, int, str, object]] = []
    sequence = 0
    for class_definition in parsed.classes:
        ordered.append((class_definition.pos.line, sequence, "class", class_definition))
        sequence += 1
    for function in parsed.funcs:
        if function.is_lifted:
            continue
        ordered.append((function.pos.line, sequence, "function", function))
        sequence += 1
    for statement in parsed.body:
        ordered.append((statement.pos.line, sequence, "statement", statement))
        sequence += 1

    for _line, _sequence, kind, node in sorted(ordered):
        if kind == "class":
            lowerer.class_definition(node)
        elif kind == "function":
            lowerer.function(node)
        else:
            lowerer.statement(node)


def compile_portable_source(
    source: str,
    filename: str = "<portapy>",
    mode: str = "exec",
) -> CodeObject:
    """Parse and lower through PortaPy-owned components.

    ``mode`` mirrors Python's public ``compile`` modes. ``eval`` returns the
    expression value from :class:`VirtualMachine.run`; ``single`` marks the
    code interactive and also returns a lone expression instead of discarding
    it. No path imports or delegates to host ``ast``.
    """
    if mode not in {"exec", "eval", "single"}:
        raise ValueError(f"unsupported compile mode: {mode!r}")

    result_name = "__portapy_compiled_result"
    parse_source = source
    if mode == "eval":
        parse_source = f"{result_name} = ({source})\n"

    parsed = parse_portable_source(parse_source)
    lowerer = _configure_lowerer(parsed, filename, parse_source)

    lone_expression = (
        mode == "single"
        and not parsed.classes
        and not parsed.funcs
        and len(parsed.body) == 1
        and isinstance(parsed.body[0], A.ExprStmt)
    )
    if lone_expression:
        lowerer.expression(parsed.body[0].expr)
        lowerer.emit(Op.RETURN)
    else:
        _lower_module(parsed, lowerer)
        if mode == "eval":
            index = lowerer.name_index(result_name)
            lowerer.emit(Op.LOAD_NAME, index)
            lowerer.emit(Op.DELETE_NAME, index)
            lowerer.emit(Op.RETURN)

    code = lowerer.finish()
    code.interactive = mode == "single"
    code.validate()
    return code


__all__ = ["PortableFrontendError", "compile_portable_source"]
