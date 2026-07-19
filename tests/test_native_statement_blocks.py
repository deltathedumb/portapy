from __future__ import annotations

from portapy import native_api as api


def _exec(runtime: int, source: str) -> int:
    return api._portapy_exec_span_impl(runtime, source, len(source))


def _value(runtime: int, name: str) -> int:
    handle = api._portapy_get_global_span_impl(runtime, name, len(name))
    assert handle != 0
    value = api._portapy_value_as_i64_impl(runtime, handle)
    assert api._portapy_value_release_impl(runtime, handle) == api.PORTAPY_OK
    return value


def test_newline_and_semicolon_assignment_blocks() -> None:
    runtime = api._portapy_runtime_create_impl()
    source = "base = 5\ndouble = base * 2; total = double + 3"
    assert _exec(runtime, source) == api.PORTAPY_OK
    assert _value(runtime, "base") == 5
    assert _value(runtime, "double") == 10
    assert _value(runtime, "total") == 13


def test_blank_lines_and_comments_are_ignored() -> None:
    runtime = api._portapy_runtime_create_impl()
    source = "\n# initial comment\nfirst = 4  # trailing comment\n\n; second = first + 6; # another\nthird = second * 2\n"
    assert _exec(runtime, source) == api.PORTAPY_OK
    assert _value(runtime, "first") == 4
    assert _value(runtime, "second") == 10
    assert _value(runtime, "third") == 20


def test_empty_and_comment_only_blocks_succeed() -> None:
    runtime = api._portapy_runtime_create_impl()
    assert _exec(runtime, "") == api.PORTAPY_OK
    assert _exec(runtime, " \n; # nothing here\n ; ") == api.PORTAPY_OK


def test_failure_stops_block_but_preserves_prior_side_effects() -> None:
    runtime = api._portapy_runtime_create_impl()
    source = "before = 1; broken = 5 // 0; after = 3"
    assert _exec(runtime, source) == api.PORTAPY_RUNTIME_ERROR
    assert _value(runtime, "before") == 1
    assert api._portapy_get_global_span_impl(runtime, "broken", 6) == 0
    assert api._portapy_last_status_impl() == api.PORTAPY_NOT_FOUND
    assert api._portapy_get_global_span_impl(runtime, "after", 5) == 0
    assert api._portapy_last_status_impl() == api.PORTAPY_NOT_FOUND


def test_later_statements_can_rebind_earlier_names() -> None:
    runtime = api._portapy_runtime_create_impl()
    assert _exec(runtime, "counter = 1; counter = counter + 1; counter = counter * 5") == api.PORTAPY_OK
    assert _value(runtime, "counter") == 10
