from __future__ import annotations

from portapy import native_api as api


def _text(api_runtime: int, kind: int, payload: bytes) -> int:
    value = api._portapy_value_from_data_begin_impl(api_runtime, kind, len(payload))
    assert value != 0
    for index, byte in enumerate(payload):
        assert api._portapy_value_set_data_byte_impl(api_runtime, value, index, byte) == api.PORTAPY_OK
    return value


def _error_text(runtime: int, size_function, byte_function) -> str:
    size = size_function(runtime)
    return bytes(byte_function(runtime, index) for index in range(size)).decode("utf-8")


def test_bytes_values_preserve_every_octet() -> None:
    runtime = api._portapy_runtime_create_impl()
    payload = bytes((0, 1, 65, 127, 128, 255))
    value = _text(runtime, api.PORTAPY_VALUE_BYTES, payload)

    assert api._portapy_value_get_kind_impl(runtime, value) == api.PORTAPY_VALUE_BYTES
    assert api._portapy_value_get_size_impl(runtime, value) == len(payload)
    assert bytes(
        api._portapy_value_get_byte_impl(runtime, value, index)
        for index in range(len(payload))
    ) == payload


def test_utf8_values_accept_valid_unicode_and_reject_invalid_sequences() -> None:
    runtime = api._portapy_runtime_create_impl()
    payload = "PortaPy π 🐍".encode("utf-8")
    value = _text(runtime, api.PORTAPY_VALUE_STRING, payload)

    assert api._portapy_value_validate_utf8_impl(runtime, value) == api.PORTAPY_OK
    assert api._portapy_value_get_kind_impl(runtime, value) == api.PORTAPY_VALUE_STRING

    invalid = _text(runtime, api.PORTAPY_VALUE_STRING, b"\xf0\x28\x8c\x28")
    assert api._portapy_value_validate_utf8_impl(runtime, invalid) == api.PORTAPY_TYPE_ERROR
    assert api._portapy_error_status_impl(runtime) == api.PORTAPY_TYPE_ERROR
    assert _error_text(runtime, api._portapy_error_type_size_impl, api._portapy_error_type_byte_impl) == "UnicodeDecodeError"
    assert "continuation" in _error_text(
        runtime,
        api._portapy_error_message_size_impl,
        api._portapy_error_message_byte_impl,
    )


def test_execution_failures_publish_structured_error_information() -> None:
    runtime = api._portapy_runtime_create_impl()
    source = "safe = 1\nbroken = 5 // 0"

    assert api._portapy_exec_span_impl(runtime, source, len(source)) == api.PORTAPY_RUNTIME_ERROR
    assert api._portapy_error_status_impl(runtime) == api.PORTAPY_RUNTIME_ERROR
    assert api._portapy_error_line_impl(runtime) == 2
    assert api._portapy_error_column_impl(runtime) > 0
    assert _error_text(runtime, api._portapy_error_type_size_impl, api._portapy_error_type_byte_impl) == "ZeroDivisionError"
    assert "zero" in _error_text(
        runtime,
        api._portapy_error_message_size_impl,
        api._portapy_error_message_byte_impl,
    )

    assert api._portapy_error_clear_impl(runtime) == api.PORTAPY_OK
    assert api._portapy_error_status_impl(runtime) == api.PORTAPY_OK
    assert api._portapy_error_type_size_impl(runtime) == 0
    assert api._portapy_error_message_size_impl(runtime) == 0


def test_type_conversion_failure_is_structured() -> None:
    runtime = api._portapy_runtime_create_impl()
    value = _text(runtime, api.PORTAPY_VALUE_BYTES, b"42")

    assert api._portapy_value_as_i64_impl(runtime, value) == 0
    assert api._portapy_last_status_impl() == api.PORTAPY_TYPE_ERROR
    assert api._portapy_error_status_impl(runtime) == api.PORTAPY_TYPE_ERROR
    assert _error_text(runtime, api._portapy_error_type_size_impl, api._portapy_error_type_byte_impl) == "TypeError"
