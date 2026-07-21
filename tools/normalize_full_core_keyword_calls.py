"""Restore ordinary keyword calls in the native parser and VM object model."""
from __future__ import annotations

from pathlib import Path


CORE = Path("src/portapy/core")
PARSER_RUNTIME_PATH = CORE / "native_parser_runtime.py"
NATIVE_AST_PATH = CORE / "native_ast.py"
VM_PATH = CORE / "vm.py"


def _replace_method(
    source: str,
    signature: str,
    replacement: str,
    *,
    next_signature: str,
    label: str,
) -> str:
    start = source.find(signature)
    if start < 0:
        raise RuntimeError(f"{label}: method start not found")
    end = source.find(next_signature, start + len(signature))
    if end < 0:
        raise RuntimeError(f"{label}: next method not found")
    print("REPLACED", label, 1)
    return source[:start] + replacement + source[end:]


def _normalize_parser_runtime() -> None:
    source = PARSER_RUNTIME_PATH.read_text(encoding="utf-8")
    anchor = "class _npr_parser_Parser:\n"
    if source.count(anchor) != 1:
        raise RuntimeError("private parser class anchor is not unique")
    keyword_node = '''class _full_core_parser_KeywordArgument:
    def __init__(self, name: str, value: object) -> None:
        self.name = name
        self.value = value


'''
    source = source.replace(anchor, keyword_node + anchor, 1)
    source = _replace_method(
        source,
        "    def _parse_call_args(self):",
        '''    def _parse_call_args(self):
        args: list[object] = []
        kwargs: list[_full_core_parser_KeywordArgument] = []
        while not self._check('OP', ')'):
            if (
                self._check('NAME')
                and self._peek(1).kind == 'OP'
                and self._peek(1).value == '='
            ):
                name = self._eat().value
                self._eat()
                value = self._parse_expr()
                kwargs.append(_full_core_parser_KeywordArgument(name, value))
            else:
                if len(kwargs) > 0:
                    raise _npr_errors_ParseError(
                        'positional argument follows keyword argument',
                        self._peek().pos,
                    )
                value = self._parse_expr()
                args.append(value)
            if not self._check('OP', ','):
                break
            self._eat()
        return (args, kwargs)
''',
        next_signature="\n    def _parse_tuple_rhs(self):",
        label="keyword call arguments",
    )
    PARSER_RUNTIME_PATH.write_text(source, encoding="utf-8")


def _normalize_native_ast() -> None:
    source = NATIVE_AST_PATH.read_text(encoding="utf-8")
    old_call = '''    if isinstance(node, _npr_ast_nodes_Call):
        keys = [keyword(name, _convert_expr(value, lifted)) for name, value in node.kwargs or []]
        if node.dstar is not None:
            keys.append(keyword(None, _convert_expr(node.dstar, lifted)))
        return Call(Name(node.func), [_convert_expr(value, lifted) for value in node.args], keys)
    if isinstance(node, _npr_ast_nodes_MethodCall):
        keys = [keyword(name, _convert_expr(value, lifted)) for name, value in node.kwargs or []]
        return Call(Attribute(_convert_expr(node.obj, lifted), node.method), [_convert_expr(value, lifted) for value in node.args], keys)
'''
    new_call = '''    if isinstance(node, _npr_ast_nodes_Call):
        keys: list[keyword] = []
        for item in node.kwargs:
            keys.append(keyword(item.name, _convert_expr(item.value, lifted)))
        if node.dstar is not None:
            keys.append(keyword(None, _convert_expr(node.dstar, lifted)))
        return Call(Name(node.func), [_convert_expr(value, lifted) for value in node.args], keys)
    if isinstance(node, _npr_ast_nodes_MethodCall):
        keys: list[keyword] = []
        for item in node.kwargs:
            keys.append(keyword(item.name, _convert_expr(item.value, lifted)))
        return Call(Attribute(_convert_expr(node.obj, lifted), node.method), [_convert_expr(value, lifted) for value in node.args], keys)
'''
    count = source.count(old_call)
    if count != 1:
        raise RuntimeError(f"native AST keyword conversion: expected 1 match, found {count}")
    NATIVE_AST_PATH.write_text(source.replace(old_call, new_call, 1), encoding="utf-8")
    print("REPLACED native AST keyword conversion", count)


def _normalize_vm() -> None:
    source = VM_PATH.read_text(encoding="utf-8")
    anchor = '''        if getattr(target, "__qualname__", "") == "object.__init__":
            return None
        if isinstance(target, Function):
'''
    replacement = '''        if getattr(target, "__qualname__", "") == "object.__init__":
            return None
        if isinstance(target, BoundMethod):
            bound_args: list[object] = [target.instance]
            for argument in args:
                bound_args.append(argument)
            return self._call(target.function, bound_args, kwargs)
        if isinstance(target, PyClass):
            instance = PyInstance(target)
            try:
                initializer = target.lookup("__init__")
            except AttributeError:
                initializer = None
            if isinstance(initializer, Function):
                initializer_args: list[object] = [instance]
                for argument in args:
                    initializer_args.append(argument)
                self._call(initializer, initializer_args, kwargs)
            return instance
        if isinstance(target, Function):
'''
    count = source.count(anchor)
    if count != 1:
        raise RuntimeError(f"native keyword object dispatch: expected 1 match, found {count}")
    VM_PATH.write_text(source.replace(anchor, replacement, 1), encoding="utf-8")
    print("RESTORED NATIVE KEYWORD OBJECT DISPATCH", count)


def main() -> int:
    _normalize_parser_runtime()
    _normalize_native_ast()
    _normalize_vm()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
