"""Variadic and unpacking layer for the standalone PortaPy frontend."""
from __future__ import annotations

from portapy.parser import ast_nodes as A

from . import portable_frontend_comprehensions as _comprehensions
from .bytecode import CodeObject, Op


PortableFrontendError = _comprehensions.PortableFrontendError


class _PortableLowerer(_comprehensions._PortableLowerer):
    """Add PEP 448 unpacking and variadic function signatures."""

    def fixed_signature(self, node: A.FuncDef) -> tuple[list[str], list]:
        params = list(node.params)
        defaults = list(node.defaults)
        if len(defaults) < len(params):
            defaults += [None] * (len(params) - len(defaults))
        dynamic = {name for name in (node.vararg, node.kwarg) if name is not None}
        fixed_params: list[str] = []
        fixed_defaults: list = []
        for name, default in zip(params, defaults):
            if name in dynamic:
                continue
            fixed_params.append(name)
            fixed_defaults.append(default)
        return fixed_params, fixed_defaults

    def compile_function_code(self, node: A.FuncDef) -> CodeObject:
        cache_key = id(node)
        cached = self.function_code_cache.get(cache_key)
        if cached is not None:
            return cached
        fixed_params, _defaults = self.fixed_signature(node)
        nested = _PortableLowerer(node.name, fixed_params)
        nested.vararg_name = node.vararg
        nested.kwarg_name = node.kwarg
        nested.free_names = set(getattr(node, "free_vars", []) or [])
        for statement in node.body:
            nested.statement(statement)
        nested.emit(Op.RETURN)
        code = nested.finish()
        self.function_code_cache[cache_key] = code
        return code

    def emit_function(self, node: A.FuncDef, store_as: str | None = None) -> None:
        function_code = self.compile_function_code(node)
        _fixed_params, defaults = self.fixed_signature(node)
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
        self.store_name(store_as or node.name)

    def call(
        self,
        args: list[A.Expr],
        kwargs: list,
        dstar: A.Expr | None = None,
    ) -> None:
        has_starred = any(isinstance(argument, A.Starred) for argument in args)
        if not has_starred and not kwargs and dstar is None:
            for argument in args:
                self.expression(argument)
            self.emit(Op.CALL, len(args))
            return

        positional_spec: list[bool] = []
        for argument in args:
            if isinstance(argument, A.Starred):
                self.expression(argument.value)
                positional_spec.append(True)
            else:
                self.expression(argument)
                positional_spec.append(False)
        keyword_names: list[str | None] = []
        for item in kwargs:
            if not isinstance(item, tuple) or len(item) != 2:
                self.unsupported(item, "malformed keyword argument")
            name, value = item
            self.expression(value)
            keyword_names.append(name)
        if dstar is not None:
            self.expression(dstar)
            keyword_names.append(None)
        self.emit(
            Op.CALL_KW,
            self.constant((tuple(positional_spec), tuple(keyword_names))),
        )

    def expression(self, node: A.Expr) -> None:
        if isinstance(node, (A.ListLit, A.TupleLit, A.SetLit)) and any(
            isinstance(element, A.Starred) for element in node.elems
        ):
            flags = 0
            for index, element in enumerate(node.elems):
                if isinstance(element, A.Starred):
                    flags |= 1 << index
                    self.expression(element.value)
                else:
                    self.expression(element)
            opcode = (
                Op.BUILD_LIST_UNPACK
                if isinstance(node, A.ListLit)
                else Op.BUILD_TUPLE_UNPACK
                if isinstance(node, A.TupleLit)
                else Op.BUILD_SET_UNPACK
            )
            self.emit(opcode, len(node.elems) | (flags << 16))
            return
        if isinstance(node, A.DictLit) and any(key is None for key in node.keys):
            flags = 0
            for index, (key, value) in enumerate(zip(node.keys, node.values)):
                if key is None:
                    flags |= 1 << index
                    self.expression(value)
                else:
                    self.expression(key)
                    self.expression(value)
                    self.emit(Op.BUILD_TUPLE, 2)
            self.emit(Op.BUILD_DICT_UNPACK, len(node.keys) | (flags << 16))
            return
        super().expression(node)

    def finish(self) -> CodeObject:
        code = CodeObject(
            name=self.name,
            instructions=self.instructions,
            constants=self.constants,
            names=self.names,
            arg_names=self.arg_names,
            vararg_name=getattr(self, "vararg_name", None),
            kwarg_name=getattr(self, "kwarg_name", None),
            is_generator=getattr(self, "is_generator", False),
            free_names=sorted(getattr(self, "free_names", set())),
        )
        code.validate()
        return code


_comprehensions._PortableLowerer = _PortableLowerer
_comprehensions._control._PortableLowerer = _PortableLowerer
_comprehensions._control._base._PortableLowerer = _PortableLowerer


def compile_portable_source(source: str, filename: str = "<portapy>"):
    return _comprehensions.compile_portable_source(source, filename)


__all__ = ["PortableFrontendError", "compile_portable_source"]
