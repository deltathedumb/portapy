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
        "_dict_scalar_test",
        "_dict_expression_test",
        "_dict_control_test",
        "_dict_function_test",
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


def _eval(api, runtime: int, source: str) -> int:
    value = api._portapy_eval_span_impl(runtime, source, len(source))
    assert value != 0
    return value


def _eval_int(api, runtime: int, source: str) -> int:
    return base._portapy_value_as_i64_impl(runtime, _eval(api, runtime, source))


def _eval_bool(api, runtime: int, source: str) -> bool:
    return base._portapy_value_as_bool_impl(runtime, _eval(api, runtime, source)) != 0


def test_generated_dictionary_source_is_static_and_namespaced(tmp_path: Path) -> None:
    _, names, paths = _api(tmp_path)
    try:
        scalar = paths[0].read_text(encoding="utf-8")
        expression = paths[1].read_text(encoding="utf-8")
        assert "PORTAPY_VALUE_DICT = 9" in scalar
        assert "def _scalar_append_dict(" in scalar
        assert "def _scalar_dict_get(" in scalar
        assert "def _scalar_dict_find_entry(" in scalar
        assert "_scalar_dict_size_unchecked," in expression
        assert "kind == 9" in expression
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_dictionary_literals_indexing_length_and_duplicate_keys(tmp_path: Path) -> None:
    api, names, _ = _api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        assert _eval_int(api, runtime, '{"answer": 42}["answer"]') == 42
        assert _eval_int(api, runtime, '{"outer": {"inner": 42}}["outer"]["inner"]') == 42
        assert _eval_int(api, runtime, "len({})") == 0
        assert _eval_int(api, runtime, 'len({"a": 1, "b": 2})') == 2
        assert _eval_int(api, runtime, '{"a": 1, "a": 42}["a"]') == 42
        assert _eval_int(api, runtime, '{1: 40, 2: 42}[2]') == 42
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_dictionary_truthiness_and_structural_equality(tmp_path: Path) -> None:
    api, names, _ = _api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        assert _eval_bool(api, runtime, "not {}") is True
        assert _eval_bool(api, runtime, 'not {"a": 1}') is False
        assert _eval_bool(api, runtime, '{"a": 1, "b": 2} == {"b": 2, "a": 1}') is True
        assert _eval_bool(api, runtime, '{"a": {"b": 2}} != {"a": {"b": 3}}') is True
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_dictionary_missing_key_is_structured(tmp_path: Path) -> None:
    api, names, _ = _api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        source = '{"a": 1}["missing"]'
        result = api._portapy_eval_span_impl(runtime, source, len(source))
        assert result == 0
        assert api._portapy_last_status_impl() == base.PORTAPY_RUNTIME_ERROR
        assert api._portapy_error_type_size_impl(runtime) == len("KeyError")
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_dictionaries_work_in_native_functions_and_control_flow(tmp_path: Path) -> None:
    api, names, _ = _api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        source = (
            'values = {"first": 18, "last": 20}\n'
            "empty_values = {}\n"
            "def summarize(values):\n"
            "    if values:\n"
            '        return values["first"] + values["last"] + len(values)\n'
            "    return 0\n"
            "answer = summarize(values)\n"
            "empty = summarize(empty_values)\n"
        )
        assert api._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK
        assert _eval_int(api, runtime, "answer") == 40
        assert _eval_int(api, runtime, "empty") == 0
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)
