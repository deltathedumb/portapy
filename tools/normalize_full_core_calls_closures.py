"""Restore positional calls and native-safe closure discovery to the full core."""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/native_parser_runtime.py")


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


_HELPERS = '''def _full_core_parser_add_name(result: list[str], name: str) -> None:
    if name not in result:
        result.append(name)


def _full_core_parser_collect_expr_names(node: object, result: list[str]) -> None:
    if isinstance(node, _npr_ast_nodes_Name):
        _full_core_parser_add_name(result, node.name)
    elif isinstance(node, _npr_ast_nodes_BinOp):
        _full_core_parser_collect_expr_names(node.left, result)
        _full_core_parser_collect_expr_names(node.right, result)
    elif isinstance(node, _npr_ast_nodes_UnaryOp):
        _full_core_parser_collect_expr_names(node.operand, result)
    elif isinstance(node, _npr_ast_nodes_BoolOp):
        _full_core_parser_collect_expr_names(node.left, result)
        _full_core_parser_collect_expr_names(node.right, result)
    elif isinstance(node, _npr_ast_nodes_Compare):
        for operand in node.operands:
            _full_core_parser_collect_expr_names(operand, result)
    elif isinstance(node, _npr_ast_nodes_IfExp):
        _full_core_parser_collect_expr_names(node.test, result)
        _full_core_parser_collect_expr_names(node.body, result)
        _full_core_parser_collect_expr_names(node.orelse, result)
    elif isinstance(node, _npr_ast_nodes_Call):
        _full_core_parser_add_name(result, node.func)
        for argument in node.args:
            _full_core_parser_collect_expr_names(argument, result)
    elif isinstance(node, _npr_ast_nodes_MethodCall):
        _full_core_parser_collect_expr_names(node.obj, result)
        for argument in node.args:
            _full_core_parser_collect_expr_names(argument, result)
    elif isinstance(node, _npr_ast_nodes_Attr):
        _full_core_parser_collect_expr_names(node.obj, result)
    elif isinstance(node, _npr_ast_nodes_Subscript):
        _full_core_parser_collect_expr_names(node.obj, result)
        _full_core_parser_collect_expr_names(node.index, result)
    elif isinstance(node, _npr_ast_nodes_ListLit):
        for item in node.elems:
            _full_core_parser_collect_expr_names(item, result)
    elif isinstance(node, _npr_ast_nodes_TupleLit):
        for item in node.elems:
            _full_core_parser_collect_expr_names(item, result)
    elif isinstance(node, _npr_ast_nodes_DictLit):
        for item in node.keys:
            if item is not None:
                _full_core_parser_collect_expr_names(item, result)
        for item in node.values:
            _full_core_parser_collect_expr_names(item, result)


'''


_FREE_VARS = '''    def _find_free_vars(self, fdef: _npr_ast_nodes_FuncDef) -> tuple:
        local_names: list[str] = list(fdef.params)
        if fdef.vararg is not None:
            _full_core_parser_add_name(local_names, fdef.vararg)
        if fdef.kwarg is not None:
            _full_core_parser_add_name(local_names, fdef.kwarg)
        referenced: list[str] = []
        for statement in fdef.body:
            if isinstance(statement, _npr_ast_nodes_Assign):
                _full_core_parser_add_name(local_names, statement.target)
                _full_core_parser_collect_expr_names(statement.value, referenced)
            elif isinstance(statement, _npr_ast_nodes_AugAssign):
                _full_core_parser_add_name(local_names, statement.target)
                _full_core_parser_collect_expr_names(statement.value, referenced)
            elif isinstance(statement, _npr_ast_nodes_Return):
                if statement.value is not None:
                    _full_core_parser_collect_expr_names(statement.value, referenced)
            elif isinstance(statement, _npr_ast_nodes_ExprStmt):
                _full_core_parser_collect_expr_names(statement.expr, referenced)
            elif isinstance(statement, _npr_ast_nodes_ClosureBind):
                _full_core_parser_add_name(local_names, statement.func_name)
        free_vars: list[str] = []
        for name in referenced:
            if name not in local_names:
                _full_core_parser_add_name(free_vars, name)
        return (free_vars, [])
'''


_CALL_ARGS = '''    def _parse_call_args(self):
        args: list = []
        kwargs: list = []
        if self._check('OP', ')'):
            return (args, kwargs)
        while True:
            if self._check('NAME') and self._peek(1).kind == 'OP' and (self._peek(1).value == '='):
                name = self._eat().value
                self._eat()
                kwargs.append((name, self._parse_expr()))
            elif self._check('OP', '**'):
                star_pos = self._eat().pos
                args.append(_npr_ast_nodes_DoubleStarred(value=self._parse_expr(), pos=star_pos))
            else:
                if kwargs:
                    raise _npr_errors_ParseError('positional argument follows keyword argument', self._peek().pos)
                if self._check('OP', '*'):
                    star_pos = self._eat().pos
                    args.append(_npr_ast_nodes_Starred(value=self._parse_expr(), pos=star_pos))
                else:
                    arg = self._parse_expr()
                    if self._check('KEYWORD', 'for'):
                        arg = self._parse_comprehension_tail(arg, arg.pos)
                    args.append(arg)
            if not self._check('OP', ','):
                break
            self._eat()
            if self._check('OP', ')'):
                break
        return (args, kwargs)
'''


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    anchor = "class _npr_parser_Parser:\n"
    if source.count(anchor) != 1:
        raise RuntimeError("private parser class anchor is not unique")
    source = source.replace(anchor, _HELPERS + anchor, 1)
    source = _replace_method(
        source,
        "    def _find_free_vars(",
        _FREE_VARS,
        next_signature="\n    def parse(",
        label="native closure discovery",
    )
    source = _replace_method(
        source,
        "    def _parse_call_args(self):",
        _CALL_ARGS,
        next_signature="\n    def _parse_tuple_rhs(self):",
        label="positional call arguments",
    )
    PATH.write_text(source, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
