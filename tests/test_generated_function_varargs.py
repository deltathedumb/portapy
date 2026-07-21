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
        "_varargs_scalar_test",
        "_varargs_expression_test",
        "_varargs_control_test",
        "_varargs_function_test",
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


def test_generated_source_contains_varargs_tuple_packing(tmp_path: Path) -> None:
    _, names, paths = _api(tmp_path)
    try:
        source = paths[3].read_text(encoding="utf-8")
        assert "_PARAMETER_VAR_POSITIONAL = 3" in source
        assert "def _var_positional_index(" in source
        assert "def _build_varargs_tuple(" in source
        assert "_scalar_tuple_item_owner.append(value)" in source
        assert "vararg_positions: list[int] = []" in source
        assert "rewrite_generated_function_varargs" not in source
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_empty_and_nonempty_varargs_are_real_tuples(tmp_path: Path) -> None:
    api, names, _ = _api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        source = (
            "def summarize(*values):\n"
            "    if values:\n"
            "        return len(values) + values[0] + values[-1]\n"
            "    return 0\n"
            "empty = summarize()\n"
            "filled = summarize(18, 1, 20)\n"
        )
        assert _exec(api, runtime, source) == base.PORTAPY_OK
        assert _eval_int(api, runtime, "empty") == 0
        assert _eval_int(api, runtime, "filled") == 41
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_varargs_mix_with_fixed_defaults_and_keyword_only_parameters(tmp_path: Path) -> None:
    api, names, _ = _api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        source = (
            "def combine(head, /, middle=2, *tail, scale=1):\n"
            "    total = head + middle + len(tail)\n"
            "    if tail:\n"
            "        total += tail[0] + tail[-1]\n"
            "    return total * scale\n"
            "defaulted = combine(10)\n"
            "positional = combine(10, 3, 4, 5)\n"
            "mixed = combine(10, 3, 4, 5, scale=2)\n"
            "keyword_middle = combine(10, middle=4, scale=3)\n"
        )
        assert _exec(api, runtime, source) == base.PORTAPY_OK
        assert _eval_int(api, runtime, "defaulted") == 12
        assert _eval_int(api, runtime, "positional") == 24
        assert _eval_int(api, runtime, "mixed") == 48
        assert _eval_int(api, runtime, "keyword_middle") == 42
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_varargs_survive_nested_calls_and_local_restore(tmp_path: Path) -> None:
    api, names, _ = _api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        source = (
            "values = 100\n"
            "def pick(*values):\n"
            "    return values[0] + values[-1]\n"
            "def outer(value, *rest):\n"
            "    return pick(value, rest[0], rest[-1])\n"
            "answer = outer(20, 1, 22)\n"
        )
        assert _exec(api, runtime, source) == base.PORTAPY_OK
        assert _eval_int(api, runtime, "answer") == 42
        assert _eval_int(api, runtime, "values") == 100
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_varargs_call_and_definition_errors_are_structured(tmp_path: Path) -> None:
    api, names, _ = _api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        assert _exec(api, runtime, "def collect(*items):\n    return len(items)\n") == base.PORTAPY_OK

        result = api._portapy_eval_span_impl(
            runtime,
            "collect(items=1)",
            len("collect(items=1)"),
        )
        assert result == 0
        assert api._portapy_last_status_impl() == base.PORTAPY_TYPE_ERROR

        invalid = (
            "def bad(*left, *right):\n    return 1\n",
            "def bad(value, *):\n    return value\n",
            "def bad(*items=1):\n    return 1\n",
        )
        for source in invalid:
            assert _exec(api, runtime, source) == base.PORTAPY_COMPILE_ERROR
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)
