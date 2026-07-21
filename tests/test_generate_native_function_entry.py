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


def _generate(tmp_path: Path):
    scalar_name = "_generated_function_scalar_test"
    expression_name = "_generated_function_expression_test"
    control_name = "_generated_function_control_test"
    function_name = "_generated_function_entry_test"
    scalar = tmp_path / f"{scalar_name}.py"
    expression = tmp_path / f"{expression_name}.py"
    control = tmp_path / f"{control_name}.py"
    function = tmp_path / f"{function_name}.py"

    rewrite_generated_scalar(generate_namespaced_scalar_entry(scalar))
    rewrite_generated_expression(
        generate_native_expression_entry(expression, scalar_module=scalar_name)
    )
    namespace_generated_module(expression, "_expr_")
    rewrite_generated_control(
        generate_native_control_entry(
            control,
            expression_module=expression_name,
            scalar_module=scalar_name,
        )
    )
    rewrite_control_expression_imports(control, expression_name)
    namespace_generated_module(control, "_ctrl_")
    rewrite_generated_function(
        generate_native_function_entry(
            function,
            scalar_module=scalar_name,
            expression_module=expression_name,
            control_module=control_name,
        )
    )
    return (
        scalar_name,
        expression_name,
        control_name,
        function_name,
        scalar,
        expression,
        control,
        function,
    )


def test_generated_function_entry_has_only_named_static_dependencies(tmp_path: Path) -> None:
    generated = _generate(tmp_path)
    expression_source = generated[5].read_text(encoding="utf-8")
    control_source = generated[6].read_text(encoding="utf-8")
    function_source = generated[7].read_text(encoding="utf-8")

    assert "def _expr_parse_boolean_expression(" in expression_source
    assert "def _ctrl_portapy_exec_span_impl(" in control_source
    assert "_expr_parse_boolean_expression as _parse_boolean_expression" in control_source
    assert "native_api_control import" not in function_source
    assert "native_api_expressions import" not in function_source
    assert "native_api_scalar import" not in function_source
    assert "_ctrl_portapy_exec_span_impl," in function_source
    assert "_expr_parse_boolean_expression," in function_source
    assert "_expr_truthy," in function_source
    assert "_scalar_binary," in function_source
    assert " as _control_exec_span" not in function_source
    assert " as _parse_boolean_expression" not in function_source
    assert " as _retain_global" not in function_source
    assert "str(header[0])" not in function_source
    assert "str(header[1])" not in function_source
    assert "str(call[0])" not in function_source
    assert "str(assignment[0])" not in function_source
    assert "from .native_api import _last_status" not in function_source
    assert 'elif char == "\\\\":' in function_source
    assert "_call_argument_top: list[int] = [1]" in function_source
    assert '_call_argument_names: list[str] = [""]' in function_source
    assert "_call_bound_top: list[int] = [1]" in function_source
    assert "def _parameter_default_bounds(" in function_source
    assert "def _call_keyword_bounds(" in function_source
    assert "def _parameter_index(" in function_source
    assert "_FUNCTION_FLOW_RETURN = 3" in function_source
    assert "def _execute_function_block(" in function_source


def test_generated_function_entry_executes_positional_calls(tmp_path: Path) -> None:
    generated = _generate(tmp_path)
    names = generated[:4]
    paths = generated[4:]
    _load(paths[0], names[0])
    _load(paths[1], names[1])
    _load(paths[2], names[2])
    api = _load(paths[3], names[3])
    try:
        runtime = api._portapy_runtime_create_impl()
        source = (
            "def zero():\n"
            "    return 7\n"
            "def add(left, right):\n"
            "    total = left + right\n"
            "    return total\n"
            "answer = add(20, 22)\n"
        )
        assert api._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK
        answer = api._portapy_eval_span_impl(runtime, "answer", len("answer"))
        assert base._portapy_value_as_i64_impl(runtime, answer) == 42
        zero = api._portapy_eval_span_impl(runtime, "zero()", len("zero()"))
        assert base._portapy_value_as_i64_impl(runtime, zero) == 7
        nested = api._portapy_eval_span_impl(
            runtime,
            "add(add(10, 11), 21)",
            len("add(add(10, 11), 21)"),
        )
        assert base._portapy_value_as_i64_impl(runtime, nested) == 42
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_generated_function_entry_executes_nested_control_flow(tmp_path: Path) -> None:
    generated = _generate(tmp_path)
    names = generated[:4]
    paths = generated[4:]
    _load(paths[0], names[0])
    _load(paths[1], names[1])
    _load(paths[2], names[2])
    api = _load(paths[3], names[3])
    try:
        runtime = api._portapy_runtime_create_impl()
        source = (
            "def classify(value):\n"
            "    if value == 0:\n"
            "        return 100\n"
            "    else:\n"
            "        total = 0\n"
            "        current = 0\n"
            "        while current < value:\n"
            "            current += 1\n"
            "            if current == 2:\n"
            "                continue\n"
            "            total += current\n"
            "            if total > 6:\n"
            "                break\n"
            "        return total\n"
            "zero = classify(0)\n"
            "small = classify(3)\n"
            "large = classify(5)\n"
        )
        assert api._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK
        zero = api._portapy_eval_span_impl(runtime, "zero", len("zero"))
        small = api._portapy_eval_span_impl(runtime, "small", len("small"))
        large = api._portapy_eval_span_impl(runtime, "large", len("large"))
        assert base._portapy_value_as_i64_impl(runtime, zero) == 100
        assert base._portapy_value_as_i64_impl(runtime, small) == 4
        assert base._portapy_value_as_i64_impl(runtime, large) == 8
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_generated_function_entry_binds_defaults_and_keywords(tmp_path: Path) -> None:
    generated = _generate(tmp_path)
    names = generated[:4]
    paths = generated[4:]
    _load(paths[0], names[0])
    _load(paths[1], names[1])
    _load(paths[2], names[2])
    api = _load(paths[3], names[3])
    try:
        runtime = api._portapy_runtime_create_impl()
        source = (
            "def combine(left, right=2, scale=3):\n"
            "    return (left + right) * scale\n"
            "defaulted = combine(12)\n"
            "mixed = combine(10, scale=4)\n"
            "reordered = combine(scale=2, left=18, right=3)\n"
            "nested = combine(combine(1), scale=2)\n"
        )
        assert api._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK
        expected = {
            "defaulted": 42,
            "mixed": 48,
            "reordered": 42,
            "nested": 22,
        }
        for name, wanted in expected.items():
            value = api._portapy_eval_span_impl(runtime, name, len(name))
            assert base._portapy_value_as_i64_impl(runtime, value) == wanted

        bad_calls = (
            "combine()",
            "combine(1, left=2)",
            "combine(1, unknown=2)",
        )
        for expression in bad_calls:
            value = api._portapy_eval_span_impl(runtime, expression, len(expression))
            assert value == 0
            assert api._portapy_last_status_impl() == base.PORTAPY_TYPE_ERROR

        syntax = "combine(left=1, 2)"
        value = api._portapy_eval_span_impl(runtime, syntax, len(syntax))
        assert value == 0
        assert api._portapy_last_status_impl() == base.PORTAPY_COMPILE_ERROR
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)
