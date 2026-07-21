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
from tools.generate_native_host_entry import generate_native_host_entry
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
    scalar_name = "_generated_host_scalar_test"
    expression_name = "_generated_host_expression_test"
    control_name = "_generated_host_control_test"
    function_name = "_generated_host_function_test"
    host_name = "_generated_host_entry_test"
    scalar = tmp_path / f"{scalar_name}.py"
    expression = tmp_path / f"{expression_name}.py"
    control = tmp_path / f"{control_name}.py"
    function = tmp_path / f"{function_name}.py"
    host = tmp_path / f"{host_name}.py"

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
    namespace_generated_module(function, "_fn_")
    generate_native_host_entry(
        host,
        scalar_module=scalar_name,
        function_module=function_name,
    )
    return (
        (scalar_name, expression_name, control_name, function_name, host_name),
        (scalar, expression, control, function, host),
    )


def test_generated_host_entry_uses_namespaced_dependencies(tmp_path: Path) -> None:
    _, paths = _generate(tmp_path)
    function_source = paths[3].read_text(encoding="utf-8")
    host_source = paths[4].read_text(encoding="utf-8")

    assert "def _fn_parse_call_or_expression(" in function_source
    assert "def _fn_portapy_exec_span_impl(" in function_source
    assert "native_api_functions import" not in host_source
    assert "native_api_scalar import" not in host_source
    assert "_fn_parse_call_or_expression," in host_source
    assert "_scalar_retain_global," in host_source
    assert " as _function_exec_span" not in host_source


def test_generated_host_entry_resolves_somnia_shaped_path(tmp_path: Path) -> None:
    names, paths = _generate(tmp_path)
    for path, name in zip(paths[:-1], names[:-1]):
        _load(path, name)
    api = _load(paths[-1], names[-1])
    try:
        runtime = api._portapy_runtime_create_impl()
        game = api._portapy_value_from_host_object_impl(runtime, 100)
        provider = api._portapy_value_from_host_object_impl(runtime, 200)
        http_provider = api._portapy_value_from_host_object_impl(runtime, 300)
        assert api._portapy_host_set_attr_span_impl(runtime, game, "provider", 8, provider) == base.PORTAPY_OK
        assert (
            api._portapy_host_set_attr_span_impl(
                runtime,
                provider,
                "HttpProvider",
                len("HttpProvider"),
                http_provider,
            )
            == base.PORTAPY_OK
        )
        assert api._portapy_set_global_span_impl(runtime, "game", 4, game) == base.PORTAPY_OK

        source = "http_provider = game.provider.HttpProvider\n"
        assert api._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK
        captured = api._portapy_get_global_span_impl(runtime, "http_provider", len("http_provider"))
        assert api._portapy_value_get_host_id_impl(runtime, captured) == 300
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)
