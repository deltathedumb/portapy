from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from portapy import native_api as base
from tools.generate_native_control_entry import generate_native_control_entry
from tools.generate_native_expression_entry import (
    generate_namespaced_scalar_entry,
    generate_native_expression_entry,
)
from tools.generate_native_function_entry import (
    generate_native_function_entry,
    rewrite_control_expression_imports,
)
from tools.namespace_generated_module import namespace_generated_module
from tools.rewrite_generated_function_stack import rewrite_generated_function
from tools.rewrite_generated_parser_safe import (
    rewrite_generated_control,
    rewrite_generated_expression,
    rewrite_generated_scalar,
)


def _load(path: Path, name: str):
    qualified = f"portapy.{name}"
    specification = importlib.util.spec_from_file_location(qualified, path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[qualified] = module
    specification.loader.exec_module(module)
    return module


def _api(tmp_path: Path):
    names = (
        "_kwargs_scalar_test",
        "_kwargs_expression_test",
        "_kwargs_control_test",
        "_kwargs_function_test",
    )
    paths = tuple(tmp_path / f"{name}.py" for name in names)
    rewrite_generated_scalar(generate_namespaced_scalar_entry(paths[0]))
    rewrite_generated_expression(
        generate_native_expression_entry(paths[1], scalar_module=names[0])
    )
    namespace_generated_module(paths[1], "_expr_")
    rewrite_generated_control(
        generate_native_control_entry(
            paths[2],
            expression_module=names[1],
            scalar_module=names[0],
        )
    )
    rewrite_control_expression_imports(paths[2], names[1])
    namespace_generated_module(paths[2], "_ctrl_")
    rewrite_generated_function(
        generate_native_function_entry(
            paths[3],
            scalar_module=names[0],
            expression_module=names[1],
            control_module=names[2],
        )
    )
    _load(paths[0], names[0])
    _load(paths[1], names[1])
    _load(paths[2], names[2])
    return _load(paths[3], names[3]), names, paths


def _exec(api, runtime: int, source: str) -> int:
    return api._portapy_exec_span_impl(runtime, source, len(source))


def _eval_int(api, runtime: int, source: str) -> int:
    value = api._portapy_eval_span_impl(runtime, source, len(source))
    assert value != 0
    return base._portapy_value_as_i64_impl(runtime, value)


def _eval_bool(api, runtime: int, source: str) -> bool:
    value = api._portapy_eval_span_impl(runtime, source, len(source))
    assert value != 0
    return base._portapy_value_as_bool_impl(runtime, value) != 0


def test_generated_source_contains_owned_kwargs_dictionary(tmp_path: Path) -> None:
    _, names, paths = _api(tmp_path)
    try:
        scalar = paths[0].read_text(encoding="utf-8")
        function = paths[3].read_text(encoding="utf-8")
        assert "PORTAPY_VALUE_DICT = 9" in scalar
        assert "def _scalar_dict_get(" in scalar
        assert "_PARAMETER_VAR_KEYWORD = 4" in function
        assert "def _var_keyword_index(" in function
        assert "def _build_kwargs_dict(" in function
        assert "_scalar_dict_entry_key.append(_call_argument_names[argument_index])" in function
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_empty_and_nonempty_kwargs_are_indexable_dictionaries(tmp_path: Path) -> None:
    api, names, _ = _api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        source = (
            "def summarize(**values):\n"
            "    if values:\n"
            "        return len(values) + values[\"left\"] + values[\"right\"]\n"
            "    return 0\n"
            "empty = summarize()\n"
            "filled = summarize(left=18, right=22)\n"
        )
        assert _exec(api, runtime, source) == base.PORTAPY_OK
        assert _eval_int(api, runtime, "empty") == 0
        assert _eval_int(api, runtime, "filled") == 42
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_kwargs_mix_with_fixed_varargs_and_keyword_only_parameters(tmp_path: Path) -> None:
    api, names, _ = _api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        source = (
            "def combine(head, /, middle=2, *tail, scale=1, **options):\n"
            "    total = head + middle + len(tail) + len(options)\n"
            "    if tail:\n"
            "        total += tail[0]\n"
            "    if options:\n"
            "        total += options[\"bonus\"]\n"
            "    return total * scale\n"
            "plain = combine(10)\n"
            "mixed = combine(10, 3, 4, scale=2, bonus=3)\n"
        )
        assert _exec(api, runtime, source) == base.PORTAPY_OK
        assert _eval_int(api, runtime, "plain") == 12
        assert _eval_int(api, runtime, "mixed") == 42
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_positional_only_names_can_be_captured_by_kwargs(tmp_path: Path) -> None:
    api, names, _ = _api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        source = (
            "def route(value, /, **options):\n"
            "    return value + options[\"value\"]\n"
            "answer = route(20, value=22)\n"
        )
        assert _exec(api, runtime, source) == base.PORTAPY_OK
        assert _eval_int(api, runtime, "answer") == 42
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_kwargs_survive_nested_calls_equality_and_local_restore(tmp_path: Path) -> None:
    api, names, _ = _api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        source = (
            "options = 100\n"
            "def capture(**options):\n"
            "    return options\n"
            "def outer(value, **rest):\n"
            "    return value + rest[\"bonus\"]\n"
            "saved = capture(alpha=18, beta=24)\n"
            "same = saved == capture(alpha=18, beta=24)\n"
            "answer = outer(saved[\"alpha\"], bonus=saved[\"beta\"])\n"
        )
        assert _exec(api, runtime, source) == base.PORTAPY_OK
        assert _eval_bool(api, runtime, "same") is True
        assert _eval_int(api, runtime, "answer") == 42
        assert _eval_int(api, runtime, "options") == 100
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_kwargs_errors_are_structured(tmp_path: Path) -> None:
    api, names, _ = _api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        assert _exec(api, runtime, "def capture(**values):\n    return values\n") == base.PORTAPY_OK

        duplicate = "capture(value=1, value=2)"
        result = api._portapy_eval_span_impl(runtime, duplicate, len(duplicate))
        assert result == 0
        assert api._portapy_last_status_impl() == base.PORTAPY_TYPE_ERROR

        missing_key = (
            "def missing(**values):\n"
            "    return values[\"absent\"]\n"
            "result = missing(present=1)\n"
        )
        assert _exec(api, runtime, missing_key) == base.PORTAPY_NOT_FOUND

        invalid = (
            "def bad(**):\n    return 1\n",
            "def bad(**values, other):\n    return other\n",
            "def bad(**values=1):\n    return 1\n",
            "def bad(*, **values):\n    return 1\n",
        )
        for source in invalid:
            assert _exec(api, runtime, source) == base.PORTAPY_COMPILE_ERROR
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)
