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


def _generated_api(tmp_path: Path):
    scalar_name = "_captured_default_scalar_test"
    expression_name = "_captured_default_expression_test"
    control_name = "_captured_default_control_test"
    function_name = "_captured_default_function_test"
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

    names = (scalar_name, expression_name, control_name, function_name)
    paths = (scalar, expression, control, function)
    _load(scalar, scalar_name)
    _load(expression, expression_name)
    _load(control, control_name)
    api = _load(function, function_name)
    return api, names, paths


def _exec(api, runtime: int, source: str) -> int:
    return api._portapy_exec_span_impl(runtime, source, len(source))


def _eval_int(api, runtime: int, source: str) -> int:
    value = api._portapy_eval_span_impl(runtime, source, len(source))
    assert value != 0
    return base._portapy_value_as_i64_impl(runtime, value)


def test_generated_source_uses_captured_default_storage(tmp_path: Path) -> None:
    api, names, paths = _generated_api(tmp_path)
    try:
        source = paths[3].read_text(encoding="utf-8")
        assert "_captured_default_slot: list[int] = [0]" in source
        assert "def _capture_function_defaults(" in source
        assert "def _find_captured_function_default(" in source
        assert "captured_default = _find_captured_function_default(slot, index)" in source
        assert "parsed_default = _expr_parse_boolean_expression(" not in source
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_default_expression_is_captured_when_definition_executes(tmp_path: Path) -> None:
    api, names, _ = _generated_api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        source = (
            "seed = 3\n"
            "def calculate(value=seed + 2):\n"
            "    return value * 2\n"
            "seed = 20\n"
            "captured = calculate()\n"
            "explicit = calculate(7)\n"
        )
        assert _exec(api, runtime, source) == base.PORTAPY_OK
        assert _eval_int(api, runtime, "captured") == 10
        assert _eval_int(api, runtime, "explicit") == 14
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_redefinition_replaces_captured_defaults(tmp_path: Path) -> None:
    api, names, _ = _generated_api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        assert _exec(
            api,
            runtime,
            "seed = 4\n"
            "def choose(value=seed):\n"
            "    return value\n",
        ) == base.PORTAPY_OK
        assert _eval_int(api, runtime, "choose()") == 4

        assert _exec(
            api,
            runtime,
            "seed = 9\n"
            "def choose(value=seed):\n"
            "    return value + 1\n"
            "seed = 100\n",
        ) == base.PORTAPY_OK
        assert _eval_int(api, runtime, "choose()") == 10
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_failed_redefinition_keeps_previous_function_and_capture(tmp_path: Path) -> None:
    api, names, _ = _generated_api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        assert _exec(
            api,
            runtime,
            "seed = 6\n"
            "def stable(value=seed):\n"
            "    return value\n",
        ) == base.PORTAPY_OK

        status = _exec(
            api,
            runtime,
            "def stable(value=missing_default):\n"
            "    return value + 100\n",
        )
        assert status == base.PORTAPY_NOT_FOUND
        assert _eval_int(api, runtime, "stable()") == 6
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)
