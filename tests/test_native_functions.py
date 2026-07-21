from __future__ import annotations

from portapy import native_api as base
from portapy import native_api_functions as functions


def _runtime() -> int:
    runtime = functions._portapy_runtime_create_impl()
    assert runtime != 0
    return runtime


def _exec(runtime: int, source: str) -> None:
    assert functions._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK


def _eval_int(runtime: int, source: str) -> int:
    value = functions._portapy_eval_span_impl(runtime, source, len(source))
    assert value != 0
    return base._portapy_value_as_i64_impl(runtime, value)


def test_function_definition_call_and_callable_global() -> None:
    runtime = _runtime()
    _exec(
        runtime,
        "def add(left, right):\n"
        "    total = left + right\n"
        "    return total\n"
        "answer = add(20, 22)\n",
    )

    assert _eval_int(runtime, "add(3, 4)") == 7
    answer = functions._portapy_get_global_span_impl(runtime, "answer", len("answer"))
    assert base._portapy_value_as_i64_impl(runtime, answer) == 42
    callable_value = functions._portapy_get_global_span_impl(runtime, "add", len("add"))
    assert base._portapy_value_get_kind_impl(runtime, callable_value) == base.PORTAPY_VALUE_CALLABLE


def test_function_locals_restore_globals_and_do_not_leak() -> None:
    runtime = _runtime()
    _exec(runtime, "total = 100\n")
    _exec(
        runtime,
        "def calculate(value):\n"
        "    total = value * 3\n"
        "    temporary = total + 1\n"
        "    return temporary\n"
        "answer = calculate(5)\n",
    )

    assert _eval_int(runtime, "total") == 100
    assert _eval_int(runtime, "answer") == 16
    missing = functions._portapy_get_global_span_impl(runtime, "temporary", len("temporary"))
    assert missing == 0
    assert functions._portapy_last_status_impl() == base.PORTAPY_NOT_FOUND


def test_nested_calls_and_cross_exec_persistence() -> None:
    runtime = _runtime()
    _exec(
        runtime,
        "def double(value):\n"
        "    return value * 2\n"
        "def add(left, right):\n"
        "    return left + right\n",
    )
    _exec(runtime, "answer = add(double(10), double(11))\n")
    assert _eval_int(runtime, "answer") == 42


def test_augmented_assignments_work_inside_function_body() -> None:
    runtime = _runtime()
    _exec(
        runtime,
        "def transform(value):\n"
        "    value *= 3\n"
        "    value += 27\n"
        "    return value\n"
        "answer = transform(5)\n",
    )
    assert _eval_int(runtime, "answer") == 42


def test_function_argument_mismatch_reports_type_error() -> None:
    runtime = _runtime()
    _exec(runtime, "def identity(value):\n    return value\n")
    value = functions._portapy_eval_span_impl(runtime, "identity()", len("identity()"))
    assert value == 0
    assert functions._portapy_last_status_impl() == base.PORTAPY_TYPE_ERROR
    assert functions._portapy_error_type_size_impl(runtime) == len("TypeError")


def test_sources_without_functions_keep_existing_control_flow() -> None:
    runtime = _runtime()
    _exec(
        runtime,
        "count = 0\n"
        "answer = 0\n"
        "while count < 4:\n"
        "    count = count + 1\n"
        "    if count == 2:\n"
        "        continue\n"
        "    answer = answer + count\n",
    )
    assert _eval_int(runtime, "answer") == 8


def test_if_else_and_nested_return_inside_function() -> None:
    runtime = _runtime()
    _exec(
        runtime,
        "def choose(value):\n"
        "    if value > 0:\n"
        "        if value > 10:\n"
        "            return 42\n"
        "        return 7\n"
        "    else:\n"
        "        return -1\n"
        "large = choose(20)\n"
        "small = choose(2)\n"
        "negative = choose(-2)\n",
    )
    assert _eval_int(runtime, "large") == 42
    assert _eval_int(runtime, "small") == 7
    assert _eval_int(runtime, "negative") == -1


def test_while_break_continue_and_nested_return_inside_function() -> None:
    runtime = _runtime()
    _exec(
        runtime,
        "def calculate(limit):\n"
        "    count = 0\n"
        "    total = 0\n"
        "    while count < limit:\n"
        "        count += 1\n"
        "        if count == 2:\n"
        "            continue\n"
        "        if count > 4:\n"
        "            break\n"
        "        total += count\n"
        "    return total\n"
        "def first_over(limit):\n"
        "    value = 0\n"
        "    while value < limit:\n"
        "        value += 1\n"
        "        if value > 3:\n"
        "            return value\n"
        "    return -1\n"
        "answer = calculate(10)\n"
        "early = first_over(10)\n",
    )
    assert _eval_int(runtime, "answer") == 8
    assert _eval_int(runtime, "early") == 4


def test_return_without_expression_inside_nested_block() -> None:
    runtime = _runtime()
    _exec(
        runtime,
        "def stop(value):\n"
        "    if value:\n"
        "        return\n"
        "    return 7\n"
        "result = stop(0)\n",
    )
    assert _eval_int(runtime, "result") == 7
    none_value = functions._portapy_eval_span_impl(runtime, "stop(1)", len("stop(1)"))
    assert none_value != 0
    assert base._portapy_value_get_kind_impl(runtime, none_value) == base.PORTAPY_VALUE_NONE
