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
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(source, encoding="utf-8")
    return output


__all__ = ["generate_native_host_call_entry"]
