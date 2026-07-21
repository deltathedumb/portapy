from __future__ import annotations

import ast
from pathlib import Path

from tools.generate_native_host_call_entry import generate_native_host_call_entry
from tools.rewrite_generated_full_vm_environment import (
    rewrite_generated_full_vm_environment,
)
from tools.rewrite_generated_host_calls import rewrite_generated_host_calls


def test_rewrite_installs_canonical_full_vm_environment(tmp_path: Path) -> None:
    output = tmp_path / "generated_environment.py"
    generate_native_host_call_entry(
        output,
        host_module="_native_host_dependency_linux",
        scalar_module="_native_scalar_dependency_linux",
    )
    rewrite_generated_host_calls(output)
    rewrite_generated_full_vm_environment(
        output,
        host_module="_native_host_dependency_linux",
        target="linux",
    )
    source = output.read_text(encoding="utf-8")
    ast.parse(source)

    assert source.count("def _incremental_portapy_exec_span_impl(") == 1
    assert source.count("def _incremental_portapy_eval_span_impl(") == 1
    assert source.count("def _incremental_portapy_runtime_destroy_impl(") == 1
    assert source.count("def _portapy_exec_span_impl(") == 1
    assert source.count("def _portapy_eval_span_impl(") == 1
    assert source.count("def _portapy_runtime_destroy_impl(") == 1

    assert "compile_portable_source as _full_compile_source" in source
    assert "from .core.vm import VirtualMachine as _FullVirtualMachine" in source
    assert "class _FullTracingVirtualMachine" in source
    assert "class _FullHostObject" in source
    assert "class _FullHostCallable" in source
    assert "_full_sync_in(runtime, state)" in source
    assert "_full_sync_out(runtime, state)" in source
    assert "movq xmm0, rdi" in source
    assert "from .native_vm_bridge import" not in source


def test_rewrite_infers_windows_target_from_host_module(tmp_path: Path) -> None:
    output = tmp_path / "generated_environment.py"
    generate_native_host_call_entry(
        output,
        host_module="generated_host_windows",
        scalar_module="generated_scalar_windows",
    )
    rewrite_generated_host_calls(output)
    rewrite_generated_full_vm_environment(
        output,
        host_module="generated_host_windows",
    )
    source = output.read_text(encoding="utf-8")
    assert "movq xmm0, rcx" in source


def test_rewrite_rejects_duplicate_application(tmp_path: Path) -> None:
    output = tmp_path / "generated_environment.py"
    generate_native_host_call_entry(
        output,
        host_module="generated_host",
        scalar_module="generated_scalar",
    )
    rewrite_generated_host_calls(output)
    rewrite_generated_full_vm_environment(output, host_module="generated_host")

    try:
        rewrite_generated_full_vm_environment(output, host_module="generated_host")
    except ValueError as error:
        assert "already contains" in str(error)
    else:
        raise AssertionError("duplicate standalone VM rewrite was accepted")
