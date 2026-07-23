from __future__ import annotations

import pytest

from tools.nasm_exception_handlers import restore_exception_handler_epilogues


def test_restores_active_handler_without_clobbering_rax() -> None:
    source = """\
section .text
probe:
    push rbp
    mov rbp, rsp
    sub rsp, 240
    mov rax, [rel _runtime_handler_top]
    mov [rbp-208], rax
    lea rax, [rbp-200]
    mov [rel _runtime_handler_top], rax
    lea rax, [rbp-200]
    call _runtime_setjmp
    mov rax, 42
.Lret_probe:
    mov rsp, rbp
    pop rbp
    ret
"""
    rewritten, functions, epilogues = restore_exception_handler_epilogues(source)
    assert (functions, epilogues) == (1, 1)
    assert "mov r10, [rel _runtime_handler_top]" in rewritten
    assert "lea r11, [rbp-200]" in rewritten
    assert "mov r10, [rbp-208]" in rewritten
    assert "mov [rel _runtime_handler_top], r10" in rewritten
    assert "mov rax, 42" in rewritten
    assert restore_exception_handler_epilogues(rewritten)[0] == rewritten


def test_nested_handlers_are_peeled_inner_first() -> None:
    source = """\
section .text
probe:
    push rbp
    mov rbp, rsp
    sub rsp, 448
    mov rax, [rel _runtime_handler_top]
    mov [rbp-208], rax
    lea rax, [rbp-200]
    mov [rel _runtime_handler_top], rax
    lea rax, [rbp-200]
    call _runtime_setjmp
    mov rax, [rel _runtime_handler_top]
    mov [rbp-416], rax
    lea rax, [rbp-408]
    mov [rel _runtime_handler_top], rax
    lea rax, [rbp-408]
    call _runtime_setjmp
    mov rsp, rbp
    pop rbp
    ret
"""
    rewritten, _, _ = restore_exception_handler_epilogues(source)
    assert rewritten.index("lea r11, [rbp-408]") < rewritten.index(
        "lea r11, [rbp-200]"
    )


def test_malformed_setjmp_setup_fails_closed() -> None:
    source = """\
section .text
probe:
    push rbp
    mov rbp, rsp
    call _runtime_setjmp
    mov rsp, rbp
    pop rbp
    ret
"""
    with pytest.raises(ValueError, match="setjmp buffer"):
        restore_exception_handler_epilogues(source)
