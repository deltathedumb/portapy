from __future__ import annotations

from portapy import native_api as api


def test_none_and_bool_values() -> None:
    runtime = api._portapy_runtime_create_impl()

    none_value = api._portapy_value_from_none_impl(runtime)
    assert none_value > 0
    assert api._portapy_value_get_kind_impl(runtime, none_value) == api.PORTAPY_VALUE_NONE
    assert api._portapy_value_as_bool_impl(runtime, none_value) == 0
    assert api._portapy_last_status_impl() == api.PORTAPY_TYPE_ERROR

    true_value = api._portapy_value_from_bool_impl(runtime, 27)
    false_value = api._portapy_value_from_bool_impl(runtime, 0)
    assert api._portapy_value_get_kind_impl(runtime, true_value) == api.PORTAPY_VALUE_BOOL
    assert api._portapy_value_as_bool_impl(runtime, true_value) == 1
    assert api._portapy_value_as_bool_impl(runtime, false_value) == 0

    assert api._portapy_value_release_impl(runtime, none_value) == api.PORTAPY_OK
    assert api._portapy_value_release_impl(runtime, true_value) == api.PORTAPY_OK
    assert api._portapy_value_release_impl(runtime, false_value) == api.PORTAPY_OK
    assert api._portapy_runtime_destroy_impl(runtime) == api.PORTAPY_OK


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
