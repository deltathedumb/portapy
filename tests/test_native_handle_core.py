from __future__ import annotations

from portapy import native_api as api


def test_runtime_and_i64_value_lifecycle() -> None:
    runtime = api._portapy_runtime_create_impl()
    assert runtime > 0
    assert api._portapy_last_status_impl() == api.PORTAPY_OK

    value = api._portapy_value_from_i64_impl(runtime, -42)
    assert value > 0
    assert api._portapy_last_status_impl() == api.PORTAPY_OK
    assert api._portapy_value_get_kind_impl(runtime, value) == api.PORTAPY_VALUE_INT
    assert api._portapy_last_status_impl() == api.PORTAPY_OK
    assert api._portapy_value_as_i64_impl(runtime, value) == -42
    assert api._portapy_last_status_impl() == api.PORTAPY_OK

    assert api._portapy_value_retain_impl(runtime, value) == api.PORTAPY_OK
    assert api._portapy_value_release_impl(runtime, value) == api.PORTAPY_OK
    assert api._portapy_value_as_i64_impl(runtime, value) == -42
    assert api._portapy_value_release_impl(runtime, value) == api.PORTAPY_OK
    assert api._portapy_value_as_i64_impl(runtime, value) == 0
    assert api._portapy_last_status_impl() == api.PORTAPY_INVALID_HANDLE

    assert api._portapy_runtime_destroy_impl(runtime) == api.PORTAPY_OK
    assert api._portapy_runtime_destroy_impl(runtime) == api.PORTAPY_INVALID_HANDLE


def test_values_are_isolated_by_runtime() -> None:
    first = api._portapy_runtime_create_impl()
    second = api._portapy_runtime_create_impl()
    value = api._portapy_value_from_i64_impl(first, 123)
    assert api._portapy_value_as_i64_impl(second, value) == 0
    assert api._portapy_last_status_impl() == api.PORTAPY_INVALID_HANDLE
    assert api._portapy_value_release_impl(second, value) == api.PORTAPY_INVALID_HANDLE
    assert api._portapy_value_as_i64_impl(first, value) == 123


def test_destroy_invalidates_owned_values() -> None:
    runtime = api._portapy_runtime_create_impl()
    value = api._portapy_value_from_i64_impl(runtime, 7)
    assert api._portapy_runtime_destroy_impl(runtime) == api.PORTAPY_OK
    assert api._portapy_value_get_kind_impl(runtime, value) == api.PORTAPY_VALUE_OBJECT
    assert api._portapy_last_status_impl() == api.PORTAPY_INVALID_HANDLE
