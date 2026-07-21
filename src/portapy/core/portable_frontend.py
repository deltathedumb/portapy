"""Final scope and loop-target layer for the standalone PortaPy frontend."""
from __future__ import annotations

from portapy.parser import ast_nodes as A
from portapy.parser import parse_source

from . import portable_frontend_unpacking as _unpacking
from .bytecode import Op


PortableFrontendError = _unpacking.PortableFrontendError


def _position_key(node: object) -> tuple[int, int]:
    position = getattr(node, "pos", None)
    return (
        int(getattr(position, "line", 0)),
        int(getattr(position, "column", 0)),
    )


class _PortableLowerer(_unpacking._PortableLowerer):
    """Add exact lifted-function binding and unpacking ``for`` targets."""

    lifted_functions_by_position: dict[tuple[int, int], A.FuncDef] = {}

    def lower_unpacking_for(self, node: A.For) -> None:
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


_unpacking._PortableLowerer = _PortableLowerer
_unpacking._comprehensions._PortableLowerer = _PortableLowerer
_unpacking._comprehensions._control._PortableLowerer = _PortableLowerer
_unpacking._comprehensions._control._base._PortableLowerer = _PortableLowerer


def compile_portable_source(source: str, filename: str = "<portapy>"):
    parsed = parse_source(source)
    _PortableLowerer.lifted_functions_by_position = {
        _position_key(function): function
        for function in parsed.funcs
        if function.is_lifted
    }
    return _unpacking.compile_portable_source(source, filename)


__all__ = ["PortableFrontendError", "compile_portable_source"]
