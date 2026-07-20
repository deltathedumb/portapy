"""Generate PortaPy's static native expression source entry.

The native library initializer cannot safely mutate imported module functions.
This build-time transform composes the Python-authored boolean and scalar parser
layers into one ordinary Python module before asmpython compilation. It does not
introduce interpreter semantics in C, assembly, or the build tool itself.
"""
from __future__ import annotations

import argparse
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BOOLEAN_SOURCE = REPOSITORY_ROOT / "src" / "portapy" / "native_api_boolean.py"
SCALAR_SOURCE = REPOSITORY_ROOT / "src" / "portapy" / "native_api_scalar.py"


def _replace_function(source: str, name: str, replacement: str) -> str:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        raise ValueError(f"native expression source is missing {name}")
    if start > 0 and source[start - 1] != "\n":
        raise ValueError(f"native expression function {name} is not top-level")
    next_function = source.find("\ndef ", start + len(marker))
    end = len(source) if next_function < 0 else next_function + 1
    return source[:start] + replacement.rstrip() + "\n\n" + source[end:]


def _static_imports() -> str:
    return """from .native_api_scalar import (
    _binary,
    _find_assignment,
    _parse_comparison as _parse_scalar_expression,
    _record_failure as _record_scalar_failure,
    _release,
    _retain_global,
)"""


def _find_comparison() -> str:
    return '''def _find_comparison(source: str, start: int, end: int) -> list[int]:
    """Find a top-level comparison without treating shifts as ordering."""
    quote = ""
    escaped = False
    depth = 0
    position = start
    while position < end:
        char = source[position]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\\\":
                escaped = True
            elif char == quote:
                quote = ""
            position += 1
            continue
        if char == "'" or char == '"':
            quote = char
            position += 1
            continue
        if char == "(":
            depth += 1
            position += 1
            continue
        if char == ")":
            if depth > 0:
                depth -= 1
            position += 1
            continue
        if depth != 0:
            position += 1
            continue
        if char == "=" and position + 1 < end and source[position + 1] == "=":
            return [position, position + 2, _CMP_EQ]
        if char == "!" and position + 1 < end and source[position + 1] == "=":
            return [position, position + 2, _CMP_NE]
        if char == "<":
            if position + 1 < end and source[position + 1] == "<":
                position += 2
                continue
            if position + 1 < end and source[position + 1] == "=":
                return [position, position + 2, _CMP_LE]
            return [position, position + 1, _CMP_LT]
        if char == ">":
            if position + 1 < end and source[position + 1] == ">":
                position += 2
                continue
            if position + 1 < end and source[position + 1] == "=":
                return [position, position + 2, _CMP_GE]
            return [position, position + 1, _CMP_GT]
        if _word_at(source, position, end, "is"):
            after_is = _skip_space(source, end, position + 2)
            if _word_at(source, after_is, end, "not"):
                return [position, after_is + 3, _CMP_IS_NOT]
            return [position, position + 2, _CMP_IS]
        position += 1
    return [-1, -1, 0]'''


def _parse_scalar_complete() -> str:
    return '''def _parse_typed_complete(runtime: int, source: str, start: int, end: int) -> list[int]:
    """Parse one complete precedence-aware scalar operand."""
    bounds = _trim_range(source, start, end)
    start = bounds[0]
    end = bounds[1]
    parsed = _parse_scalar_expression(runtime, source, end, start)
    if parsed[2] != PORTAPY_OK:
        return parsed
    final = _skip_space(source, end, parsed[1])
    if final != end:
        _release(runtime, parsed[0])
        return [0, final, PORTAPY_COMPILE_ERROR]
    return [parsed[0], end, PORTAPY_OK]'''


def _record_failure() -> str:
    return '''def _record_expression_failure(runtime: int, status: int, position: int) -> int:
    return _record_scalar_failure(runtime, status, position)'''


def _exec_statement() -> str:
    return '''def _exec_expression_assignment(runtime: int, source: str, source_size: int) -> int:
    """Execute assignment, augmented assignment, pass, or a bare expression."""
    bounds = _trim_statement_bounds(source, 0, source_size)
    source = source[bounds[0]:bounds[1]]
    source_size = len(source)
    if source_size == 0 or source == "pass":
        return _set_status(PORTAPY_OK)

    assignment = _find_assignment(source, source_size)
    if assignment[0]:
        left_text = source[0:int(assignment[1])]
        left_bounds = _parse_identifier_bounds(left_text, len(left_text), 0)
        if left_bounds[2] != PORTAPY_OK:
            return _record_expression_failure(runtime, PORTAPY_COMPILE_ERROR, left_bounds[1])
        if _skip_space(left_text, len(left_text), left_bounds[1]) != len(left_text):
            return _record_expression_failure(runtime, PORTAPY_COMPILE_ERROR, left_bounds[1])
        name = left_text[left_bounds[0]:left_bounds[1]]
        right = _parse_boolean_expression(runtime, source, int(assignment[2]), source_size)
        if right[2] != PORTAPY_OK:
            return _record_expression_failure(runtime, right[2], right[1])

        if assignment[0] != "=":
            current = _retain_global(runtime, name, 0)
            if current[2] != PORTAPY_OK:
                _release(runtime, right[0])
                return _record_expression_failure(runtime, current[2], 0)
            operator = str(assignment[0])[:-1]
            combined = _binary(
                runtime,
                current[0],
                right[0],
                operator,
                int(assignment[1]),
            )
            if combined[2] != PORTAPY_OK:
                return _record_expression_failure(runtime, combined[2], combined[1])
            right = combined
        return _bind_global(runtime, name, right[0])

    value = _parse_boolean_expression(runtime, source, 0, source_size)
    if value[2] != PORTAPY_OK:
        return _record_expression_failure(runtime, value[2], value[1])
    _release(runtime, value[0])
    return _set_status(PORTAPY_OK)'''


def generate_native_expression_entry(output: Path) -> Path:
    source = BOOLEAN_SOURCE.read_text(encoding="utf-8")
    if not SCALAR_SOURCE.is_file():
        raise ValueError(f"native scalar source is missing: {SCALAR_SOURCE}")

    old_import = "from .native_api_typed import _parse_typed_expression, _record_typed_failure"
    if old_import not in source:
        raise ValueError("boolean expression source has an unexpected scalar import")
    source = source.replace(old_import, _static_imports(), 1)
    source = source.replace(
        '"""Boolean and comparison expression entry for PortaPy\'s native runtime.',
        '"""Generated general expression entry for PortaPy\'s native runtime.',
        1,
    )
    source = _replace_function(source, "_find_comparison", _find_comparison())
    source = _replace_function(source, "_parse_typed_complete", _parse_scalar_complete())
    source = _replace_function(source, "_record_expression_failure", _record_failure())
    source = _replace_function(source, "_exec_expression_assignment", _exec_statement())

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(source, encoding="utf-8")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    generate_native_expression_entry(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
