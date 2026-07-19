from __future__ import annotations

import pytest

from tools.nasm_scalar_abi import append_scalar_abi


_SOURCE = "\n".join(
    [
        "BITS 64",
        "default rel",
        "section .text",
        "_portapy_last_status_impl:",
        "    xor eax, eax",
        "    ret",
        "_portapy_value_from_none_impl:",
        "    mov eax, 1",
        "    ret",
        "_portapy_value_from_bool_impl:",
        "    mov eax, 1",
        "    ret",
        "_portapy_value_as_bool_impl:",
        "    mov eax, 1",
        "    ret",
        "",
    ]
)


def test_linux_scalar_wrappers_clear_handle_outputs() -> None:
    rewritten = append_scalar_abi(_SOURCE, target="linux")
    assert "portapy_value_from_none:" in rewritten
    assert "portapy_value_from_bool:" in rewritten
    assert "portapy_value_as_bool:" in rewritten
    assert "mov qword [rsi], 0" in rewritten
    assert "mov qword [rdx], 0" in rewritten
    assert "call _portapy_value_from_none_impl" in rewritten
    assert "call _portapy_value_from_bool_impl" in rewritten
    assert "mov dword [rdx], ecx" in rewritten


def test_windows_scalar_wrappers_reserve_shadow_space() -> None:
    rewritten = append_scalar_abi(_SOURCE, target="windows")
    assert "portapy_value_from_none:" in rewritten
    assert "portapy_value_from_bool:" in rewritten
    assert "portapy_value_as_bool:" in rewritten
    assert "mov qword [rdx], 0" in rewritten
    assert "mov qword [r8], 0" in rewritten
    assert "sub rsp, 48" in rewritten
    assert "mov dword [r8], r9d" in rewritten


def test_missing_scalar_implementation_fails_closed() -> None:
    with pytest.raises(ValueError, match="missing scalar implementation"):
        append_scalar_abi("BITS 64\n", target="linux")
