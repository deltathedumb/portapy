from __future__ import annotations

import pytest

from tools.nasm_handle_abi import append_handle_abi


_SOURCE = "\n".join(
    [
        "BITS 64",
        "default rel",
        "section .text",
        "_portapy_last_status_impl:",
        "    xor eax, eax",
        "    ret",
        "_portapy_runtime_create_impl:",
        "    mov eax, 1",
        "    ret",
        "_portapy_runtime_destroy_impl:",
        "    xor eax, eax",
        "    ret",
        "_portapy_value_from_i64_impl:",
        "    mov eax, 1",
        "    ret",
        "_portapy_value_get_kind_impl:",
        "    mov eax, 2",
        "    ret",
        "_portapy_value_as_i64_impl:",
        "    mov rax, rsi",
        "    ret",
        "_portapy_value_retain_impl:",
        "    xor eax, eax",
        "    ret",
        "_portapy_value_release_impl:",
        "    xor eax, eax",
        "    ret",
        "",
    ]
)


def test_linux_wrappers_use_sysv_arguments_and_write_outputs() -> None:
    rewritten = append_handle_abi(_SOURCE, target="linux")
    assert "portapy_runtime_create:" in rewritten
    assert "cmp dword [rdi + 8], 1" in rewritten
    assert "mov rbx, rdx" in rewritten
    assert "mov [rbx], rcx" in rewritten
    assert "jmp _portapy_value_release_impl" in rewritten


def test_windows_wrappers_reserve_shadow_space() -> None:
    rewritten = append_handle_abi(_SOURCE, target="windows")
    assert "cmp dword [rcx + 8], 1" in rewritten
    assert "sub rsp, 48" in rewritten
    assert "mov rbx, r8" in rewritten
    assert "mov [rbx], r9" in rewritten


def test_missing_python_implementation_fails_closed() -> None:
    with pytest.raises(ValueError, match="missing implementation"):
        append_handle_abi("BITS 64\n", target="linux")
