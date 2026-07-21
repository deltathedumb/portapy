from __future__ import annotations

from portapy import native_api as base
from portapy import native_api_environment as environment
from portapy import native_api_host as host


def test_native_environment_enumerates_and_deletes_globals() -> None:
    runtime = base._portapy_runtime_create_impl()
    assert runtime != 0

    first = base._portapy_value_from_i64_impl(runtime, 41)
    second = base._portapy_value_from_i64_impl(runtime, 42)
    assert first != 0 and second != 0
    assert host._portapy_set_global_span_impl(runtime, "first", 5, first) == base.PORTAPY_OK
    assert host._portapy_set_global_span_impl(runtime, "second", 6, second) == base.PORTAPY_OK
    assert base._portapy_value_release_impl(runtime, first) == base.PORTAPY_OK
    assert base._portapy_value_release_impl(runtime, second) == base.PORTAPY_OK

    assert environment._portapy_global_count_impl(runtime) == 2
    assert environment._portapy_global_name_size_impl(runtime, 0) == 5
    name = "".join(
        chr(environment._portapy_global_name_byte_impl(runtime, 0, index))
        for index in range(5)
    )
    assert name == "first"

    assert (
        environment._portapy_delete_global_span_impl(runtime, "first", 5)
        == base.PORTAPY_OK
    )
    assert environment._portapy_global_count_impl(runtime) == 1
    captured = base._portapy_get_global_span_impl(runtime, "second", 6)
    assert base._portapy_value_as_i64_impl(runtime, captured) == 42
    assert base._portapy_value_release_impl(runtime, captured) == base.PORTAPY_OK

    assert (
        environment._portapy_delete_global_span_impl(runtime, "first", 5)
        == base.PORTAPY_NOT_FOUND
    )
    assert base._portapy_error_status_impl(runtime) == base.PORTAPY_NOT_FOUND
