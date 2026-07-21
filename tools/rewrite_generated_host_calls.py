"""Apply asmpython-safe flat argument transport to generated host calls."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_imports import rewrite_generated_imports
from tools.rewrite_generated_parser import _replace_function


def _begin_pending_call() -> str:
    return '''def _begin_pending_call(
    runtime: int,
    callable_id: int,
    argument_start: int,
    argument_count: int,
) -> int:
    start = len(_pending_arguments)
    index = 0
    while index < argument_count:
        _pending_arguments.append(_host_call_argument_values[argument_start + index])
        index += 1
    _pending_runtime.append(runtime)
    _pending_callable_id.append(callable_id)
    _pending_argument_start.append(start)
    _pending_argument_count.append(argument_count)
    return len(_pending_runtime) - 1'''


def _dispatch_host_call() -> str:
    return '''def _dispatch_host_call(
    runtime: int,
    callable_id: int,
    argument_start: int,
    argument_count: int,
    position: int,
) -> list[int]:
    _begin_pending_call(runtime, callable_id, argument_start, argument_count)
    result = _portapy_host_dispatch_impl(runtime, callable_id)
    if result == 0:
        status = _portapy_last_status_impl()
        frame = _find_pending_frame(runtime)
        if frame != 0:
            _clear_pending_frame(runtime, frame)
        if status == PORTAPY_OK:
            status = PORTAPY_RUNTIME_ERROR
        return [0, position, status]
    return [result, position, PORTAPY_OK]'''


def _parse_host_call_or_expression() -> str:
    return '''def _push_host_call_argument(value: int) -> None:
    top = _host_call_argument_top[0]
    if top < len(_host_call_argument_values):
        _host_call_argument_values[top] = value
    else:
        _host_call_argument_values.append(value)
    _host_call_argument_top[0] = top + 1


def _parse_host_call_or_expression(runtime: int, source: str, start: int, end: int) -> list[int]:
    call = _host_call_bounds(source, start, end)
    if call[5] == _HOST_NOT_CALL:
        return _host_parse_host_or_function_expression(runtime, source, start, end)
    if call[5] != PORTAPY_OK:
        return [0, call[4], call[5]]
    target = _resolve_call_target(runtime, source, call[0], call[1])
    if target[2] != PORTAPY_OK:
        return _host_parse_host_or_function_expression(runtime, source, start, end)
    callable_id = _host_callable_identifier(runtime, target[0])
    if callable_id[1] != PORTAPY_OK:
        _scalar_release(runtime, target[0])
        dotted = _host_dotted_path_bounds(source, call[0], call[1])
        if dotted[2] == PORTAPY_OK:
            _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "host attribute is not callable")
            return [0, call[0], PORTAPY_TYPE_ERROR]
        return _host_parse_host_or_function_expression(runtime, source, start, end)
    _scalar_release(runtime, target[0])
    spans = _argument_spans(source, call[2], call[3])
    if spans[0] != PORTAPY_OK:
        return [0, spans[1], spans[0]]
    argument_start = _host_call_argument_top[0]
    index = 2
    while index < len(spans):
        parsed = _parse_host_call_or_expression(runtime, source, spans[index], spans[index + 1])
        if parsed[2] != PORTAPY_OK:
            release = argument_start
            while release < _host_call_argument_top[0]:
                _scalar_release(runtime, _host_call_argument_values[release])
                release += 1
            _host_call_argument_top[0] = argument_start
            return parsed
        _push_host_call_argument(parsed[0])
        index += 2
    argument_count = _host_call_argument_top[0] - argument_start
    dispatched = _dispatch_host_call(
        runtime,
        callable_id[0],
        argument_start,
        argument_count,
        call[4],
    )
    _host_call_argument_top[0] = argument_start
    dispatched[1] = call[4]
    return dispatched'''


def rewrite_generated_host_calls(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    marker = "_pending_arguments: list[int] = [0]\n"
    if marker not in source:
        raise ValueError("generated host-call entry is missing pending argument storage")
    source = source.replace(
        marker,
        marker
        + "_host_call_argument_values: list[int] = [0]\n"
        + "_host_call_argument_top: list[int] = [1]\n",
        1,
    )
    source = _replace_function(source, "_begin_pending_call", _begin_pending_call())
    source = _replace_function(source, "_dispatch_host_call", _dispatch_host_call())
    source = _replace_function(
        source,
        "_parse_host_call_or_expression",
        _parse_host_call_or_expression(),
    )
    path.write_text(source, encoding="utf-8")
    return rewrite_generated_imports(path)


__all__ = ["rewrite_generated_host_calls"]
