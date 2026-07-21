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
from tools.rewrite_generated_parser_safe import (
    rewrite_generated_control,
    rewrite_generated_expression,
    rewrite_generated_scalar,
)


def _load_generated(path: Path, name: str):
    qualified = f"portapy.{name}"
    specification = importlib.util.spec_from_file_location(qualified, path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[qualified] = module
    specification.loader.exec_module(module)
    return module


def _generate_scalar(path: Path) -> Path:
    return rewrite_generated_scalar(generate_namespaced_scalar_entry(path))


def _generate_expression(path: Path, scalar_name: str) -> Path:
    return rewrite_generated_expression(
        generate_native_expression_entry(path, scalar_module=scalar_name)
    )


def _generate_control(path: Path, expression_name: str, scalar_name: str) -> Path:
    return rewrite_generated_control(
        generate_native_control_entry(
            path,
            expression_module=expression_name,
            scalar_module=scalar_name,
        )
    )


def test_generator_produces_namespace_safe_source(tmp_path: Path) -> None:
    scalar_name = "_generated_scalar_source_test"
    expression_name = "_generated_expression_source_test"
    scalar_output = _generate_scalar(tmp_path / f"{scalar_name}.py")
    expression_output = _generate_expression(
        tmp_path / f"{expression_name}.py",
        scalar_name,
    )
    scalar_source = scalar_output.read_text(encoding="utf-8")
    expression_source = expression_output.read_text(encoding="utf-8")

    assert "def _scalar_parse_comparison(" in scalar_source
    assert "def _parse_comparison(" not in scalar_source
    assert scalar_source.count("for operator in operators") == 1
    assert "def _scalar_parse_multiply(" in scalar_source
    assert 'source[operator_at] == "*"' in scalar_source
    assert 'if operator[0] == "":' in scalar_source
    assert f"from .{scalar_name} import" in expression_source
    assert "_scalar_parse_comparison" in expression_source
    assert 'assignment[0] == "*="' in expression_source
    assert "str(assignment[0])[:-1]" not in expression_source
    assert "native_api_expressions as" not in expression_source
    assert "._parse_typed_complete =" not in expression_source


def test_generated_entry_preserves_boolean_and_scalar_semantics(tmp_path: Path) -> None:
    scalar_name = "_generated_scalar_test"
    expression_name = "_generated_native_expression_test"
    _load_generated(
        _generate_scalar(tmp_path / f"{scalar_name}.py"),
        scalar_name,
    )
    api = _load_generated(
        _generate_expression(tmp_path / f"{expression_name}.py", scalar_name),
        expression_name,
    )
    try:
        runtime = api._portapy_runtime_create_impl()

        multiplied = api._portapy_eval_span_impl(runtime, "1 + 2 * 3", len("1 + 2 * 3"))
        assert multiplied != 0
        assert base._portapy_value_as_i64_impl(runtime, multiplied) == 7

        shifted = api._portapy_eval_span_impl(runtime, "1 << 4 | 3", len("1 << 4 | 3"))
        assert shifted != 0
        assert base._portapy_value_as_i64_impl(runtime, shifted) == 19

        short_circuit = api._portapy_eval_span_impl(
            runtime,
            "False and missing_name",
            len("False and missing_name"),
        )
        assert short_circuit != 0
        assert base._portapy_value_as_bool_impl(runtime, short_circuit) == 0

        source = 'name = "Som" + "nia"\nanswer = 5\nanswer *= 3\nanswer += 27\npass\n'
        assert api._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK

        answer = api._portapy_get_global_span_impl(runtime, "answer", len("answer"))
        assert base._portapy_value_as_i64_impl(runtime, answer) == 42
    finally:
        sys.modules.pop(f"portapy.{expression_name}", None)
        sys.modules.pop(f"portapy.{scalar_name}", None)


def test_generated_control_flow_uses_general_scalar_grammar(tmp_path: Path) -> None:
    scalar_name = "_generated_scalar_for_control_test"
    expression_name = "_generated_expression_for_control_test"
    control_name = "_generated_control_test"
    _load_generated(
        _generate_scalar(tmp_path / f"{scalar_name}.py"),
        scalar_name,
    )
    _load_generated(
        _generate_expression(tmp_path / f"{expression_name}.py", scalar_name),
        expression_name,
    )
    control = _load_generated(
        _generate_control(
            tmp_path / f"{control_name}.py",
            expression_name,
            scalar_name,
        ),
        control_name,
    )
    try:
        runtime = control._portapy_runtime_create_impl()
        source = (
            "count = 0\n"
            "answer = 1\n"
            "while count < 4:\n"
            "    count += 1\n"
            "    if count == 2:\n"
            "        continue\n"
            "    answer *= 2\n"
            "    answer += count << 1\n"
        )
        assert control._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK
        answer = control._portapy_get_global_span_impl(runtime, "answer", len("answer"))
        assert base._portapy_value_as_i64_impl(runtime, answer) == 42
    finally:
        sys.modules.pop(f"portapy.{control_name}", None)
        sys.modules.pop(f"portapy.{expression_name}", None)
        sys.modules.pop(f"portapy.{scalar_name}", None)
