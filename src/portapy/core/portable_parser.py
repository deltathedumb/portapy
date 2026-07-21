"""Portable-only parser extensions for coroutine syntax.

The shared asmpython parser intentionally remains unchanged.  This subclass
adds the Python syntax needed by PortaPy's standalone bytecode VM while still
using PortaPy's own lexer, parser, and AST carriers rather than host ``ast``.
"""
from __future__ import annotations

from portapy.parser import ast_nodes as A
from portapy.parser.errors import ErrorCode, ParseError
from portapy.parser.lexer import Lexer
from portapy.parser.parser import Parser


class PortableParser(Parser):
    """Add ``async def`` and ``await`` to the PortaPy-owned parser."""

    def __init__(self, tokens: list, active_extensions=None) -> None:
        super().__init__(tokens, active_extensions=active_extensions)
        self._async_function_context: list[bool] = []

    def _at_async_def(self) -> bool:
        if self.i + 1 >= len(self.toks):
            return False
        token = self._peek()
        following = self._peek(1)
        return (
            token.kind == "KEYWORD"
            and token.value == "async"
            and following.kind == "KEYWORD"
            and following.value == "def"
        )

    def _check(self, kind: str, value: str = None) -> bool:
        # Existing top-level and class-body dispatch asks whether the current
        # token is ``def`` before calling _parse_funcdef. Treat ``async def``
        # as that same shape; _parse_funcdef consumes the leading ``async``.
        if kind == "KEYWORD" and value == "def" and self._at_async_def():
            return True
        return super()._check(kind, value)

    def _parse_funcdef(self, decorators=None):
        is_async = self._at_async_def()
        if is_async:
            self._eat()  # async
        self._async_function_context.append(is_async)
        try:
            function = super()._parse_funcdef(decorators=decorators)
        finally:
            self._async_function_context.pop()
        # FuncDef is deliberately a dumb, non-slotted data carrier. PortaPy's
        # final lowering layer consumes this portable-only marker; the shared
        # asmpython parser and semantic pipeline remain unchanged.
        function.is_async = is_async
        return function

    def _parse_stmt(self):
        # Nested async functions need the same lifting and closure metadata as
        # the shared parser's nested ordinary-def path.
        if self._at_async_def():
            function = self._parse_funcdef(decorators=None)
            function.is_lifted = True
            free_vars, nonlocal_vars = self._find_free_vars(function)
            function.free_vars = free_vars
            function.nonlocal_vars = nonlocal_vars
            self._nested_funcs.append(function)
            if free_vars:
                return A.ClosureBind(
                    func_name=function.name,
                    free_vars=free_vars,
                    nonlocal_vars=nonlocal_vars,
                    pos=function.pos,
                )
            return A.Pass(pos=function.pos)
        return super()._parse_stmt()

    def _parse_unary(self):
        if self._peek().kind == "KEYWORD" and self._peek().value == "await":
            token = self._eat()
            if not self._async_function_context or not self._async_function_context[-1]:
                raise ParseError(
                    "'await' outside async function",
                    token.pos,
                    ErrorCode.P_UNEXPECTED_TOKEN,
                )
            return A.UnaryOp(
                op="await",
                operand=self._parse_unary(),
                pos=token.pos,
            )
        return super()._parse_unary()


def parse_portable_source(source: str) -> A.Module:
    return PortableParser(Lexer(source).tokenize()).parse()


__all__ = ["PortableParser", "parse_portable_source"]
