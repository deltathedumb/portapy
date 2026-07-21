from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from portapy import native_api as base
from tools.generate_native_control_entry import generate_native_control_entry
from tools.generate_native_expression_entry import generate_native_expression_entry


def _load_generated(path: Path, name: str):
    qualified = f"portapy.{name}"
    specification = importlib.util.spec_from_file_location(qualified, path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[qualified] = module
    specification.loader.exec_module(module)
    return module


def test_generator_produces_static_import_safe_source(tmp_path: Path) -> None:
    output = generate_native_expression_entry(tmp_path / "native_api_generated.py")
    source = output.read_text(encoding="utf-8")

    assert "native_api_scalar import" in source
    assert "_parse_scalar_expression" in source
    assert "native_api_expressions as" not in source
    assert "._parse_typed_complete =" not in source


def test_generated_entry_preserves_boolean_and_scalar_semantics(tmp_path: Path) -> None:
    name = "_generated_native_expression_test"
    api = _load_generated(
        generate_native_expression_entry(tmp_path / f"{name}.py"),
        name,
    )
    try:
        runtime = api._portapy_runtime_create_impl()

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

        source = 'name = "Som" + "nia"\nanswer = 5\nanswer += 37\npass\n'
        assert api._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK

        answer = api._portapy_get_global_span_impl(runtime, "answer", len("answer"))
        assert base._portapy_value_as_i64_impl(runtime, answer) == 42
    finally:
        sys.modules.pop(f"portapy.{name}", None)


def test_generated_control_flow_uses_general_scalar_grammar(tmp_path: Path) -> None:
    expression_name = "_generated_expression_for_control_test"
    control_name = "_generated_control_test"
    _load_generated(
        generate_native_expression_entry(tmp_path / f"{expression_name}.py"),
        expression_name,
    )
    control = _load_generated(
        generate_native_control_entry(
            tmp_path / f"{control_name}.py",
            expression_module=expression_name,
        ),
        control_name,
    )
    try:
        runtime = control._portapy_runtime_create_impl()
        source = (
            "count = 0\n"
            "answer = 0\n"
            "while count < 4:\n"
            "    count += 1\n"
            "    if count == 2:\n"
            "        continue\n"
            "    answer += count << 1\n"
        )
        assert control._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK
        answer = control._portapy_get_global_span_impl(runtime, "answer", len("answer"))
        assert base._portapy_value_as_i64_impl(runtime, answer) == 16
    finally:
        sys.modules.pop(f"portapy.{control_name}", None)
        sys.modules.pop(f"portapy.{expression_name}", None)
