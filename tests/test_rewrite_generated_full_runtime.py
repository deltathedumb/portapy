from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tools.rewrite_generated_full_runtime import rewrite_generated_full_runtime


_ENTRY = '''from __future__ import annotations


def _portapy_eval_span_impl(runtime: int, source: str, source_size: int) -> int:
    return 1


def _portapy_exec_span_impl(runtime: int, source: str, source_size: int) -> int:
    return 0


def _portapy_value_get_host_id_impl(runtime: int, value: int) -> int:
    return 0


def _portapy_value_get_host_callable_id_impl(runtime: int, value: int) -> int:
    return 0


def _portapy_error_clear_impl(runtime: int) -> int:
    return 0


def _portapy_runtime_destroy_impl(runtime: int) -> int:
    return 0
'''


def test_full_runtime_rewrite_replaces_entrypoints_and_parses(tmp_path: Path) -> None:
    entry = tmp_path / "entry.py"
    entry.write_text(_ENTRY, encoding="utf-8")

    rewrite_generated_full_runtime(entry, target="linux")
    source = entry.read_text(encoding="utf-8")
    ast.parse(source)

    assert "def _incremental_portapy_exec_span_impl(" in source
    assert "def _incremental_portapy_eval_span_impl(" in source
    assert source.count("def _portapy_exec_span_impl(") == 1
    assert source.count("def _portapy_eval_span_impl(") == 1
    assert "compile_portable_source as _full_compile_source" in source
    assert "class _FullTracingVirtualMachine" in source
    assert "movq xmm0, rdi" in source
    assert "_full_sync_in(runtime, state)" in source
    assert "_full_sync_out(runtime, state)" in source


def test_windows_full_runtime_uses_windows_integer_register(tmp_path: Path) -> None:
    entry = tmp_path / "entry.py"
    entry.write_text(_ENTRY, encoding="utf-8")
    rewrite_generated_full_runtime(entry, target="windows")
    source = entry.read_text(encoding="utf-8")
    assert "movq xmm0, rcx" in source
    assert "movq xmm0, rdi" not in source


def test_full_runtime_rewrite_is_fail_closed(tmp_path: Path) -> None:
    entry = tmp_path / "entry.py"
    entry.write_text("from __future__ import annotations\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected exactly one"):
        rewrite_generated_full_runtime(entry, target="linux")


def test_full_runtime_rewrite_rejects_unknown_target(tmp_path: Path) -> None:
    entry = tmp_path / "entry.py"
    entry.write_text(_ENTRY, encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported full-runtime target"):
        rewrite_generated_full_runtime(entry, target="plan9")
