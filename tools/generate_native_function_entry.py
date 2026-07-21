"""Generate PortaPy's native function entry over namespaced dependencies."""
from __future__ import annotations

import argparse
from io import StringIO
from pathlib import Path
import token
import tokenize


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FUNCTION_SOURCE = REPOSITORY_ROOT / "src" / "portapy" / "native_api_functions.py"


_CONTROL_IMPORT = """from .native_api_control import (
    _line_info,
    _portapy_exec_span_impl as _control_exec_span,
    _syntax_error,
)"""
_EXPRESSION_IMPORT = """from .native_api_expressions import (
    _parse_boolean_expression,
    _record_expression_failure,
)"""
_SCALAR_IMPORT = """from .native_api_scalar import (
    _binary,
    _find_assignment,
    _release,
    _retain_global,
)"""


def _rename_identifiers(source: str, mapping: dict[str, str]) -> str:
    rewritten: list[tokenize.TokenInfo] = []
    for item in tokenize.generate_tokens(StringIO(source).readline):
        if item.type == token.NAME and item.string in mapping:
            item = tokenize.TokenInfo(
                item.type,
                mapping[item.string],
                item.start,
                item.end,
                item.line,
            )
        rewritten.append(item)
    return tokenize.untokenize(rewritten)


def rewrite_control_expression_imports(path: Path, expression_module: str) -> Path:
    """Point generated control code at the namespaced expression functions."""
    source = path.read_text(encoding="utf-8")
    old = f"""from .{expression_module} import (
    _parse_boolean_expression,
    _record_expression_failure,
    _truthy,
    _word_at,
)"""
    new = f"""from .{expression_module} import (
    _expr_parse_boolean_expression as _parse_boolean_expression,
    _expr_record_expression_failure as _record_expression_failure,
    _expr_truthy as _truthy,
    _expr_word_at as _word_at,
)"""
    if old not in source:
        raise ValueError("generated control entry has an unexpected expression import")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")
    return path


def generate_native_function_entry(
    output: Path,
    *,
    scalar_module: str,
    expression_module: str,
    control_module: str,
) -> Path:
    for label, module in (
        ("scalar", scalar_module),
        ("expression", expression_module),
        ("control", control_module),
    ):
        if not module.isidentifier():
            raise ValueError(f"invalid generated {label} module: {module!r}")

    source = FUNCTION_SOURCE.read_text(encoding="utf-8")
    control_import = f"""from .{control_module} import (
    _ctrl_line_info,
    _ctrl_portapy_exec_span_impl,
    _ctrl_syntax_error,
)"""
    expression_import = f"""from .{expression_module} import (
    _expr_parse_boolean_expression,
    _expr_record_expression_failure,
)"""
    scalar_import = f"""from .{scalar_module} import (
    _scalar_binary,
    _scalar_find_assignment,
    _scalar_release,
    _scalar_retain_global,
    _scalar_tuple_item_owner,
    _scalar_tuple_item_index,
    _scalar_tuple_item_value,
    _scalar_dict_build_top,
    _scalar_push_dict_build,
    _scalar_release_dict_build,
    _scalar_append_dict,
    _scalar_string_from_text,
)"""

    for old, new, label in (
        (_CONTROL_IMPORT, control_import, "control"),
        (_EXPRESSION_IMPORT, expression_import, "expression"),
        (_SCALAR_IMPORT, scalar_import, "scalar"),
    ):
        if old not in source:
            raise ValueError(f"native function source has an unexpected {label} import")
        source = source.replace(old, new, 1)

    source = _rename_identifiers(
        source,
        {
            "_line_info": "_ctrl_line_info",
            "_control_exec_span": "_ctrl_portapy_exec_span_impl",
            "_syntax_error": "_ctrl_syntax_error",
            "_parse_boolean_expression": "_expr_parse_boolean_expression",
            "_record_expression_failure": "_expr_record_expression_failure",
            "_binary": "_scalar_binary",
            "_find_assignment": "_scalar_find_assignment",
            "_release": "_scalar_release",
            "_retain_global": "_scalar_retain_global",
        },
    )
    source = source.replace(
        '"""Positional function definitions and calls for PortaPy\'s native runtime.',
        '"""Generated positional function entry for PortaPy\'s native runtime.',
        1,
    )
    source = source.replace(
        "    _global_value,\n",
        "    _global_value,\n    _last_status,\n",
        1,
    )
    old_status = '''def _last_status_value() -> int:
    from .native_api import _last_status

    return _last_status[0]'''
    new_status = '''def _last_status_value() -> int:
    return _last_status[0]'''
    if old_status not in source:
        raise ValueError("native function source has an unexpected last-status helper")
    source = source.replace(old_status, new_status, 1)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(source, encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--scalar-module", required=True)
    parser.add_argument("--expression-module", required=True)
    parser.add_argument("--control-module", required=True)
    arguments = parser.parse_args()
    generate_native_function_entry(
        arguments.output,
        scalar_module=arguments.scalar_module,
        expression_module=arguments.expression_module,
        control_module=arguments.control_module,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
