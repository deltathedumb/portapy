"""Generate PortaPy's host-call entry over namespaced native dependencies."""
from __future__ import annotations

from io import StringIO
from pathlib import Path
import token
import tokenize


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPOSITORY_ROOT / "src" / "portapy" / "native_api_host_calls.py"

_HOST_IMPORT = """from .native_api_host import (
    _dotted_path_bounds as _host_dotted_path_bounds,
    _parse_host_or_function_expression as _host_parse_expression,
    _portapy_host_get_attr_span_impl as _host_get_attr_span,
    _portapy_host_set_attr_span_impl as _host_set_attr_span,
    _portapy_set_global_span_impl as _host_set_global_span,
    _portapy_value_from_host_object_impl as _host_value_from_object,
    _portapy_value_get_host_id_impl as _host_value_get_id,
    _portapy_eval_span_impl as _host_eval_span,
    _portapy_exec_span_impl as _host_exec_span,
    _resolve_host_path as _host_resolve_path,
)"""
_SCALAR_IMPORT = "from .native_api_scalar import _find_assignment, _release, _retain_global"
_ENVIRONMENT_IMPORT = """from .native_api_environment import (
    _portapy_delete_global_span_impl,
    _portapy_global_count_impl,
    _portapy_global_name_byte_impl,
    _portapy_global_name_size_impl,
)
"""
_TRACEBACK_FORWARDERS = '''


def _traceback_filename_for_runtime(runtime: int) -> str:
    return _host_traceback_filename_for_runtime(runtime)


def _portapy_traceback_set_filename_impl(runtime: int, filename: str, filename_size: int) -> int:
    return _host_portapy_traceback_set_filename_impl(runtime, filename, filename_size)


def _portapy_traceback_default_filename_impl(runtime: int) -> int:
    return _host_portapy_traceback_default_filename_impl(runtime)


def _portapy_traceback_reset_impl(runtime: int) -> int:
    return _host_portapy_traceback_reset_impl(runtime)


def _portapy_traceback_add_impl(
    runtime: int,
    line: int,
    column: int,
    function_name: str,
    source_line: str,
) -> int:
    return _host_portapy_traceback_add_impl(
        runtime,
        line,
        column,
        function_name,
        source_line,
    )


def _portapy_traceback_count_impl(runtime: int) -> int:
    return _host_portapy_traceback_count_impl(runtime)


def _portapy_traceback_line_impl(runtime: int, index: int) -> int:
    return _host_portapy_traceback_line_impl(runtime, index)


def _portapy_traceback_column_impl(runtime: int, index: int) -> int:
    return _host_portapy_traceback_column_impl(runtime, index)


def _portapy_traceback_filename_size_impl(runtime: int, index: int) -> int:
    return _host_portapy_traceback_filename_size_impl(runtime, index)


def _portapy_traceback_filename_byte_impl(runtime: int, index: int, byte_index: int) -> int:
    return _host_portapy_traceback_filename_byte_impl(runtime, index, byte_index)


def _portapy_traceback_function_size_impl(runtime: int, index: int) -> int:
    return _host_portapy_traceback_function_size_impl(runtime, index)


def _portapy_traceback_function_byte_impl(runtime: int, index: int, byte_index: int) -> int:
    return _host_portapy_traceback_function_byte_impl(runtime, index, byte_index)


def _portapy_traceback_source_size_impl(runtime: int, index: int) -> int:
    return _host_portapy_traceback_source_size_impl(runtime, index)


def _portapy_traceback_source_byte_impl(runtime: int, index: int, byte_index: int) -> int:
    return _host_portapy_traceback_source_byte_impl(runtime, index, byte_index)
'''
_LIFECYCLE_FORWARDERS = '''


def _portapy_error_clear_impl(runtime: int) -> int:
    if _runtime_is_valid(runtime):
        _portapy_traceback_reset_impl(runtime)
    return _core_portapy_error_clear_impl(runtime)


def _portapy_runtime_destroy_impl(runtime: int) -> int:
    if _runtime_is_valid(runtime):
        _portapy_traceback_reset_impl(runtime)
    return _core_portapy_runtime_destroy_impl(runtime)
'''


def _rename(source: str, mapping: dict[str, str]) -> str:
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


def _alias_core_lifecycle(source: str) -> str:
    aliases = (
        ("_portapy_error_clear_impl", "_core_portapy_error_clear_impl"),
        ("_portapy_runtime_destroy_impl", "_core_portapy_runtime_destroy_impl"),
    )
    for original, alias in aliases:
        marker = f"    {original},\n"
        replacement = f"    {original} as {alias},\n"
        if marker not in source:
            raise ValueError(f"host-call source is missing lifecycle import: {original}")
        source = source.replace(marker, replacement, 1)
    return source


def generate_native_host_call_entry(
    output: Path,
    *,
    host_module: str,
    scalar_module: str,
) -> Path:
    if not host_module.isidentifier() or not scalar_module.isidentifier():
        raise ValueError("generated module names must be identifiers")
    source = SOURCE.read_text(encoding="utf-8")
    if _HOST_IMPORT not in source:
        raise ValueError("host-call source has an unexpected host import")
    if _SCALAR_IMPORT not in source:
        raise ValueError("host-call source has an unexpected scalar import")
    source = _alias_core_lifecycle(source)

    host_import = f"""from .{host_module} import (
    _host_dotted_path_bounds,
    _host_parse_host_or_function_expression,
    _host_portapy_host_get_attr_span_impl,
    _host_portapy_host_set_attr_span_impl,
    _host_portapy_set_global_span_impl,
    _host_portapy_value_from_host_object_impl,
    _host_portapy_value_get_host_id_impl,
    _host_portapy_eval_span_impl,
    _host_portapy_exec_span_impl,
    _host_resolve_host_path,
    _host_traceback_filename_for_runtime,
    _host_portapy_traceback_set_filename_impl,
    _host_portapy_traceback_default_filename_impl,
    _host_portapy_traceback_reset_impl,
    _host_portapy_traceback_add_impl,
    _host_portapy_traceback_count_impl,
    _host_portapy_traceback_line_impl,
    _host_portapy_traceback_column_impl,
    _host_portapy_traceback_filename_size_impl,
    _host_portapy_traceback_filename_byte_impl,
    _host_portapy_traceback_function_size_impl,
    _host_portapy_traceback_function_byte_impl,
    _host_portapy_traceback_source_size_impl,
    _host_portapy_traceback_source_byte_impl,
)"""
    scalar_import = f"""from .{scalar_module} import (
    _scalar_find_assignment,
    _scalar_release,
    _scalar_retain_global,
    _scalar_tuple_item_owner,
    _scalar_tuple_item_index,
    _scalar_tuple_item_value,
    _scalar_tuple_size_unchecked,
    _scalar_tuple_item_unchecked,
    _scalar_dict_entry_owner,
    _scalar_dict_entry_key,
    _scalar_dict_entry_value,
    _scalar_dict_size_unchecked,
    _scalar_dict_item_unchecked,
    _scalar_list_item_owner,
    _scalar_list_item_index,
    _scalar_list_item_value,
    _scalar_list_size_unchecked,
    _scalar_list_item_unchecked,
    _scalar_list_set,
    _scalar_list_append,
)"""
    source = source.replace(_HOST_IMPORT, host_import, 1)
    source = source.replace(_SCALAR_IMPORT, scalar_import, 1)
    source = source.replace(
        "from __future__ import annotations\n",
        "from __future__ import annotations\n\n" + _ENVIRONMENT_IMPORT,
        1,
    )
    source = _rename(
        source,
        {
            "_host_dotted_path_bounds": "_host_dotted_path_bounds",
            "_host_parse_expression": "_host_parse_host_or_function_expression",
            "_host_get_attr_span": "_host_portapy_host_get_attr_span_impl",
            "_host_set_attr_span": "_host_portapy_host_set_attr_span_impl",
            "_host_set_global_span": "_host_portapy_set_global_span_impl",
            "_host_value_from_object": "_host_portapy_value_from_host_object_impl",
            "_host_value_get_id": "_host_portapy_value_get_host_id_impl",
            "_host_eval_span": "_host_portapy_eval_span_impl",
            "_host_exec_span": "_host_portapy_exec_span_impl",
            "_host_resolve_path": "_host_resolve_host_path",
            "_find_assignment": "_scalar_find_assignment",
            "_release": "_scalar_release",
            "_retain_global": "_scalar_retain_global",
        },
    )
    source = source.replace(
        '"""Synchronous host-callable dispatch over PortaPy\'s opaque host bridge.',
        '"""Generated synchronous host-call entry for PortaPy.',
        1,
    )
    source = source.rstrip() + _TRACEBACK_FORWARDERS + _LIFECYCLE_FORWARDERS
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(source, encoding="utf-8")
    return output


__all__ = ["generate_native_host_call_entry"]
