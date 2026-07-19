from __future__ import annotations

import pytest

from tools.nasm_eval_abi import append_eval_abi


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
        "_portapy_eval_span_impl:",
        "    mov eax, 1",
        "    ret",
        "",
    ]
)


def test_linux_eval_wrapper_preserves_explicit_length() -> None:
    rewritten = append_eval_abi(_SOURCE, target="linux")
    assert "portapy_eval_utf8:" in rewritten
    assert "mov [rsp + 16], rdx" in rewritten
    assert ".eval_nul_scan:" in rewritten
    assert "lea rdi, [rdx + 1]" in rewritten
    assert "call malloc" in rewritten
    assert "call memcpy" in rewritten
    assert "mov rdx, [rsp + 16]\n    call _portapy_eval_span_impl" in rewritten
    assert "call free" in rewritten
    assert "mov qword [r9], 0" in rewritten


def test_windows_eval_wrapper_reads_stack_arguments_before_frame_change() -> None:
    rewritten = append_eval_abi(_SOURCE, target="windows")
    assert "portapy_eval_utf8:" in rewritten
    assert "cmp qword [rsp + 40], 0" in rewritten
    assert "mov r10, [rsp + 48]" in rewritten
    assert "sub rsp, 80" in rewritten
    assert ".eval_nul_scan:" in rewritten
    assert "mov [rsp + 48], r8" in rewritten
    assert "mov r8, [rsp + 48]\n    call _portapy_eval_span_impl" in rewritten
    assert "mov qword [r10], 0" in rewritten


def test_missing_eval_implementation_fails_closed() -> None:
    with pytest.raises(ValueError, match="missing evaluator implementation"):
        append_eval_abi("BITS 64\n", target="linux")
