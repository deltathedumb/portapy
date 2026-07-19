from __future__ import annotations

from portapy import native_api as api


def test_runtime_and_integer_value_lifecycle() -> None:
    runtime = api.portapy_internal_runtime_create()
    assert runtime > 0
    assert api.portapy_internal_runtime_status(runtime) == api.PORTAPY_OK

    value = api.portapy_internal_value_create_i64(runtime, -42)
    assert value > 0
    assert api.portapy_internal_value_status(runtime, value) == api.PORTAPY_OK
    assert api.portapy_internal_value_kind(runtime, value) == api.PORTAPY_VALUE_INT
    assert api.portapy_internal_value_i64(runtime, value) == -42

    assert api.portapy_internal_value_retain(runtime, value) == api.PORTAPY_OK
    assert api.portapy_internal_value_release(runtime, value) == api.PORTAPY_OK
    assert api.portapy_internal_value_i64(runtime, value) == -42
    assert api.portapy_internal_value_release(runtime, value) == api.PORTAPY_OK
    assert (
        api.portapy_internal_value_status(runtime, value)
        == api.PORTAPY_INVALID_HANDLE
    )

    owned_value = api.portapy_internal_value_create_i64(runtime, 99)
    assert owned_value > 0
    assert api.portapy_internal_runtime_destroy(runtime) == api.PORTAPY_OK
    assert api.portapy_internal_runtime_status(runtime) == api.PORTAPY_CLOSED
    assert (
        api.portapy_internal_value_status(runtime, owned_value)
        == api.PORTAPY_CLOSED
    )


def test_values_cannot_cross_runtime_boundaries() -> None:
    first = api.portapy_internal_runtime_create()
    second = api.portapy_internal_runtime_create()
    value = api.portapy_internal_value_create_i64(first, 7)

    assert (
        api.portapy_internal_value_status(second, value)
        == api.PORTAPY_INVALID_HANDLE
    )
    assert api.portapy_internal_runtime_destroy(first) == api.PORTAPY_OK
    assert api.portapy_internal_runtime_destroy(second) == api.PORTAPY_OK
