"""Single source of truth for PortaPy's public native ABI surface."""
from __future__ import annotations


ASSEMBLY_PUBLIC_EXPORTS = (
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

BASE_GLUE_EXPORTS = (
    "portapy_value_from_utf8",
    "portapy_value_from_bytes",
    "portapy_value_get_size",
    "portapy_value_copy_data",
    "portapy_error_get_info",
    "portapy_error_copy_type_utf8",
    "portapy_error_copy_message_utf8",
    "portapy_error_clear",
)

HOST_GLUE_EXPORTS = (
    "portapy_set_global_utf8",
    "portapy_value_from_host_object",
    "portapy_value_get_host_id",
    "portapy_host_set_attr_utf8",
    "portapy_host_get_attr_utf8",
)

HOST_CALL_GLUE_EXPORTS = (
    "portapy_host_set_call_handler",
    "portapy_value_from_host_callable",
    "portapy_value_get_host_callable_id",
)

ENVIRONMENT_GLUE_EXPORTS = (
    "portapy_delete_global_utf8",
    "portapy_global_count",
    "portapy_global_name_copy_utf8",
)

TUPLE_GLUE_EXPORTS = (
    "portapy_value_from_tuple",
    "portapy_tuple_get_size",
    "portapy_tuple_get_item",
)

BASE_GLUE_INTERNALS = (
    "_portapy_last_status_impl",
    "_portapy_value_from_data_begin_impl",
    "_portapy_value_set_data_byte_impl",
    "_portapy_value_validate_utf8_impl",
    "_portapy_value_get_size_impl",
    "_portapy_value_get_byte_impl",
    "_portapy_value_release_impl",
    "_portapy_error_status_impl",
    "_portapy_error_line_impl",
    "_portapy_error_column_impl",
    "_portapy_error_type_size_impl",
    "_portapy_error_type_byte_impl",
    "_portapy_error_message_size_impl",
    "_portapy_error_message_byte_impl",
    "_portapy_error_clear_impl",
)

HOST_GLUE_INTERNALS = (
    "_portapy_value_from_host_object_impl",
    "_portapy_value_get_host_id_impl",
    "_portapy_set_global_span_impl",
    "_portapy_host_set_attr_span_impl",
    "_portapy_host_get_attr_span_impl",
)

# C glue links against these ABI-preserving assembly adapters rather than the
# generated helpers directly. The adapters are internal to the shared library.
HOST_CALL_GLUE_INTERNALS = (
    "_portapy_cabi_last_status_impl",
    "_portapy_cabi_value_from_host_callable_impl",
    "_portapy_cabi_value_get_host_callable_id_impl",
    "_portapy_cabi_host_pending_arg_count_impl",
    "_portapy_cabi_host_pending_arg_impl",
    "_portapy_cabi_host_dispatch_complete_impl",
)

ENVIRONMENT_GLUE_INTERNALS = (
    "_portapy_cabi_delete_global_span_impl",
    "_portapy_cabi_global_count_impl",
    "_portapy_cabi_global_name_size_impl",
    "_portapy_cabi_global_name_byte_impl",
)

TUPLE_GLUE_INTERNALS = (
    "_portapy_cabi_tuple_begin_impl",
    "_portapy_cabi_tuple_set_item_impl",
    "_portapy_cabi_tuple_finish_impl",
    "_portapy_cabi_tuple_get_size_impl",
    "_portapy_cabi_tuple_get_item_impl",
    "_portapy_cabi_tuple_release_impl",
)

# Compatibility constants used by older tooling and tests.
GLUE_EXPORTS = BASE_GLUE_EXPORTS
GLUE_INTERNALS = BASE_GLUE_INTERNALS
ASSEMBLY_EXPORTS = ASSEMBLY_PUBLIC_EXPORTS + BASE_GLUE_INTERNALS
PUBLIC_EXPORTS = ASSEMBLY_PUBLIC_EXPORTS + BASE_GLUE_EXPORTS


def assembly_exports(
    *,
    host_bridge: bool = False,
    host_calls: bool = False,
) -> tuple[str, ...]:
    result = ASSEMBLY_PUBLIC_EXPORTS + BASE_GLUE_INTERNALS
    if host_bridge or host_calls:
        result += HOST_GLUE_INTERNALS
    if host_calls:
        result += HOST_CALL_GLUE_INTERNALS
        result += ENVIRONMENT_GLUE_INTERNALS
        result += TUPLE_GLUE_INTERNALS
    return result


def public_exports(
    *,
    host_bridge: bool = False,
    host_calls: bool = False,
) -> tuple[str, ...]:
    result = ASSEMBLY_PUBLIC_EXPORTS + BASE_GLUE_EXPORTS
    if host_bridge or host_calls:
        result += HOST_GLUE_EXPORTS
    if host_calls:
        result += HOST_CALL_GLUE_EXPORTS
        result += ENVIRONMENT_GLUE_EXPORTS
        result += TUPLE_GLUE_EXPORTS
    return result


def linux_version_script(
    *,
    host_bridge: bool = False,
    host_calls: bool = False,
) -> str:
    lines = ["{", "  global:"]
    lines.extend(
        f"    {symbol};"
        for symbol in public_exports(host_bridge=host_bridge, host_calls=host_calls)
    )
    lines.extend(["  local: *;", "};", ""])
    return "\n".join(lines)


def windows_definition(
    library_name: str = "portapy",
    *,
    host_bridge: bool = False,
    host_calls: bool = False,
) -> str:
    lines = [f"LIBRARY {library_name}", "EXPORTS"]
    lines.extend(
        f"    {symbol}"
        for symbol in public_exports(host_bridge=host_bridge, host_calls=host_calls)
    )
    lines.append("")
    return "\n".join(lines)
