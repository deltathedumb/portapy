"""Comprehension layer for the CPython-independent PortaPy frontend."""
from __future__ import annotations

from portapy.parser import ast_nodes as A

from . import portable_frontend_control as _control
from .bytecode import Op


PortableFrontendError = _control.PortableFrontendError


class _PortableLowerer(_control._PortableLowerer):
    """Add eager portable comprehension lowering."""

    def store_comprehension_target(self, var: str, targets: list) -> None:
        if not targets:
            self.store_name(var)
            return
        self.emit(Op.UNPACK_SEQUENCE, len(targets))
        for target in targets:
            if isinstance(target, str):
                self.store_name(target)
            elif isinstance(target, list):
                self.store_comprehension_target("", target)
            else:
                self.unsupported(target, "comprehension target")

    def comprehension_clauses(self, node: A.Comprehension) -> list[tuple]:
        clauses = [(node.var, node.targets, node.iter, node.cond)]
        for var, targets, iterable, condition in zip(
            node.extra_for_vars,
            node.extra_for_targets,
            node.extra_for_iters,
            node.extra_for_conds,
        ):
            clauses.append((var, targets, iterable, condition))
        return clauses

    def lower_comprehension_clauses(
        self,
        clauses: list[tuple],
        index: int,
        emit_value,
    ) -> None:
        var, targets, iterable, condition = clauses[index]
        self.expression(iterable)
        self.emit(Op.GET_ITER)
        start = len(self.instructions)
        exit_jump = self.emit(Op.FOR_ITER)
        self.store_comprehension_target(var, targets)
        condition_jump: int | None = None
        if condition is not None:
            self.expression(condition)
            condition_jump = self.emit(Op.JUMP_IF_FALSE)
        if index + 1 < len(clauses):
            self.lower_comprehension_clauses(clauses, index + 1, emit_value)
        else:
            emit_value()
        loop_back = self.emit(Op.JUMP, start)
        if condition_jump is not None:
            self.patch(condition_jump, loop_back)
        self.patch(exit_jump, len(self.instructions))

    def lower_list_comprehension(self, node: A.Comprehension) -> None:
        result_name = f"__portapy_list_comp_{len(self.instructions)}"
        self.emit(Op.BUILD_LIST, 0)
        self.emit(Op.STORE_NAME, self.name_index(result_name))

        def emit_value() -> None:
            self.emit(Op.LOAD_NAME, self.name_index(result_name))
            self.expression(node.elt)
            self.emit(Op.LIST_APPEND)
            self.emit(Op.STORE_NAME, self.name_index(result_name))

        self.lower_comprehension_clauses(
            self.comprehension_clauses(node), 0, emit_value
        )
        self.emit(Op.LOAD_NAME, self.name_index(result_name))

    def lower_dict_comprehension(self, node: A.DictComprehension) -> None:
        result_name = f"__portapy_dict_comp_{len(self.instructions)}"
        self.emit(Op.BUILD_DICT, 0)
        self.emit(Op.STORE_NAME, self.name_index(result_name))

        self.expression(node.iter)
        self.emit(Op.GET_ITER)
        start = len(self.instructions)
        exit_jump = self.emit(Op.FOR_ITER)
        self.store_comprehension_target(node.var, node.targets)
        condition_jump: int | None = None
        if node.cond is not None:
            self.expression(node.cond)
            condition_jump = self.emit(Op.JUMP_IF_FALSE)
        self.emit(Op.LOAD_NAME, self.name_index(result_name))
        self.expression(node.key)
        self.expression(node.value)
        self.emit(Op.SET_ITEM)
        loop_back = self.emit(Op.JUMP, start)
        if condition_jump is not None:
            self.patch(condition_jump, loop_back)
        self.patch(exit_jump, len(self.instructions))
        self.emit(Op.LOAD_NAME, self.name_index(result_name))

    def expression(self, node: A.Expr) -> None:
        if isinstance(node, A.Comprehension):
            self.lower_list_comprehension(node)
            return
        if isinstance(node, A.DictComprehension):
            self.lower_dict_comprehension(node)
            return
        super().expression(node)


# Every older layer resolves nested lowerers through these module globals.
_control._PortableLowerer = _PortableLowerer
_control._base._PortableLowerer = _PortableLowerer


def compile_portable_source(source: str, filename: str = "<portapy>"):
    return _control.compile_portable_source(source, filename)


__all__ = ["PortableFrontendError", "compile_portable_source"]
