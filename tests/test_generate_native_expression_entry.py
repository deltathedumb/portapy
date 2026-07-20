from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from portapy import native_api as base
from tools.generate_native_expression_entry import generate_native_expression_entry


def _load_generated(path: Path):
    name = "portapy._generated_native_expression_test"
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    try:
        specification.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


def test_generator_produces_static_import_safe_source(tmp_path: Path) -> None:
    output = generate_native_expression_entry(tmp_path / "native_api_generated.py")
    source = output.read_text(encoding="utf-8")

    assert "native_api_scalar import" in source
    assert "_parse_scalar_expression" in source
    assert "native_api_expressions as" not in source
    assert "._parse_typed_complete =" not in source


def test_generated_entry_preserves_boolean_and_scalar_semantics(tmp_path: Path) -> None:
    api = _load_generated(
        generate_native_expression_entry(tmp_path / "native_api_generated.py")
    )
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
