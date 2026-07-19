from __future__ import annotations

from tools.nasm_module_init import make_module_initializer


_SOURCE = """\
BITS 64
default rel
global main
extern exit
section .text
main:
    push rbp
    mov rbp, rsp
    sub rsp, 16
    mov rax, 42
    xor rdi, rdi
    call exit
portapy_probe:
    mov rax, 1
    ret
"""


def test_linux_initializer_returns_and_supplies_zero_args() -> None:
    rewritten = make_module_initializer(
        _SOURCE,
        target="linux",
        public_symbol="portapy_library_initialize",
    )
    assert "global main" not in rewritten
    assert "_portapy_module_init:" in rewritten
    assert "call exit" not in rewritten
    assert "portapy_library_initialize:" in rewritten
    assert "sub rsp, 8" in rewritten
    assert "xor edi, edi" in rewritten
    assert "xor esi, esi" in rewritten
    assert "call _portapy_module_init" in rewritten


def test_windows_initializer_reserves_shadow_space() -> None:
    rewritten = make_module_initializer(
        _SOURCE,
        target="windows",
        public_symbol="portapy_library_initialize",
    )
    assert "sub rsp, 40" in rewritten
    assert "xor ecx, ecx" in rewritten
    assert "xor edx, edx" in rewritten
    assert "call _portapy_module_init" in rewritten
