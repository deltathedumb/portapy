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
