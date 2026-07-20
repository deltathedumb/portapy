"""Single source of truth for PortaPy's public native ABI surface."""
from __future__ import annotations


ASSEMBLY_EXPORTS = (
    "portapy_library_initialize",
    "portapy_abi_version",
    "portapy_runtime_create",
    "portapy_runtime_destroy",
    "portapy_exec_utf8",
    "portapy_eval_utf8",
    "portapy_get_global_utf8",
    "portapy_value_from_none",
    "portapy_value_from_bool",
    "portapy_value_from_i64",
    "portapy_value_from_f64",
    "portapy_value_get_kind",
    "portapy_value_as_bool",
    "portapy_value_as_i64",
    "portapy_value_as_f64",
    "portapy_value_retain",
    "portapy_value_release",
)

GLUE_EXPORTS = (
    "portapy_value_from_utf8",
    "portapy_value_from_bytes",
    "portapy_value_get_size",
    "portapy_value_copy_data",
    "portapy_error_get_info",
    "portapy_error_copy_type_utf8",
    "portapy_error_copy_message_utf8",
    "portapy_error_clear",
)

PUBLIC_EXPORTS = ASSEMBLY_EXPORTS + GLUE_EXPORTS


def linux_version_script() -> str:
    lines = ["{", "  global:"]
    lines.extend(f"    {symbol};" for symbol in PUBLIC_EXPORTS)
    lines.extend(["  local: *;", "};", ""])
    return "\n".join(lines)


def windows_definition(library_name: str = "portapy") -> str:
    lines = [f"LIBRARY {library_name}", "EXPORTS"]
    lines.extend(f"    {symbol}" for symbol in PUBLIC_EXPORTS)
    lines.append("")
    return "\n".join(lines)
