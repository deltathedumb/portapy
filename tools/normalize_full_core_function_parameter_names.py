"""Preserve function and lambda parameter names through native lowering.

The pinned compiler treats ``arg.arg`` inside comprehensions as an opaque
attribute and materializes null list elements. Those nulls become
``CodeObject.arg_names`` entries and later crash dictionary hashing during
function argument binding. Replace every function/lambda parameter-name
comprehension and conditional attribute expression with explicitly typed
string loops.
"""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/frontend.py")

_FUNCTION_ARGUMENTS_OLD = '''            function_arguments = list(node.args.posonlyargs)
            for argument in node.args.args:
                function_arguments.append(argument)
            nested = _Lowerer(node.name, [arg.arg for arg in function_arguments])
'''

_FUNCTION_ARGUMENTS_NEW = '''            function_arguments = list(node.args.posonlyargs)
            for argument in node.args.args:
                function_arguments.append(argument)
            function_argument_names: list[str] = []
            for argument in function_arguments:
                function_argument_name: str = argument.arg
                function_argument_names.append(function_argument_name)
            nested = _Lowerer(node.name, function_argument_names)
'''

_LAMBDA_ARGUMENTS_OLD = '''            lambda_arguments = list(node.args.posonlyargs)
            for argument in node.args.args:
                lambda_arguments.append(argument)
            nested = _Lowerer("<lambda>", [arg.arg for arg in lambda_arguments])
'''

_LAMBDA_ARGUMENTS_NEW = '''            lambda_arguments = list(node.args.posonlyargs)
            for argument in node.args.args:
                lambda_arguments.append(argument)
            lambda_argument_names: list[str] = []
            for argument in lambda_arguments:
                lambda_argument_name: str = argument.arg
                lambda_argument_names.append(lambda_argument_name)
            nested = _Lowerer("<lambda>", lambda_argument_names)
'''

_SPECIAL_OLD = '''            nested.posonly_names = [arg.arg for arg in node.args.posonlyargs]
            nested.kwonly_names = [arg.arg for arg in node.args.kwonlyargs]
            nested.vararg_name = node.args.vararg.arg if node.args.vararg else None
            nested.kwarg_name = node.args.kwarg.arg if node.args.kwarg else None
'''

_SPECIAL_NEW = '''            positional_only_names: list[str] = []
            for argument in node.args.posonlyargs:
                positional_only_name: str = argument.arg
                positional_only_names.append(positional_only_name)
            nested.posonly_names = positional_only_names
            keyword_only_names: list[str] = []
            for argument in node.args.kwonlyargs:
                keyword_only_name: str = argument.arg
                keyword_only_names.append(keyword_only_name)
            nested.kwonly_names = keyword_only_names
            if node.args.vararg is not None:
                variadic_positional_name: str = node.args.vararg.arg
                nested.vararg_name = variadic_positional_name
            else:
                nested.vararg_name = None
            if node.args.kwarg is not None:
                variadic_keyword_name: str = node.args.kwarg.arg
                nested.kwarg_name = variadic_keyword_name
            else:
                nested.kwarg_name = None
'''


def _state(
    source: str,
    old: str,
    new: str,
    label: str,
    expected: int,
) -> str:
    old_count = source.count(old)
    new_count = source.count(new)
    if old_count == expected and new_count == 0:
        return "original"
    if old_count == 0 and new_count == expected:
        return "normalized"
    raise RuntimeError(
        f"native {label} parameter source shape changed: "
        f"old={old_count}, normalized={new_count}, expected={expected}"
    )


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    function_state = _state(
        source,
        _FUNCTION_ARGUMENTS_OLD,
        _FUNCTION_ARGUMENTS_NEW,
        "function regular",
        1,
    )
    lambda_state = _state(
        source,
        _LAMBDA_ARGUMENTS_OLD,
        _LAMBDA_ARGUMENTS_NEW,
        "lambda regular",
        1,
    )
    special_state = _state(
        source,
        _SPECIAL_OLD,
        _SPECIAL_NEW,
        "function/lambda special",
        2,
    )

    function_count = 0
    lambda_count = 0
    special_count = 0
    if function_state == "original":
        source = source.replace(_FUNCTION_ARGUMENTS_OLD, _FUNCTION_ARGUMENTS_NEW, 1)
        function_count = 1
    if lambda_state == "original":
        source = source.replace(_LAMBDA_ARGUMENTS_OLD, _LAMBDA_ARGUMENTS_NEW, 1)
        lambda_count = 1
    if special_state == "original":
        source = source.replace(_SPECIAL_OLD, _SPECIAL_NEW)
        special_count = 2
    PATH.write_text(source, encoding="utf-8")

    required = (
        "function_argument_name: str = argument.arg",
        "nested = _Lowerer(node.name, function_argument_names)",
        "lambda_argument_name: str = argument.arg",
        'nested = _Lowerer("<lambda>", lambda_argument_names)',
        "positional_only_name: str = argument.arg",
        "keyword_only_name: str = argument.arg",
        "variadic_positional_name: str = node.args.vararg.arg",
        "variadic_keyword_name: str = node.args.kwarg.arg",
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        raise RuntimeError(f"native function parameter validation failed: {missing}")
    forbidden = (
        _FUNCTION_ARGUMENTS_OLD,
        _LAMBDA_ARGUMENTS_OLD,
        _SPECIAL_OLD,
    )
    remaining = [marker for marker in forbidden if marker in source]
    if remaining:
        raise RuntimeError("unsafe native function parameter extraction remains")
    if source.count(_SPECIAL_NEW) != 2:
        raise RuntimeError("native special parameter normalization lost a site")
    print(
        "NORMALIZED NATIVE FUNCTION PARAMETER NAMES",
        function_count,
        lambda_count,
        special_count,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
