from __future__ import annotations

import pytest

from tools.nasm_state_abi import append_state_abi


_SOURCE = "\n".join(
    [
        "BITS 64",
        "default rel",
        "extern malloc",
        "extern memcpy",
        "extern free",
        "section .text",
        "_portapy_last_status_impl:",
        "    xor eax, eax",
        "    ret",
        "_portapy_exec_span_impl:",
        "    xor eax, eax",
        "    ret",
        "_portapy_get_global_span_impl:",
        "    mov eax, 1",
        "    ret",
        "",
    ]
)


def test_linux_state_wrappers_copy_exact_spans() -> None:
    rewritten = append_state_abi(_SOURCE, target="linux")
    assert "portapy_exec_utf8:" in rewritten
    assert "portapy_get_global_utf8:" in rewritten
    assert ".exec_nul_scan:" in rewritten
    assert ".get_global_nul_scan:" in rewritten
    assert "call _portapy_exec_span_impl" in rewritten
    assert "call _portapy_get_global_span_impl" in rewritten
    assert "mov qword [rcx], 0" in rewritten
    assert "call _portapy_last_status_impl" in rewritten
    assert rewritten.count("call free") == 2


def test_windows_exec_reads_fifth_argument_before_frame_change() -> None:
    rewritten = append_state_abi(_SOURCE, target="windows")
    assert "portapy_exec_utf8:" in rewritten
    assert "cmp qword [rsp + 40], 0" in rewritten
    assert "sub rsp, 64" in rewritten
    assert "mov [rsp + 48], r8" in rewritten
    assert "mov r8, [rsp + 48]\n    call _portapy_exec_span_impl" in rewritten


def test_windows_get_global_clears_and_writes_output() -> None:
    rewritten = append_state_abi(_SOURCE, target="windows")
    assert "portapy_get_global_utf8:" in rewritten
    assert "mov qword [r9], 0" in rewritten
    assert "mov [rsp + 56], r9" in rewritten
    assert "call _portapy_get_global_span_impl" in rewritten
    assert "mov r8, [rsp + 56]" in rewritten
    assert "mov [r8], r9" in rewritten


def test_missing_state_implementation_fails_closed() -> None:
    with pytest.raises(ValueError, match="missing state implementation"):
        append_state_abi("BITS 64\n", target="linux")
