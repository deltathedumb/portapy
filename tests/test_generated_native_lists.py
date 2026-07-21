from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from portapy import native_api as base
from portapy.native_api_host import _portapy_set_global_span_impl
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
        "_list_scalar_test",
        "_list_expression_test",
        "_list_control_test",
        "_list_function_test",
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
    scalar = _load(paths[0], names[0])
    _load(paths[1], names[1])
    _load(paths[2], names[2])
    return scalar, _load(paths[3], names[3]), names, paths


def _eval(api, runtime: int, source: str) -> int:
    value = api._portapy_eval_span_impl(runtime, source, len(source))
    assert value != 0
    return value


def _eval_int(api, runtime: int, source: str) -> int:
    return base._portapy_value_as_i64_impl(runtime, _eval(api, runtime, source))


def _eval_bool(api, runtime: int, source: str) -> bool:
    return base._portapy_value_as_bool_impl(runtime, _eval(api, runtime, source)) != 0


def test_generated_source_contains_owned_list_storage(tmp_path: Path) -> None:
    _, _, names, paths = _api(tmp_path)
    try:
        scalar = paths[0].read_text(encoding="utf-8")
        expression = paths[1].read_text(encoding="utf-8")
        assert "PORTAPY_VALUE_LIST = 10" in scalar
        assert "def _scalar_append_list(" in scalar
        assert "def _scalar_list_get(" in scalar
        assert "def _scalar_list_set(" in scalar
        assert "def _scalar_list_append(" in scalar
        assert "_scalar_list_size_unchecked," in expression
        assert "kind == 10" in expression
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_list_literals_indexing_length_and_truthiness(tmp_path: Path) -> None:
    _, api, names, _ = _api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        assert _eval_int(api, runtime, "[1, 2, 3][0]") == 1
        assert _eval_int(api, runtime, "[1, 2, 3][-1]") == 3
        assert _eval_int(api, runtime, "[1, [2, 3]][1][0]") == 2
        assert _eval_int(api, runtime, "len([])") == 0
        assert _eval_int(api, runtime, "len([1, 2, 3])") == 3
        assert _eval_bool(api, runtime, "not []") is True
        assert _eval_bool(api, runtime, "not [1]") is False
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_list_structural_equality(tmp_path: Path) -> None:
    _, api, names, _ = _api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        assert _eval_bool(api, runtime, "[1, [2, 3]] == [1, [2, 3]]") is True
        assert _eval_bool(api, runtime, "[1, 2] != [1, 3]") is True
        assert _eval_bool(api, runtime, "[1, 2] == (1, 2)") is False
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_list_storage_supports_replacement_and_append(tmp_path: Path) -> None:
    scalar, api, names, _ = _api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        value = _eval(api, runtime, "[18, 1]")
        replacement = _eval(api, runtime, "20")
        appended = _eval(api, runtime, "22")
        try:
            assert scalar._scalar_list_set(runtime, value, 1, replacement) == base.PORTAPY_OK
            assert scalar._scalar_list_append(runtime, value, appended) == base.PORTAPY_OK
            name = "values"
            assert _portapy_set_global_span_impl(runtime, name, len(name), value) == base.PORTAPY_OK
            assert _eval_int(api, runtime, "values[0] + values[1] + values[2]") == 60
            assert _eval_int(api, runtime, "len(values)") == 3
        finally:
            scalar._scalar_release(runtime, replacement)
            scalar._scalar_release(runtime, appended)
            scalar._scalar_release(runtime, value)
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_lists_work_inside_native_functions(tmp_path: Path) -> None:
    _, api, names, _ = _api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        source = (
            "def summarize(values):\n"
            "    if values:\n"
            "        return values[0] + values[-1] + len(values)\n"
            "    return 0\n"
            "answer = summarize([18, 1, 20])\n"
            "empty = summarize([])\n"
        )
        assert api._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK
        assert _eval_int(api, runtime, "answer") == 41
        assert _eval_int(api, runtime, "empty") == 0
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)


def test_list_index_errors_are_structured(tmp_path: Path) -> None:
    _, api, names, _ = _api(tmp_path)
    try:
        runtime = api._portapy_runtime_create_impl()
        missing = api._portapy_eval_span_impl(runtime, "[1][2]", len("[1][2]"))
        assert missing == 0
        assert api._portapy_last_status_impl() == base.PORTAPY_RUNTIME_ERROR

        wrong = api._portapy_eval_span_impl(runtime, '[1]["x"]', len('[1]["x"]'))
        assert wrong == 0
        assert api._portapy_last_status_impl() == base.PORTAPY_TYPE_ERROR
    finally:
        for name in reversed(names):
            sys.modules.pop(f"portapy.{name}", None)
