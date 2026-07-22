from __future__ import annotations

import pytest

from tools.elf_pic import make_elf_pic


def test_external_calls_use_plt_and_data_uses_got() -> None:
    source = """\
BITS 64
default rel
extern malloc
extern stdin
section .text
probe:
    call malloc
    mov rdx, [stdin]
    ret
"""
    rewritten = make_elf_pic(source)
    assert "call malloc wrt ..plt" in rewritten
    assert "mov rdx, [rel stdin wrt ..got]" in rewritten
    assert "mov rdx, [rdx]" in rewritten
    assert "section .note.GNU-stack noalloc noexec nowrite progbits" in rewritten
    assert make_elf_pic(rewritten) == rewritten


def test_local_calls_are_unchanged() -> None:
    source = """\
BITS 64
extern malloc
section .text
probe:
    call local_helper
    ret
local_helper:
    ret
"""
    rewritten = make_elf_pic(source)
    assert "call local_helper\n" in rewritten
    assert "call local_helper wrt ..plt" not in rewritten


def test_transient_push_is_aligned_around_call() -> None:
    source = """\
BITS 64
section .text
probe:
    push rbp
    mov rbp, rsp
    push rax
    call helper
    pop rax
    leave
    ret
helper:
    ret
"""
    rewritten = make_elf_pic(source)
    assert (
        "    push rax\n"
        "    sub rsp, 8\n"
        "    call helper\n"
        "    add rsp, 8\n"
        "    pop rax"
    ) in rewritten


def test_stack_argument_reservation_absorbs_alignment_padding() -> None:
    source = """\
BITS 64
section .text
probe:
    push rbp
    mov rbp, rsp
    push rax
    sub rsp, 16
    mov qword [rsp+0], 1
    mov qword [rsp+8], 2
    call helper
    add rsp, 16
    pop rax
    leave
    ret
helper:
    ret
"""
    rewritten = make_elf_pic(source)
    assert "sub rsp, 24" in rewritten
    assert "add rsp, 24" in rewritten
    assert "sub rsp, 8\n    call helper" not in rewritten


def test_branch_alternatives_keep_aligned_calls_unchanged() -> None:
    source = """\
BITS 64
section .text
probe:
    push rbp
    mov rbp, rsp
    test rax, rax
    jz .alternate
    call first
    leave
    ret
.alternate:
    call second
    leave
    ret
first:
    ret
second:
    ret
"""
    rewritten = make_elf_pic(source)
    assert "sub rsp, 8" not in rewritten
    assert "call first" in rewritten
    assert "call second" in rewritten


def test_ambiguous_stack_alignment_fails_closed() -> None:
    source = """\
BITS 64
section .text
probe:
    push rbp
    mov rbp, rsp
    test rax, rax
    jz .joined
    push rax
.joined:
    call helper
    leave
    ret
helper:
    ret
"""
    with pytest.raises(ValueError, match="ambiguous stack alignment"):
        make_elf_pic(source)


def test_unknown_external_memory_reference_fails_closed() -> None:
    source = """\
BITS 64
extern foreign_data
section .text
probe:
    mov rax, [foreign_data]
    ret
"""
    with pytest.raises(ValueError, match="unsupported external memory reference"):
        make_elf_pic(source)
