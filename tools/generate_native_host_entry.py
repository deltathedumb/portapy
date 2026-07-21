"""Generate PortaPy's host-object entry over namespaced native functions."""
from __future__ import annotations

from io import StringIO
from pathlib import Path
import token
import tokenize


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
HOST_SOURCE = REPOSITORY_ROOT / "src" / "portapy" / "native_api_host.py"


_FUNCTION_IMPORT = """from .native_api_functions import (
    _parse_call_or_expression as _function_parse_expression,
    _portapy_eval_span_impl as _function_eval_span,
    _portapy_exec_span_impl as _function_exec_span,
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


def generate_native_host_entry(
    output: Path,
    *,
    scalar_module: str,
    function_module: str,
) -> Path:
    if not scalar_module.isidentifier():
        raise ValueError(f"invalid generated scalar module: {scalar_module!r}")
    if not function_module.isidentifier():
        raise ValueError(f"invalid generated function module: {function_module!r}")

    source = HOST_SOURCE.read_text(encoding="utf-8")
    function_import = f"""from .{function_module} import (
    _fn_parse_call_or_expression,
    _fn_portapy_eval_span_impl,
    _fn_portapy_exec_span_impl,
)"""
    scalar_import = f"""from .{scalar_module} import (
    _scalar_binary,
    _scalar_find_assignment,
    _scalar_release,
    _scalar_retain_global,
)"""
    if _FUNCTION_IMPORT not in source:
        raise ValueError("native host source has an unexpected function import")
    if _SCALAR_IMPORT not in source:
        raise ValueError("native host source has an unexpected scalar import")
    source = source.replace(_FUNCTION_IMPORT, function_import, 1)
    source = source.replace(_SCALAR_IMPORT, scalar_import, 1)
    source = _rename_identifiers(
        source,
        {
            "_function_parse_expression": "_fn_parse_call_or_expression",
            "_function_eval_span": "_fn_portapy_eval_span_impl",
            "_function_exec_span": "_fn_portapy_exec_span_impl",
            "_binary": "_scalar_binary",
            "_find_assignment": "_scalar_find_assignment",
            "_release": "_scalar_release",
            "_retain_global": "_scalar_retain_global",
        },
    )
    source = source.replace(
        '"""Opaque host objects, global injection, and attribute traversal.',
        '"""Generated opaque host object entry for PortaPy.',
        1,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(source, encoding="utf-8")
    return output


__all__ = ["generate_native_host_entry"]
