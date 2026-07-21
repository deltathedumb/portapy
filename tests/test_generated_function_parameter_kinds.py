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
        "_parameter_kind_scalar_test",
        "_parameter_kind_expression_test",
        "_parameter_kind_control_test",
        "_parameter_kind_function_test",
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


def test_generated_source_contains_parameter_kind_helpers(tmp_path: Path) -> None:
    _, names, paths = _api(tmp_path)
    try:
        source = paths[3].read_text(encoding="utf-8")
        assert "_PARAMETER_POSITIONAL_ONLY = 1" in source
        assert "_PARAMETER_KEYWORD_ONLY = 2" in source
        assert "def _parameter_kind(" in source
        assert "def _next_positional_parameter(" in source
        assert "positional-only argument passed as keyword" in source
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_positional_only_and_keyword_only_calls(tmp_path: Path) -> None:
    api, names, _ = _api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        source = (
            "def route(left, /, right=2, *, scale=3):\n"
            "    return (left + right) * scale\n"
            "def required(value, *, offset):\n"
            "    return value + offset\n"
            "qualified = route(10, scale=4)\n"
            "mixed = route(18, right=3, scale=2)\n"
            "required_result = required(40, offset=2)\n"
        )
        assert _exec(api, runtime, source) == base.PORTAPY_OK
        assert _eval_int(api, runtime, "qualified") == 48
        assert _eval_int(api, runtime, "mixed") == 42
        assert _eval_int(api, runtime, "required_result") == 42

        type_errors = (
            "route(left=10)",
            "route(10, 2, 4)",
            "required(40)",
            "required(40, 2)",
        )
        for expression in type_errors:
            result = api._portapy_eval_span_impl(runtime, expression, len(expression))
            assert result == 0
            assert api._portapy_last_status_impl() == base.PORTAPY_TYPE_ERROR
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_marker_defaults_are_captured_at_definition(tmp_path: Path) -> None:
    api, names, _ = _api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        source = (
            "seed = 3\n"
            "def captured(value=seed, /, *, offset=2):\n"
            "    return value + offset\n"
            "seed = 100\n"
            "answer = captured()\n"
        )
        assert _exec(api, runtime, source) == base.PORTAPY_OK
        assert _eval_int(api, runtime, "answer") == 5
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_invalid_parameter_markers_report_compile_error(tmp_path: Path) -> None:
    api, names, _ = _api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        invalid_definitions = (
            "def bad(*):\n    return 1\n",
            "def bad(/, value):\n    return value\n",
            "def bad(value, /, /):\n    return value\n",
            "def bad(value=1, /, other):\n    return other\n",
            "def bad(*args):\n    return 1\n",
            "def bad(**kwargs):\n    return 1\n",
        )
        for source in invalid_definitions:
            assert _exec(api, runtime, source) == base.PORTAPY_COMPILE_ERROR
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)
