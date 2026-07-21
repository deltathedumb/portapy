"""Loop-target layer for the standalone PortaPy frontend."""
from __future__ import annotations

from portapy.parser import ast_nodes as A

from . import portable_frontend_unpacking as _unpacking
from .bytecode import Op


PortableFrontendError = _unpacking.PortableFrontendError


class _PortableLowerer(_unpacking._PortableLowerer):
    """Add tuple and nested-unpack targets to ordinary ``for`` loops."""

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
        if isinstance(node, A.For) and node.targets:
            self.lower_unpacking_for(node)
            return
        super().statement(node)


_unpacking._PortableLowerer = _PortableLowerer
_unpacking._comprehensions._PortableLowerer = _PortableLowerer
_unpacking._comprehensions._control._PortableLowerer = _PortableLowerer
_unpacking._comprehensions._control._base._PortableLowerer = _PortableLowerer


def compile_portable_source(source: str, filename: str = "<portapy>"):
    return _unpacking.compile_portable_source(source, filename)


__all__ = ["PortableFrontendError", "compile_portable_source"]
