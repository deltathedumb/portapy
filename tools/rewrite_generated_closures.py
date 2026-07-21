"""Add lexical closure cells and nested ``def`` execution to native functions."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_parser import _replace_function
from tools.rewrite_generated_traceback import _EXECUTION_WITH_TRACEBACK


_STATE_MARKER = "_captured_default_top: list[int] = [1]\n"
_LOCAL_MARKER = "    names = _collect_local_names(_function_body[slot], parameters)\n"
_SAVE_END_MARKER = '''    while index < len(names):
        _save_binding(runtime, names[index], saved_names, saved_existed, saved_values)
        index += 1

    index = 0
    while index < expected:'''
_SAVE_END_REPLACEMENT = '''    while index < len(names):
        _save_binding(runtime, names[index], saved_names, saved_existed, saved_values)
        index += 1

    closure_frame = _closure_begin_frame(runtime, slot, local_names)
    _closure_bind_captures(runtime, slot, local_names)

    index = 0
    while index < expected:'''
_PARAMETER_BIND_MARKER = '''        parameter = _parameter_at(parameters, index)
        _bind_global(runtime, parameter, _call_bound_values[bound_start + index])
        index += 1'''
_PARAMETER_BIND_REPLACEMENT = '''        parameter = _parameter_at(parameters, index)
        _bind_global(runtime, parameter, _call_bound_values[bound_start + index])
        _closure_update_active_cell(runtime, parameter, _call_bound_values[bound_start + index])
        index += 1'''
_EXECUTION_WITH_CLOSURE = '''    _call_depth[runtime] += 1
    executed = _execute_function_body(runtime, slot)
    _call_depth[runtime] -= 1
    _closure_end_frame(runtime, closure_frame)
    _restore_bindings(runtime, saved_names, saved_existed, saved_values)
    _call_bound_top[0] = bound_start
    if executed[1] != PORTAPY_OK:
        _portapy_traceback_add_function_impl(runtime, slot)
        return [0, position, executed[1]]'''
_NESTED_BRANCH_MARKER = '        if _word_at(source, start, end, "if"):\n'


def _state_and_helpers() -> str:
    return r'''_closure_next_frame: list[int] = [1]
_closure_active_runtime: list[int] = [0]
_closure_active_slot: list[int] = [0]
_closure_active_frame: list[int] = [0]
_closure_cell_runtime: list[int] = [0]
_closure_cell_frame: list[int] = [0]
_closure_cell_name: list[str] = [""]
_closure_cell_value: list[int] = [0]
_closure_cell_captured: list[int] = [0]
_closure_function_slot: list[int] = [0]
_closure_function_cell: list[int] = [0]


def _closure_name_in(names: list[str], name: str) -> bool:
    index = 0
    while index < len(names):
        if names[index] == name:
            return True
        index += 1
    return False


def _closure_collect_local_names(body: str, parameters: str) -> list[str]:
    names = _collect_local_names(body, parameters)
    position = 0
    body_size = len(body)
    while position < body_size:
        line_end = position
        while line_end < body_size and body[line_end] != "\n":
            line_end += 1
        bounds = _trim(body, position, line_end)
        if bounds[0] < bounds[1] and _word_at(body, bounds[0], bounds[1], "def"):
            header = _parse_definition_header(body, bounds[0], bounds[1])
            if header[3] == PORTAPY_OK:
                name = header[0]
                if not _closure_name_in(names, name):
                    names.append(name)
        position = line_end + 1
    return names


def _closure_current_active_index(runtime: int) -> int:
    index = len(_closure_active_runtime) - 1
    while index > 0:
        if _closure_active_runtime[index] == runtime:
            return index
        index -= 1
    return 0


def _closure_find_cell(runtime: int, frame: int, name: str) -> int:
    index = 1
    while index < len(_closure_cell_runtime):
        if (
            _closure_cell_runtime[index] == runtime
            and _closure_cell_frame[index] == frame
            and _closure_cell_name[index] == name
        ):
            return index
        index += 1
    return 0


def _closure_begin_frame(runtime: int, slot: int, names: list[str]) -> int:
    frame = _closure_next_frame[0]
    _closure_next_frame[0] = frame + 1
    _closure_active_runtime.append(runtime)
    _closure_active_slot.append(slot)
    _closure_active_frame.append(frame)
    index = 0
    while index < len(names):
        _closure_cell_runtime.append(runtime)
        _closure_cell_frame.append(frame)
        _closure_cell_name.append(names[index])
        _closure_cell_value.append(0)
        _closure_cell_captured.append(0)
        index += 1
    return frame


def _closure_update_cell(runtime: int, cell: int, value: int) -> None:
    if cell <= 0 or cell >= len(_closure_cell_runtime):
        return
    if _closure_cell_runtime[cell] != runtime:
        return
    previous = _closure_cell_value[cell]
    if _value_is_valid(runtime, previous):
        _value_refs[previous] -= 1
    _closure_cell_value[cell] = value
    if _value_is_valid(runtime, value):
        _value_refs[value] += 1


def _closure_update_active_cell(runtime: int, name: str, value: int) -> None:
    active = _closure_current_active_index(runtime)
    if active == 0:
        return
    cell = _closure_find_cell(runtime, _closure_active_frame[active], name)
    if cell != 0:
        _closure_update_cell(runtime, cell, value)


def _closure_end_frame(runtime: int, frame: int) -> None:
    active = len(_closure_active_runtime) - 1
    while active > 0:
        if (
            _closure_active_runtime[active] == runtime
            and _closure_active_frame[active] == frame
        ):
            _closure_active_runtime[active] = 0
            _closure_active_slot[active] = 0
            _closure_active_frame[active] = 0
            break
        active -= 1
    cell = 1
    while cell < len(_closure_cell_runtime):
        if (
            _closure_cell_runtime[cell] == runtime
            and _closure_cell_frame[cell] == frame
            and _closure_cell_captured[cell] == 0
        ):
            value = _closure_cell_value[cell]
            if _value_is_valid(runtime, value):
                _value_refs[value] -= 1
            _closure_cell_runtime[cell] = 0
            _closure_cell_frame[cell] = 0
            _closure_cell_name[cell] = ""
            _closure_cell_value[cell] = 0
        cell += 1


def _closure_function_has_cell(slot: int, cell: int) -> bool:
    index = 1
    while index < len(_closure_function_slot):
        if _closure_function_slot[index] == slot and _closure_function_cell[index] == cell:
            return True
        index += 1
    return False


def _closure_function_has_name(slot: int, name: str) -> bool:
    index = 1
    while index < len(_closure_function_slot):
        if _closure_function_slot[index] == slot:
            cell = _closure_function_cell[index]
            if cell > 0 and cell < len(_closure_cell_name):
                if _closure_cell_name[cell] == name:
                    return True
        index += 1
    return False


def _closure_add_function_cell(slot: int, cell: int) -> None:
    if cell == 0 or _closure_function_has_cell(slot, cell):
        return
    _closure_function_slot.append(slot)
    _closure_function_cell.append(cell)
    _closure_cell_captured[cell] = 1


def _closure_capture_active_cells(runtime: int, parent_slot: int, child_slot: int) -> None:
    active = _closure_current_active_index(runtime)
    if active == 0 or _closure_active_slot[active] != parent_slot:
        return
    frame = _closure_active_frame[active]
    cell = 1
    while cell < len(_closure_cell_runtime):
        if (
            _closure_cell_runtime[cell] == runtime
            and _closure_cell_frame[cell] == frame
        ):
            _closure_add_function_cell(child_slot, cell)
        cell += 1
    index = 1
    while index < len(_closure_function_slot):
        if _closure_function_slot[index] == parent_slot:
            parent_cell = _closure_function_cell[index]
            if parent_cell > 0 and parent_cell < len(_closure_cell_name):
                name = _closure_cell_name[parent_cell]
                if not _closure_function_has_name(child_slot, name):
                    _closure_add_function_cell(child_slot, parent_cell)
        index += 1


def _closure_append_capture_names(slot: int, names: list[str]) -> None:
    index = 1
    while index < len(_closure_function_slot):
        if _closure_function_slot[index] == slot:
            cell = _closure_function_cell[index]
            if cell > 0 and cell < len(_closure_cell_name):
                name = _closure_cell_name[cell]
                if not _closure_name_in(names, name):
                    names.append(name)
        index += 1


def _closure_bind_captures(runtime: int, slot: int, local_names: list[str]) -> None:
    index = 1
    while index < len(_closure_function_slot):
        if _closure_function_slot[index] == slot:
            cell = _closure_function_cell[index]
            if cell > 0 and cell < len(_closure_cell_name):
                name = _closure_cell_name[cell]
                if not _closure_name_in(local_names, name):
                    value = _closure_cell_value[cell]
                    if _value_is_valid(runtime, value):
                        _value_refs[value] += 1
                        _bind_global(runtime, name, value)
        index += 1


def _register_nested_function(
    runtime: int,
    parent_slot: int,
    name: str,
    parameters: str,
    body: str,
    line: int,
) -> int:
    captured = _capture_function_defaults(runtime, parameters, line)
    capture_start = captured[0]
    if captured[1] != PORTAPY_OK:
        return captured[1]
    _function_runtime.append(runtime)
    _function_name.append(name)
    _function_parameters.append(parameters)
    _function_body.append(body)
    _function_definition_line.append(line)
    slot = len(_function_runtime) - 1
    value = _append_value(runtime, PORTAPY_VALUE_CALLABLE, slot)
    if value == 0:
        _function_runtime[slot] = 0
        _function_name[slot] = ""
        _function_parameters[slot] = ""
        _function_body[slot] = ""
        _function_definition_line[slot] = 0
        _release_captured_default_range(runtime, capture_start)
        return _last_status_value()
    status = _bind_global(runtime, name, value)
    if status != PORTAPY_OK:
        _function_runtime[slot] = 0
        _function_name[slot] = ""
        _function_parameters[slot] = ""
        _function_body[slot] = ""
        _function_definition_line[slot] = 0
        _release_captured_default_range(runtime, capture_start)
        return status
    _commit_captured_function_defaults(capture_start, slot)
    _closure_capture_active_cells(runtime, parent_slot, slot)
    _closure_update_active_cell(runtime, name, value)
    return status
'''


def _find_function_slot() -> str:
    return '''def _find_function_slot(runtime: int, name: str) -> int:
    global_slot = _find_global_slot(runtime, name)
    if global_slot == 0:
        return 0
    value = _global_value[global_slot]
    if not _value_is_valid(runtime, value):
        return 0
    if _value_kind[value] != PORTAPY_VALUE_CALLABLE:
        return 0
    slot = _value_i64[value]
    if slot <= 0 or slot >= len(_function_runtime):
        return 0
    if _function_runtime[slot] != runtime:
        return 0
    return slot'''


def _execute_function_statement() -> str:
    return '''def _execute_function_statement(runtime: int, statement: str, line: int) -> int:
    assignment = _find_assignment(statement, len(statement))
    if assignment[0] == "":
        parsed = _parse_call_or_expression(runtime, statement, 0, len(statement))
        if parsed[2] != PORTAPY_OK:
            _runtime_error_line[runtime] = line
            return _expr_record_expression_failure(runtime, parsed[2], parsed[1])
        _scalar_release(runtime, parsed[0])
        return _set_status(PORTAPY_OK)
    left = statement[0:assignment[1]]
    bounds = _parse_identifier_bounds(left, len(left), 0)
    if bounds[2] != PORTAPY_OK or _skip_space(left, len(left), bounds[1]) != len(left):
        return _fail(runtime, PORTAPY_COMPILE_ERROR, "SyntaxError", "invalid assignment target", line, 1)
    name = left[bounds[0]:bounds[1]]
    parsed = _parse_call_or_expression(runtime, statement, assignment[2], len(statement))
    if parsed[2] != PORTAPY_OK:
        _runtime_error_line[runtime] = line
        return _expr_record_expression_failure(runtime, parsed[2], parsed[1])
    if assignment[0] != "=":
        current = _scalar_retain_global(runtime, name, 0)
        if current[2] != PORTAPY_OK:
            _scalar_release(runtime, parsed[0])
            return _expr_record_expression_failure(runtime, current[2], 0)
        operator = _operator_from_assignment(assignment[0])
        if operator == "":
            _scalar_release(runtime, current[0])
            _scalar_release(runtime, parsed[0])
            return _fail(runtime, PORTAPY_COMPILE_ERROR, "SyntaxError", "unsupported augmented assignment", line, 1)
        combined = _scalar_binary(runtime, current[0], parsed[0], operator, assignment[1])
        if combined[2] != PORTAPY_OK:
            return _expr_record_expression_failure(runtime, combined[2], combined[1])
        parsed = combined
    status = _bind_global(runtime, name, parsed[0])
    if status == PORTAPY_OK:
        _closure_update_active_cell(runtime, name, parsed[0])
    return status'''


def _nested_branch() -> str:
    return '''        if _word_at(source, start, end, "def"):
            header = _parse_definition_header(source, start, end)
            if header[3] != PORTAPY_OK:
                return [
                    position,
                    _function_syntax_error(runtime, slot, source, start, "invalid nested function definition"),
                    _FUNCTION_FLOW_NORMAL,
                    0,
                ]
            child_indent = _function_child_indent(source, source_size, next_position, indent)
            if child_indent < 0:
                return [
                    position,
                    _function_syntax_error(runtime, slot, source, end, "expected an indented function body"),
                    _FUNCTION_FLOW_NORMAL,
                    0,
                ]
            body_end = _function_skip_block(source, source_size, next_position, child_indent)
            body = _dedent_body(source, next_position, body_end, child_indent)
            status = _register_nested_function(
                runtime,
                slot,
                header[0],
                header[1],
                body,
                _function_actual_line(slot, source, start),
            )
            if status != PORTAPY_OK:
                return [position, status, _FUNCTION_FLOW_NORMAL, 0]
            position = body_end
            continue

'''


def _rewrite_invoke(source: str) -> str:
    start = source.find("def _invoke_function(")
    if start < 0:
        raise ValueError("generated function entry is missing _invoke_function")
    end = source.find("\ndef ", start + 1)
    if end < 0:
        end = len(source)
    function = source[start:end]
    if _LOCAL_MARKER not in function:
        raise ValueError("generated invoke function is missing local collection")
    function = function.replace(
        _LOCAL_MARKER,
        '''    local_names = _closure_collect_local_names(_function_body[slot], parameters)
    names: list[str] = []
    index = 0
    while index < len(local_names):
        names.append(local_names[index])
        index += 1
    _closure_append_capture_names(slot, names)
''',
        1,
    )
    if _SAVE_END_MARKER not in function:
        raise ValueError("generated invoke function is missing saved-binding boundary")
    function = function.replace(_SAVE_END_MARKER, _SAVE_END_REPLACEMENT, 1)
    if _PARAMETER_BIND_MARKER not in function:
        raise ValueError("generated invoke function is missing parameter binding")
    function = function.replace(_PARAMETER_BIND_MARKER, _PARAMETER_BIND_REPLACEMENT, 1)
    if _EXECUTION_WITH_TRACEBACK not in function:
        raise ValueError("generated invoke function is missing traceback unwind block")
    function = function.replace(_EXECUTION_WITH_TRACEBACK, _EXECUTION_WITH_CLOSURE, 1)
    return source[:start] + function + source[end:]


def rewrite_generated_closures(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    if _STATE_MARKER not in source:
        raise ValueError("generated function entry is missing captured-default state")
    source = source.replace(
        _STATE_MARKER,
        _STATE_MARKER + _state_and_helpers().rstrip() + "\n",
        1,
    )
    source = _replace_function(source, "_find_function_slot", _find_function_slot())
    source = _replace_function(
        source,
        "_execute_function_statement",
        _execute_function_statement(),
    )
    if _NESTED_BRANCH_MARKER not in source:
        raise ValueError("generated function block executor is missing if branch")
    source = source.replace(
        _NESTED_BRANCH_MARKER,
        _nested_branch() + _NESTED_BRANCH_MARKER,
        1,
    )
    source = _rewrite_invoke(source)
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_closures"]
