"""Generate PortaPy's native control-flow entry over static parser modules."""
from __future__ import annotations

import argparse
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONTROL_SOURCE = REPOSITORY_ROOT / "src" / "portapy" / "native_api_control.py"


def _replace_function(source: str, name: str, replacement: str) -> str:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        raise ValueError(f"native control-flow source is missing {name}")
    if start > 0 and source[start - 1] != "\n":
        raise ValueError(f"native control-flow function {name} is not top-level")
    next_function = source.find("\ndef ", start + len(marker))
    end = len(source) if next_function < 0 else next_function + 1
    return source[:start] + replacement.rstrip() + "\n\n" + source[end:]


def _execute_assignment() -> str:
    return '''def _execute_assignment(runtime: int, source: str, start: int, end: int) -> int:
    statement = source[start:end]
    assignment = _scalar_find_assignment(statement, len(statement))
    if not assignment[0]:
        parsed = _parse_boolean_expression(runtime, source, start, end)
        if parsed[2] != PORTAPY_OK:
            return _record_expression_failure(runtime, parsed[2], parsed[1])
        _release_value(runtime, parsed[0])
        return _set_status(PORTAPY_OK)

    left_text = statement[0:int(assignment[1])]
    bounds = _parse_identifier_bounds(left_text, len(left_text), 0)
    if bounds[2] != PORTAPY_OK:
        return _record_expression_failure(runtime, bounds[2], start + bounds[1])
    name_end = _skip_space(left_text, len(left_text), bounds[1])
    if name_end != len(left_text):
        return _syntax_error(runtime, source, start + name_end, "invalid assignment target")
    name = left_text[bounds[0]:bounds[1]]

    parsed = _parse_boolean_expression(
        runtime,
        statement,
        int(assignment[2]),
        len(statement),
    )
    if parsed[2] != PORTAPY_OK:
        return _record_expression_failure(runtime, parsed[2], start + parsed[1])

    if assignment[0] != "=":
        current = _retain_scalar_global(runtime, name, start)
        if current[2] != PORTAPY_OK:
            _release_value(runtime, parsed[0])
            return _record_expression_failure(runtime, current[2], start)
        operator = str(assignment[0])[:-1]
        combined = _scalar_binary(
            runtime,
            current[0],
            parsed[0],
            operator,
            start + int(assignment[1]),
        )
        if combined[2] != PORTAPY_OK:
            return _record_expression_failure(runtime, combined[2], combined[1])
        parsed = combined
    return _bind_global(runtime, name, parsed[0])'''


def generate_native_control_entry(
    output: Path,
    *,
    expression_module: str,
    scalar_module: str,
) -> Path:
    if not expression_module.isidentifier():
        raise ValueError(f"invalid generated expression module: {expression_module!r}")
    if not scalar_module.isidentifier():
        raise ValueError(f"invalid generated scalar module: {scalar_module!r}")
    source = CONTROL_SOURCE.read_text(encoding="utf-8")
    old_import = """from .native_api_expressions import (
    _parse_boolean_expression,
    _record_expression_failure,
    _truthy,
    _word_at,
)"""
    new_import = f"""from .{expression_module} import (
    _parse_boolean_expression,
    _record_expression_failure,
    _truthy,
    _word_at,
)
from .{scalar_module} import (
    _scalar_binary,
    _scalar_find_assignment,
)
from .native_api import (
    _release as _release_value,
    _retain_global as _retain_scalar_global,
)"""
    if old_import not in source:
        raise ValueError("control-flow source has an unexpected expression import")
    source = source.replace(old_import, new_import, 1)
    source = source.replace(
        '"""Indented control-flow entry for PortaPy\'s native runtime.',
        '"""Generated control-flow entry for PortaPy\'s native runtime.',
        1,
    )
    source = _replace_function(source, "_execute_assignment", _execute_assignment())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(source, encoding="utf-8")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expression-module", required=True)
    parser.add_argument("--scalar-module", required=True)
    args = parser.parse_args(argv)
    generate_native_control_entry(
        args.output,
        expression_module=args.expression_module,
        scalar_module=args.scalar_module,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
