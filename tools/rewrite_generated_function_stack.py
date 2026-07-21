"""Stack-safe native function rewrite with full argument semantics."""
from __future__ import annotations

from pathlib import Path

from tools.generated_function_control_source import (
    FUNCTION_FLOW_CONSTANTS,
    execute_function_body_source,
)
from tools.rewrite_generated_function_arguments_safe import rewrite_generated_function_arguments
from tools.rewrite_generated_function_containers import (
    rewrite_generated_function_containers,
)
from tools.rewrite_generated_function_default_capture import (
    rewrite_generated_function_default_capture,
)
from tools.rewrite_generated_function_kwargs import rewrite_generated_function_kwargs
from tools.rewrite_generated_function_parameter_kinds_safe import (
    rewrite_generated_function_parameter_kinds,
)
from tools.rewrite_generated_function_safe import rewrite_generated_function as _rewrite
from tools.rewrite_generated_function_varargs_safe import rewrite_generated_function_varargs
from tools.rewrite_generated_parser import _replace_function


def _parse_call_or_expression() -> str:
    return '''def _push_call_argument(value: int) -> None:
    top = _call_argument_top[0]
    if top < len(_call_argument_values):
        _call_argument_values[top] = value
    else:
        _call_argument_values.append(value)
    _call_argument_top[0] = top + 1


def _parse_call_or_expression(runtime: int, source: str, start: int, end: int) -> list[int]:
    call = _direct_call_bounds(source, start, end)
    if call[3] == 0:
        return _expr_parse_boolean_expression(runtime, source, start, end)
    function_slot = _find_function_slot(runtime, call[0])
    if function_slot == 0:
        return _expr_parse_boolean_expression(runtime, source, start, end)
    arguments = _argument_spans(source, int(call[1]), int(call[2]))
    if arguments[0] != PORTAPY_OK:
        return [0, arguments[1], arguments[0]]
    argument_start = _call_argument_top[0]
    index = 2
    while index < len(arguments):
        parsed = _parse_call_or_expression(runtime, source, arguments[index], arguments[index + 1])
        if parsed[2] != PORTAPY_OK:
            release = argument_start
            while release < _call_argument_top[0]:
                _scalar_release(runtime, _call_argument_values[release])
                release += 1
            _call_argument_top[0] = argument_start
            return parsed
        _push_call_argument(parsed[0])
        index += 2
    argument_count = _call_argument_top[0] - argument_start
    result = _invoke_function(runtime, function_slot, argument_start, argument_count, start)
    _call_argument_top[0] = argument_start
    return result'''


def rewrite_generated_function(path: Path) -> Path:
    _rewrite(path)
    source = path.read_text(encoding="utf-8")
    marker = "_call_argument_values: list[int] = [0]\n"
    if marker not in source:
        raise ValueError("generated function entry is missing call argument storage")
    source = source.replace(
        marker,
        marker + "_call_argument_top: list[int] = [1]\n",
        1,
    )
    expression_import = "    _expr_record_expression_failure,\n)"
    if expression_import not in source:
        raise ValueError("generated function entry has an unexpected expression import")
    source = source.replace(
        expression_import,
        "    _expr_record_expression_failure,\n    _expr_truthy,\n)",
        1,
    )
    constant_marker = "_MAX_CALL_DEPTH = 128\n"
    if constant_marker not in source:
        raise ValueError("generated function entry is missing call-depth configuration")
    source = source.replace(
        constant_marker,
        constant_marker + FUNCTION_FLOW_CONSTANTS,
        1,
    )
    source = _replace_function(
        source,
        "_parse_call_or_expression",
        _parse_call_or_expression(),
    )
    source = _replace_function(
        source,
        "_execute_function_body",
        execute_function_body_source(),
    )
    path.write_text(source, encoding="utf-8")
    rewrite_generated_function_arguments(path)
    rewrite_generated_function_default_capture(path)
    rewrite_generated_function_parameter_kinds(path)
    rewrite_generated_function_varargs(path)
    rewrite_generated_function_kwargs(path)
    rewrite_generated_function_containers(path)
    return path


__all__ = ["rewrite_generated_function"]
