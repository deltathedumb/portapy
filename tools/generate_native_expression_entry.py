"""Generate namespace-safe native scalar and expression source entries.

asmpython currently lowers imported Python functions into one native symbol
namespace. PortaPy's scalar and boolean parser layers intentionally use several
of the same private helper names, so the scalar layer is deterministically
prefixed before compilation. Interpreter semantics remain in the original
Python sources; this tool only performs a build-time symbol transform.
"""
from __future__ import annotations

import argparse
import ast
from io import StringIO
from pathlib import Path
import token
import tokenize


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BOOLEAN_SOURCE = REPOSITORY_ROOT / "src" / "portapy" / "native_api_boolean.py"
SCALAR_SOURCE = REPOSITORY_ROOT / "src" / "portapy" / "native_api_scalar.py"
SCALAR_PREFIX = "_scalar_"


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


def _prefixed(name: str) -> str:
    return SCALAR_PREFIX + name.lstrip("_")


def _top_level_function_names(source: str) -> tuple[str, ...]:
    tree = ast.parse(source)
    return tuple(
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )


def _rename_identifiers(source: str, mapping: dict[str, str]) -> str:
    tokens: list[tokenize.TokenInfo] = []
    for item in tokenize.generate_tokens(StringIO(source).readline):
        if item.type == token.NAME and item.string in mapping:
            item = tokenize.TokenInfo(
                item.type,
                mapping[item.string],
                item.start,
                item.end,
                item.line,
            )
        tokens.append(item)
    return tokenize.untokenize(tokens)


def generate_namespaced_scalar_entry(output: Path) -> Path:
    """Write a scalar parser module whose private functions cannot collide."""
    source = SCALAR_SOURCE.read_text(encoding="utf-8")
    names = _top_level_function_names(source)
    mapping = {name: _prefixed(name) for name in names}
    required = {
        "_binary",
        "_find_assignment",
        "_parse_comparison",
        "_record_failure",
        "_release",
    }
    missing = sorted(required.difference(mapping))
    if missing:
        raise ValueError(f"native scalar source is missing helpers: {missing}")

    source = _rename_identifiers(source, mapping)
    source = source.replace(
        '"""General scalar-expression native source entry for PortaPy.',
        '"""Generated namespace-safe scalar expression entry for PortaPy.',
        1,
    )
    source += '''


def _scalar_retain_global(runtime: int, name: str, position: int) -> list[int]:
    """Namespace-safe forwarding wrapper for the typed global lookup helper."""
    return _retain_global(runtime, name, position)
'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(source, encoding="utf-8")
    return output


def _static_imports(scalar_module: str) -> str:
    return f"""from .{scalar_module} import (
    _scalar_binary,
    _scalar_find_assignment,
    _scalar_parse_comparison,
    _scalar_record_failure,
    _scalar_release,
    _scalar_retain_global,
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
    parsed = _scalar_parse_comparison(runtime, source, end, start)
    if parsed[2] != PORTAPY_OK:
        return parsed
    final = _skip_space(source, end, parsed[1])
    if final != end:
        _scalar_release(runtime, parsed[0])
        return [0, final, PORTAPY_COMPILE_ERROR]
    return [parsed[0], end, PORTAPY_OK]'''


def _record_failure() -> str:
    return '''def _record_expression_failure(runtime: int, status: int, position: int) -> int:
    return _scalar_record_failure(runtime, status, position)'''


def _exec_statement() -> str:
    return '''def _exec_expression_assignment(runtime: int, source: str, source_size: int) -> int:
    """Execute assignment, augmented assignment, pass, or a bare expression."""
    bounds = _trim_statement_bounds(source, 0, source_size)
    source = source[bounds[0]:bounds[1]]
    source_size = len(source)
    if source_size == 0 or source == "pass":
        return _set_status(PORTAPY_OK)

    assignment = _scalar_find_assignment(source, source_size)
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
            current = _scalar_retain_global(runtime, name, 0)
            if current[2] != PORTAPY_OK:
                _scalar_release(runtime, right[0])
                return _record_expression_failure(runtime, current[2], 0)
            operator = str(assignment[0])[:-1]
            combined = _scalar_binary(
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
    _scalar_release(runtime, value[0])
    return _set_status(PORTAPY_OK)'''


def generate_native_expression_entry(output: Path, *, scalar_module: str) -> Path:
    if not scalar_module.isidentifier():
        raise ValueError(f"invalid generated scalar module: {scalar_module!r}")
    source = BOOLEAN_SOURCE.read_text(encoding="utf-8")

    old_import = "from .native_api_typed import _parse_typed_expression, _record_typed_failure"
    if old_import not in source:
        raise ValueError("boolean expression source has an unexpected scalar import")
    source = source.replace(old_import, _static_imports(scalar_module), 1)
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
    parser.add_argument("--scalar-module", required=True)
    parser.add_argument("--scalar-output", type=Path)
    args = parser.parse_args(argv)
    if args.scalar_output is not None:
        generate_namespaced_scalar_entry(args.scalar_output)
    generate_native_expression_entry(args.output, scalar_module=args.scalar_module)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
