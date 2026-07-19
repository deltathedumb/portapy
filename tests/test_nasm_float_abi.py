from __future__ import annotations

import pytest

from tools.nasm_float_abi import append_float_abi


_SOURCE = "\n".join(
    [
        "BITS 64",
        "default rel",
        "section .text",
        "_portapy_last_status_impl:",
        "    xor eax, eax",
        "    ret",
        "_portapy_value_from_f64_bits_impl:",
        "    mov eax, 1",
        "    ret",
        "_portapy_value_as_f64_bits_impl:",
        "    mov rax, rsi",
        "    ret",
        "",
    ]
)


def test_linux_float_wrappers_bit_cast_xmm0() -> None:
    rewritten = append_float_abi(_SOURCE, target="linux")
    assert "portapy_value_from_f64:" in rewritten
    assert "portapy_value_as_f64:" in rewritten
    assert "movq rsi, xmm0" in rewritten
    assert "mov qword [rsi], 0" in rewritten
    assert "call _portapy_value_from_f64_bits_impl" in rewritten
    assert "call _portapy_value_as_f64_bits_impl" in rewritten


def test_windows_float_wrappers_use_positional_xmm1() -> None:
    rewritten = append_float_abi(_SOURCE, target="windows")
    assert "portapy_value_from_f64:" in rewritten
    assert "portapy_value_as_f64:" in rewritten
    assert "movq rdx, xmm1" in rewritten
    assert "mov qword [r8], 0" in rewritten
    assert "sub rsp, 48" in rewritten


def test_missing_float_implementation_fails_closed() -> None:
    with pytest.raises(ValueError, match="missing float implementation"):
        append_float_abi("BITS 64\n", target="linux")
