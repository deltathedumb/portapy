"""Preserve ``/`` and ``*`` function-parameter markers in the native parser.

The pinned parser accepts a bare ``*`` but flattens every named parameter into one
list, and it rejects the positional-only ``/`` marker entirely.  Carry two private
sentinel entries through the vendored FuncDef parameter/default arrays, then remove
them while constructing PortaPy's compatibility ``arguments`` node.  This avoids
changing the pinned compiler AST schema while retaining Python's positional-only
and keyword-only partitions and their independent defaults.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/core/native_ast.py")
_PARSER_CLASS = "_npr_parser_Parser"
_FUNCDEF_CLASS = "_npr_ast_nodes_FuncDef"
_ARGUMENT_CLASS = "AstArg"
_POSONLY_MARKER = "__portapy_posonly_marker__"
_KWONLY_MARKER = "__portapy_kwonly_marker__"


_PARSER_BODY = f'''start = self._peek().pos
self._expect("KEYWORD", "def")
name = self._expect("NAME").value
self._expect("OP", "(")
params: list[str] = []
defaults: list[object] = []
param_types: list[object] = []
vararg: str | None = None
kwarg: str | None = None
first = True
posonly_seen = False
keyword_only = False
positional_default_seen = False
kwarg_seen = False
while not self._check("OP", ")"):
    if not first:
        self._expect("OP", ",")
        if self._check("OP", ")"):
            break
    first = False
    if kwarg_seen:
        raise _npr_errors_ParseError("parameter follows **kwargs", self._peek().pos)
    if self._check("OP", "/"):
        if posonly_seen or keyword_only or len(params) == 0:
            raise _npr_errors_ParseError("invalid positional-only marker", self._peek().pos)
        self._eat()
        params.append("{_POSONLY_MARKER}")
        defaults.append(None)
        param_types.append(None)
        posonly_seen = True
        continue
    if self._check("OP", "**"):
        self._eat()
        kwarg = self._expect("NAME").value
        if self._check("OP", ":"):
            self._eat()
            self._parse_type_annotation()
        params.append(kwarg)
        param_types.append(("dict", None))
        defaults.append(None)
        kwarg_seen = True
        continue
    if self._check("OP", "*"):
        self._eat()
        if keyword_only:
            raise _npr_errors_ParseError("duplicate keyword-only marker", self._peek().pos)
        if self._check("NAME"):
            vararg = self._expect("NAME").value
            element_type = None
            if self._check("OP", ":"):
                self._eat()
                inner = self._parse_type_annotation()
                element_type = inner[0] if inner else None
            params.append(vararg)
            param_types.append(("list", element_type))
            defaults.append(None)
        params.append("{_KWONLY_MARKER}")
        param_types.append(None)
        defaults.append(None)
        keyword_only = True
        continue
    parameter_name = self._expect("NAME").value
    params.append(parameter_name)
    annotation = None
    if self._check("OP", ":"):
        self._eat()
        annotation = self._parse_type_annotation()
    param_types.append(annotation)
    default = self._parse_optional_default()
    if not keyword_only:
        if default is None and positional_default_seen:
            raise _npr_errors_ParseError(
                "non-default argument follows default argument",
                self._peek().pos,
            )
        if default is not None:
            positional_default_seen = True
    defaults.append(default)
self._expect("OP", ")")
ret_type = None
if self._check("OP", "->"):
    self._eat()
    ret_type = self._parse_type_annotation()
self._expect("OP", ":")
body = self._parse_block()
asm_body = None
asm_symbol = None
if decorators and self._ASM_DECORATOR in decorators:
    asm_body, asm_symbol = self._extract_asm_body(name, body, start)
return {_FUNCDEF_CLASS}(
    name=name,
    params=params,
    body=body,
    pos=start,
    defaults=defaults,
    param_types=param_types,
    ret_type=ret_type,
    vararg=vararg,
    kwarg=kwarg,
    asm_body=asm_body,
    asm_symbol=asm_symbol,
    decorators=list(decorators) if decorators else [],
    readonly_params=list(self._pending_readonly_params),
)
'''


_BRIDGE_BODY = f'''native_params: list[str] = getattr(node, "params")
native_defaults: list[dict] = getattr(node, "defaults")
posonly_marker = -1
kwonly_marker = -1
marker_index = 0
while marker_index < len(native_params):
    marker_name = native_params[marker_index]
    if marker_name == "{_POSONLY_MARKER}":
        posonly_marker = marker_index
    elif marker_name == "{_KWONLY_MARKER}":
        kwonly_marker = marker_index
    marker_index += 1
positional_only: list[{_ARGUMENT_CLASS}] = []
regular: list[{_ARGUMENT_CLASS}] = []
keyword_only: list[{_ARGUMENT_CLASS}] = []
defaults: list[dict] = []
keyword_defaults: list[dict] = []
vararg_name = getattr(node, "vararg")
kwarg_name = getattr(node, "kwarg")
parameter_index = 0
while parameter_index < len(native_params):
    parameter_name = native_params[parameter_index]
    if (
        parameter_name != "{_POSONLY_MARKER}"
        and parameter_name != "{_KWONLY_MARKER}"
        and parameter_name != vararg_name
        and parameter_name != kwarg_name
    ):
        parameter = {_ARGUMENT_CLASS}(parameter_name)
        default_node: dict = native_defaults[parameter_index]
        if kwonly_marker >= 0 and parameter_index > kwonly_marker:
            keyword_only.append(parameter)
            if default_node is None:
                keyword_defaults.append(None)
            else:
                converted_keyword_default: dict = _convert_expr(default_node, lifted)
                keyword_defaults.append(converted_keyword_default)
        else:
            if posonly_marker >= 0 and parameter_index < posonly_marker:
                positional_only.append(parameter)
            else:
                regular.append(parameter)
            if default_node is not None:
                converted_default: dict = _convert_expr(default_node, lifted)
                defaults.append(converted_default)
    parameter_index += 1
vararg_node = None
if vararg_name is not None:
    vararg_node = {_ARGUMENT_CLASS}(vararg_name)
kwarg_node = None
if kwarg_name is not None:
    kwarg_node = {_ARGUMENT_CLASS}(kwarg_name)
return arguments(
    positional_only,
    regular,
    vararg_node,
    keyword_only,
    keyword_defaults,
    kwarg_node,
    defaults,
)
'''


def _parser_method(module: ast.Module) -> ast.FunctionDef:
    classes = [
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == _PARSER_CLASS
    ]
    if len(classes) != 1:
        raise RuntimeError(
            f"native parameter markers expected one parser class, found {len(classes)}"
        )
    methods = [
        node
        for node in classes[0].body
        if isinstance(node, ast.FunctionDef) and node.name == "_parse_funcdef"
    ]
    if len(methods) != 1:
        raise RuntimeError(
            f"native parameter markers expected one function parser, found {len(methods)}"
        )
    return methods[0]


def _bridge_function(module: ast.Module) -> ast.FunctionDef:
    functions = [
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "_convert_arguments"
    ]
    if len(functions) != 1:
        raise RuntimeError(
            f"native parameter markers expected one argument bridge, found {len(functions)}"
        )
    return functions[0]


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"), filename=str(PATH))
    parser = _parser_method(module)
    bridge = _bridge_function(module)

    parser_text = ast.unparse(parser)
    bridge_text = ast.unparse(bridge)
    if _POSONLY_MARKER in parser_text or _KWONLY_MARKER in parser_text:
        raise RuntimeError("native function parser already carries parameter markers")
    if "self._check('OP', '/')" in parser_text:
        raise RuntimeError("native function parser has an unknown slash implementation")
    if "return arguments([], all_args" not in bridge_text:
        raise RuntimeError("native argument bridge no longer has the flattened source shape")

    parser.body = ast.parse(_PARSER_BODY).body
    bridge.body = ast.parse(_BRIDGE_BODY).body

    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    verified = ast.parse(source, filename=str(PATH))
    parser_text = ast.unparse(_parser_method(verified))
    bridge_text = ast.unparse(_bridge_function(verified))
    parser_required = (
        "self._check('OP', '/')",
        f"params.append('{_POSONLY_MARKER}')",
        f"params.append('{_KWONLY_MARKER}')",
        "keyword_only = True",
        "positional_default_seen = True",
    )
    bridge_required = (
        f"parameter_name != '{_POSONLY_MARKER}'",
        f"parameter_name != '{_KWONLY_MARKER}'",
        "positional_only.append(parameter)",
        "keyword_only.append(parameter)",
        "keyword_defaults.append(None)",
        "return arguments(positional_only, regular, vararg_node, keyword_only",
    )
    missing = [
        marker
        for marker in (*parser_required, *bridge_required)
        if marker not in parser_text and marker not in bridge_text
    ]
    if missing:
        raise RuntimeError(f"native parameter marker repair was lost: {missing}")
    forbidden = (
        "return arguments([], all_args",
        "self._parse_param(params, defaults, param_types)",
    )
    remaining = [
        marker
        for marker in forbidden
        if marker in parser_text or marker in bridge_text
    ]
    if remaining:
        raise RuntimeError(f"flattened parameter handling remains: {remaining}")

    print("NORMALIZED NATIVE PARAMETER MARKERS", 1, 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
