"""Extended CPython-independent PortaPy frontend.

The first standalone lowering slices live in :mod:`portable_frontend_base`.
This module layers control-flow semantics that need explicit VM coordination on
top while keeping the public import path stable.
"""
from __future__ import annotations

from portapy.parser import ast_nodes as A
from portapy.parser import parse_source

from . import portable_frontend_base as _base
from .bytecode import CodeObject, Op


PortableFrontendError = _base.PortableFrontendError


class _PortableLowerer(_base._PortableLowerer):
    """Add exceptions, generators, and pattern matching to the lowerer."""

    def exception_spec(self, names: list[str]) -> object:
        """Build the VM's compact named-value specification."""
        specs: list[object] = []
        for name in names:
            pieces = name.split(".")
            spec: object = self.name_index(pieces[0])
            for piece in pieces[1:]:
                spec = ("attr", spec, piece)
            specs.append(spec)
        if len(specs) == 1:
            return specs[0]
        return tuple(specs)

    def value_spec(self, node: A.Expr) -> object:
        """Encode a match value for runtime resolution."""
        if isinstance(node, A.IntLit):
            if node.is_none:
                value: object = None
            elif node.is_bool:
                value = bool(node.value)
            else:
                value = node.value
            return ("literal", value)
        if isinstance(node, A.FloatLit):
            return ("literal", node.value)
        if isinstance(node, A.StrLit):
            return ("literal", node.value)
        if isinstance(node, A.Name):
            return self.name_index(node.name)
        if isinstance(node, A.Attr):
            pieces: list[str] = []
            current: A.Expr = node
            while isinstance(current, A.Attr):
                pieces.append(current.name)
                current = current.obj
            if isinstance(current, A.Name):
                spec: object = self.name_index(current.name)
                for piece in reversed(pieces):
                    spec = ("attr", spec, piece)
                return spec
        nested = _PortableLowerer(f"{self.name}.<pattern-value>")
        nested.expression(node)
        nested.emit(Op.RETURN)
        return ("expr", nested.finish())

    def pattern_spec(self, pattern: A.Pattern) -> object:
        if isinstance(pattern, A.MatchValue):
            return ("value", self.value_spec(pattern.value))
        if isinstance(pattern, A.MatchCapture):
            if pattern.name == "_":
                return ("wildcard",)
            return ("bind", None, pattern.name)
        if isinstance(pattern, A.MatchOr):
            return ("or", tuple(self.pattern_spec(item) for item in pattern.patterns))
        if isinstance(pattern, A.MatchSequence):
            items: list[object] = []
            for index, item in enumerate(pattern.patterns):
                item_spec = self.pattern_spec(item)
                if pattern.star_index == index:
                    item_spec = ("star", item_spec)
                items.append(item_spec)
            return ("sequence", tuple(items))
        if isinstance(pattern, A.MatchClass):
            cls_spec = self.exception_spec([pattern.cls_name])
            positional = tuple(self.pattern_spec(item) for item in pattern.positional)
            keywords = tuple(
                (name, self.pattern_spec(item)) for name, item in pattern.kwargs
            )
            return ("class", cls_spec, positional, keywords)
        if isinstance(pattern, A.MatchAs):
            inner = self.pattern_spec(pattern.pattern) if pattern.pattern is not None else None
            return ("bind", inner, pattern.name)
        if isinstance(pattern, A.MatchMapping):
            pairs = tuple(
                (("literal", key), self.pattern_spec(item))
                for key, item in zip(pattern.keys, pattern.patterns)
            )
            return ("mapping", pairs, None)
        self.unsupported(pattern, "match pattern")
        return ("wildcard",)

    def lower_match(self, node: A.Match) -> None:
        subject_name = f"__portapy_match_{len(self.instructions)}"
        self.expression(node.subject)
        self.emit(Op.STORE_NAME, self.name_index(subject_name))
        end_jumps: list[int] = []
        for pattern, guard, body in node.cases:
            self.emit(Op.LOAD_NAME, self.name_index(subject_name))
            self.emit(Op.MATCH_PATTERN, self.constant(self.pattern_spec(pattern)))
            next_case = self.emit(Op.JUMP_IF_FALSE)
            guard_jump: int | None = None
            if guard is not None:
                self.expression(guard)
                guard_jump = self.emit(Op.JUMP_IF_FALSE)
            for statement in body:
                self.statement(statement)
            end_jumps.append(self.emit(Op.JUMP))
            next_offset = len(self.instructions)
            self.patch(next_case, next_offset)
            if guard_jump is not None:
                self.patch(guard_jump, next_offset)
        end = len(self.instructions)
        for jump in end_jumps:
            self.patch(jump, end)

    def lower_try(self, node: A.Try) -> None:
        handlers = [
            (node.handler_types, node.bind_name, node.handler),
            *node.extra_handlers,
        ]
        if not node.handler and not node.handler_types and node.bind_name is None:
            handlers = list(node.extra_handlers)

        if not handlers:
            handler_jump = self.emit(Op.TRY_BEGIN)
            for statement in node.body:
                self.statement(statement)
            self.emit(Op.TRY_END)
            for statement in node.finally_body:
                self.statement(statement)
            normal_jump = self.emit(Op.JUMP)
            self.patch(handler_jump, len(self.instructions))
            for statement in node.finally_body:
                self.statement(statement)
            self.emit(Op.RAISE)
            self.patch(normal_jump, len(self.instructions))
            return

        handler_jump = self.emit(Op.TRY_BEGIN)
        for statement in node.body:
            self.statement(statement)
        self.emit(Op.TRY_END)
        for statement in node.else_body:
            self.statement(statement)
        for statement in node.finally_body:
            self.statement(statement)
        normal_jump = self.emit(Op.JUMP)
        self.patch(handler_jump, len(self.instructions))

        end_jumps: list[int] = []
        for types, bind_name, body in handlers:
            next_handler: int | None = None
            if types:
                self.emit(
                    Op.MATCH_EXCEPTION_CHECK,
                    self.constant(self.exception_spec(types)),
                )
                next_handler = self.emit(Op.JUMP_IF_FALSE)
            if bind_name:
                self.store_name(bind_name)
            else:
                self.emit(Op.POP_TOP)
            for statement in body:
                self.statement(statement)
            for statement in node.finally_body:
                self.statement(statement)
            end_jumps.append(self.emit(Op.JUMP))
            if next_handler is not None:
                self.patch(next_handler, len(self.instructions))

        self.emit(Op.RAISE)
        end = len(self.instructions)
        self.patch(normal_jump, end)
        for jump in end_jumps:
            self.patch(jump, end)

    def statement(self, node: A.Stmt) -> None:
        if isinstance(node, A.Match):
            self.lower_match(node)
            return
        if isinstance(node, A.Try):
            self.lower_try(node)
            return
        if isinstance(node, A.YieldStmt):
            self.expression(node.value)
            self.emit(Op.YIELD_VALUE)
            self.is_generator = True
            return
        super().statement(node)

    def finish(self) -> CodeObject:
        code = CodeObject(
            name=self.name,
            instructions=self.instructions,
            constants=self.constants,
            names=self.names,
            arg_names=self.arg_names,
            is_generator=getattr(self, "is_generator", False),
        )
        code.validate()
        return code


# Base methods create nested lowerers through their module-global class name.
# Rebind it so functions, lambdas, class methods, and nested code all receive
# the extended control-flow implementation without duplicating the base file.
_base._PortableLowerer = _PortableLowerer


def compile_portable_source(
    source: str,
    filename: str = "<portapy>",
) -> CodeObject:
    """Parse and lower source without importing CPython's :mod:`ast`."""
    module = parse_source(source)
    lowerer = _PortableLowerer(filename)
    for class_definition in module.classes:
        lowerer.class_definition(class_definition)
    for function in module.funcs:
        lowerer.function(function)
    for statement in module.body:
        lowerer.statement(statement)
    return lowerer.finish()


__all__ = ["PortableFrontendError", "compile_portable_source"]
