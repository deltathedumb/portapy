"""Wrap final native eval/exec entries with traceback reset and root frames."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_parser import _replace_function


def _helpers() -> str:
    return '''def _traceback_source_line(source: str, line: int) -> str:
    if line <= 0:
        return ""
    current = 1
    start = 0
    position = 0
    while position <= len(source):
        if position == len(source) or source[position] == "\\n":
            if current == line:
                bounds = _trim(source, start, position)
                return source[bounds[0]:bounds[1]]
            current += 1
            start = position + 1
        position += 1
    return ""


def _traceback_record_root(runtime: int, source: str) -> int:
    saved_status = _portapy_last_status_impl()
    line = _runtime_error_line[runtime]
    if line <= 0:
        line = 1
    column = _portapy_error_column_impl(runtime)
    if column <= 0:
        column = 1
    source_line = _traceback_source_line(source, line)
    _portapy_traceback_add_impl(
        runtime,
        line,
        column,
        "<module>",
        source_line,
    )
    _set_status(saved_status)
    return PORTAPY_OK'''


def _eval_entry() -> str:
    return '''def _portapy_eval_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _clear_runtime_error(runtime)
    _portapy_traceback_reset_impl(runtime)
    if source_size < 0:
        _fail(runtime, PORTAPY_INVALID_ARGUMENT, "ValueError", "source size cannot be negative")
        _traceback_record_root(runtime, source)
        return 0
    call = _host_call_bounds(source, 0, source_size)
    if call[5] != PORTAPY_OK:
        value = _host_portapy_eval_span_impl(runtime, source, source_size)
    else:
        parsed = _parse_host_call_or_expression(runtime, source, 0, source_size)
        if parsed[2] != PORTAPY_OK:
            _set_status(parsed[2])
            value = 0
        else:
            value = parsed[0]
    if value == 0 and _portapy_last_status_impl() != PORTAPY_OK:
        _traceback_record_root(runtime, source)
    return value'''


def _exec_entry() -> str:
    return '''def _portapy_exec_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        return _set_status(PORTAPY_INVALID_HANDLE)
    _clear_runtime_error(runtime)
    _portapy_traceback_reset_impl(runtime)
    if source_size < 0:
        status = _fail(runtime, PORTAPY_INVALID_ARGUMENT, "ValueError", "source size cannot be negative")
    elif _source_has_import_statement(source, source_size):
        status = _exec_source_with_imports(runtime, source, source_size)
    elif _source_has_definition_or_compound(source, source_size):
        status = _host_portapy_exec_span_impl(runtime, source, source_size)
    elif not _source_has_host_call(source, source_size):
        status = _host_portapy_exec_span_impl(runtime, source, source_size)
    else:
        status = _exec_host_call_source(runtime, source, source_size)
    if status != PORTAPY_OK:
        _traceback_record_root(runtime, source)
    return status'''


def rewrite_generated_traceback_entry(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    source = _replace_function(source, "_portapy_eval_span_impl", _eval_entry())
    source = _replace_function(source, "_portapy_exec_span_impl", _exec_entry())
    source = source.rstrip() + "\n\n" + _helpers().rstrip() + "\n"
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_traceback_entry"]
