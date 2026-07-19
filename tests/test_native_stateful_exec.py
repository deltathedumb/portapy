from __future__ import annotations

from portapy import native_api as api


def _exec(runtime: int, source: str) -> int:
    return api._portapy_exec_span_impl(runtime, source, len(source))


def _eval(runtime: int, source: str) -> int:
    handle = api._portapy_eval_span_impl(runtime, source, len(source))
    assert handle != 0
    return handle


def _get(runtime: int, name: str) -> int:
    return api._portapy_get_global_span_impl(runtime, name, len(name))


def test_assignment_persists_and_eval_resolves_globals() -> None:
    runtime = api._portapy_runtime_create_impl()
    assert _exec(runtime, "answer = 6 * 7") == api.PORTAPY_OK

    value = _get(runtime, "answer")
    assert value != 0
    assert api._portapy_value_as_i64_impl(runtime, value) == 42

    evaluated = _eval(runtime, "answer + 8")
    assert api._portapy_value_as_i64_impl(runtime, evaluated) == 50

    assert api._portapy_value_release_impl(runtime, value) == api.PORTAPY_OK
    assert api._portapy_value_release_impl(runtime, evaluated) == api.PORTAPY_OK
    assert api._portapy_runtime_destroy_impl(runtime) == api.PORTAPY_OK


def test_globals_are_isolated_by_runtime() -> None:
    first = api._portapy_runtime_create_impl()
    second = api._portapy_runtime_create_impl()
    assert _exec(first, "value = 9") == api.PORTAPY_OK

    assert _get(second, "value") == 0
    assert api._portapy_last_status_impl() == api.PORTAPY_NOT_FOUND
    assert api._portapy_eval_span_impl(second, "value + 1", 9) == 0
    assert api._portapy_last_status_impl() == api.PORTAPY_NOT_FOUND

    first_value = _get(first, "value")
    assert api._portapy_value_as_i64_impl(first, first_value) == 9


def test_rebinding_preserves_previously_fetched_handle() -> None:
    runtime = api._portapy_runtime_create_impl()
    assert _exec(runtime, "counter = 41") == api.PORTAPY_OK
    old_value = _get(runtime, "counter")
    assert api._portapy_value_as_i64_impl(runtime, old_value) == 41

    assert _exec(runtime, "counter = counter + 1") == api.PORTAPY_OK
    new_value = _get(runtime, "counter")
    assert new_value != old_value
    assert api._portapy_value_as_i64_impl(runtime, old_value) == 41
    assert api._portapy_value_as_i64_impl(runtime, new_value) == 42

    assert api._portapy_value_release_impl(runtime, old_value) == api.PORTAPY_OK
    assert api._portapy_value_release_impl(runtime, new_value) == api.PORTAPY_OK


def test_failed_assignment_leaves_previous_binding_unchanged() -> None:
    runtime = api._portapy_runtime_create_impl()
    assert _exec(runtime, "stable = 12") == api.PORTAPY_OK

    assert _exec(runtime, "stable = 5 // 0") == api.PORTAPY_RUNTIME_ERROR
    current = _get(runtime, "stable")
    assert api._portapy_value_as_i64_impl(runtime, current) == 12

    assert _exec(runtime, "stable + 1") == api.PORTAPY_COMPILE_ERROR
    current_again = _get(runtime, "stable")
    assert api._portapy_value_as_i64_impl(runtime, current_again) == 12


def test_missing_and_invalid_global_names_fail_closed() -> None:
    runtime = api._portapy_runtime_create_impl()
    assert _get(runtime, "missing") == 0
    assert api._portapy_last_status_impl() == api.PORTAPY_NOT_FOUND
    assert api._portapy_get_global_span_impl(runtime, "", 0) == 0
    assert api._portapy_last_status_impl() == api.PORTAPY_INVALID_ARGUMENT

    for source in ("= 1", "1value = 2", "name =", "name == 2", "name = 1 trailing"):
        assert _exec(runtime, source) == api.PORTAPY_COMPILE_ERROR


def test_runtime_destroy_invalidates_global_and_fetched_handles() -> None:
    runtime = api._portapy_runtime_create_impl()
    assert _exec(runtime, "owned = 7") == api.PORTAPY_OK
    fetched = _get(runtime, "owned")
    assert fetched != 0

    assert api._portapy_runtime_destroy_impl(runtime) == api.PORTAPY_OK
    assert api._portapy_value_as_i64_impl(runtime, fetched) == 0
    assert api._portapy_last_status_impl() == api.PORTAPY_INVALID_HANDLE
    assert api._portapy_get_global_span_impl(runtime, "owned", 5) == 0
    assert api._portapy_last_status_impl() == api.PORTAPY_INVALID_HANDLE
