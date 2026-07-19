"""Append C ABI wrappers for PortaPy's Python-authored runtime state.

Assignment parsing, global ownership, lookup, and status semantics remain in
``native_api.py``. These wrappers only validate byte spans, provide temporary
NUL-terminated storage for compiled strings, adapt calling conventions, and
write returned handles.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


_LABEL_RE = re.compile(r"^(?P<label>[A-Za-z_.$?][\w.$?@]*):\s*(?:;.*)?$")
_REQUIRED_IMPLS = (
    "_portapy_last_status_impl",
    "_portapy_exec_span_impl",
    "_portapy_get_global_span_impl",
)


def _labels(source: str) -> set[str]:
    result: set[str] = set()
    for line in source.splitlines():
        match = _LABEL_RE.match(line.strip())
        if match is not None:
            result.add(match.group("label"))
    return result


def _linux_wrappers() -> str:
    return r"""
section .text

portapy_exec_utf8:
    test rsi, rsi
    jz .exec_invalid
    test r8, r8
    jz .exec_filename_ok
    test rcx, rcx
    jz .exec_invalid
.exec_filename_ok:
    cmp rdx, -1
    je .exec_invalid
    push rbx
    sub rsp, 48
    mov [rsp], rdi
    mov [rsp + 8], rsi
    mov [rsp + 16], rdx

    xor rcx, rcx
.exec_nul_scan:
    cmp rcx, [rsp + 16]
    jge .exec_nul_scan_done
    mov rax, [rsp + 8]
    cmp byte [rax + rcx], 0
    je .exec_embedded_nul
    inc rcx
    jmp .exec_nul_scan
.exec_nul_scan_done:

    mov rdx, [rsp + 16]
    lea rdi, [rdx + 1]
    call malloc
    test rax, rax
    jz .exec_alloc_failed
    mov [rsp + 24], rax

    mov rdi, rax
    mov rsi, [rsp + 8]
    mov rdx, [rsp + 16]
    call memcpy
    mov rax, [rsp + 24]
    mov rcx, [rsp + 16]
    mov byte [rax + rcx], 0

    mov rdi, [rsp]
    mov rsi, rax
    mov rdx, [rsp + 16]
    call _portapy_exec_span_impl
    mov [rsp + 32], rax

    mov rdi, [rsp + 24]
    call free
    mov rax, [rsp + 32]
    add rsp, 48
    pop rbx
    ret
.exec_embedded_nul:
    add rsp, 48
    pop rbx
    mov eax, 2
    ret
.exec_alloc_failed:
    add rsp, 48
    pop rbx
    mov eax, 3
    ret
.exec_invalid:
    mov eax, 1
    ret

portapy_get_global_utf8:
    test rsi, rsi
    jz .get_global_invalid
    test rcx, rcx
    jz .get_global_invalid
    test rdx, rdx
    jz .get_global_invalid
    cmp rdx, -1
    je .get_global_invalid
    mov qword [rcx], 0
    push rbx
    sub rsp, 64
    mov [rsp], rdi
    mov [rsp + 8], rsi
    mov [rsp + 16], rdx
    mov [rsp + 24], rcx

    xor rcx, rcx
.get_global_nul_scan:
    cmp rcx, [rsp + 16]
    jge .get_global_nul_scan_done
    mov rax, [rsp + 8]
    cmp byte [rax + rcx], 0
    je .get_global_embedded_nul
    inc rcx
    jmp .get_global_nul_scan
.get_global_nul_scan_done:

    mov rdx, [rsp + 16]
    lea rdi, [rdx + 1]
    call malloc
    test rax, rax
    jz .get_global_alloc_failed
    mov [rsp + 32], rax

    mov rdi, rax
    mov rsi, [rsp + 8]
    mov rdx, [rsp + 16]
    call memcpy
    mov rax, [rsp + 32]
    mov rcx, [rsp + 16]
    mov byte [rax + rcx], 0

    mov rdi, [rsp]
    mov rsi, rax
    mov rdx, [rsp + 16]
    call _portapy_get_global_span_impl
    mov [rsp + 40], rax
    call _portapy_last_status_impl
    mov [rsp + 48], rax

    mov rdi, [rsp + 32]
    call free
    mov rax, [rsp + 48]
    test eax, eax
    jnz .get_global_done
    mov rdx, [rsp + 24]
    mov rcx, [rsp + 40]
    mov [rdx], rcx
.get_global_done:
    add rsp, 64
    pop rbx
    ret
.get_global_embedded_nul:
    add rsp, 64
    pop rbx
    mov eax, 1
    ret
.get_global_alloc_failed:
    add rsp, 64
    pop rbx
    mov eax, 3
    ret
.get_global_invalid:
    mov eax, 1
    ret
"""


def _windows_wrappers() -> str:
    return r"""
section .text

portapy_exec_utf8:
    test rdx, rdx
    jz .exec_invalid
    cmp qword [rsp + 40], 0
    je .exec_filename_ok
    test r9, r9
    jz .exec_invalid
.exec_filename_ok:
    cmp r8, -1
    je .exec_invalid
    push rbx
    sub rsp, 64
    mov [rsp + 32], rcx
    mov [rsp + 40], rdx
    mov [rsp + 48], r8

    xor r10, r10
.exec_nul_scan:
    cmp r10, [rsp + 48]
    jge .exec_nul_scan_done
    mov r11, [rsp + 40]
    cmp byte [r11 + r10], 0
    je .exec_embedded_nul
    inc r10
    jmp .exec_nul_scan
.exec_nul_scan_done:

    mov rcx, [rsp + 48]
    inc rcx
    call malloc
    test rax, rax
    jz .exec_alloc_failed
    mov [rsp + 56], rax

    mov rcx, rax
    mov rdx, [rsp + 40]
    mov r8, [rsp + 48]
    call memcpy
    mov rax, [rsp + 56]
    mov r10, [rsp + 48]
    mov byte [rax + r10], 0

    mov rcx, [rsp + 32]
    mov rdx, rax
    mov r8, [rsp + 48]
    call _portapy_exec_span_impl
    mov [rsp + 40], rax

    mov rcx, [rsp + 56]
    call free
    mov rax, [rsp + 40]
    add rsp, 64
    pop rbx
    ret
.exec_embedded_nul:
    add rsp, 64
    pop rbx
    mov eax, 2
    ret
.exec_alloc_failed:
    add rsp, 64
    pop rbx
    mov eax, 3
    ret
.exec_invalid:
    mov eax, 1
    ret

portapy_get_global_utf8:
    test rdx, rdx
    jz .get_global_invalid
    test r9, r9
    jz .get_global_invalid
    test r8, r8
    jz .get_global_invalid
    cmp r8, -1
    je .get_global_invalid
    mov qword [r9], 0
    push rbx
    sub rsp, 80
    mov [rsp + 32], rcx
    mov [rsp + 40], rdx
    mov [rsp + 48], r8
    mov [rsp + 56], r9

    xor r10, r10
.get_global_nul_scan:
    cmp r10, [rsp + 48]
    jge .get_global_nul_scan_done
    mov r11, [rsp + 40]
    cmp byte [r11 + r10], 0
    je .get_global_embedded_nul
    inc r10
    jmp .get_global_nul_scan
.get_global_nul_scan_done:

    mov rcx, [rsp + 48]
    inc rcx
    call malloc
    test rax, rax
    jz .get_global_alloc_failed
    mov [rsp + 64], rax

    mov rcx, rax
    mov rdx, [rsp + 40]
    mov r8, [rsp + 48]
    call memcpy
    mov rax, [rsp + 64]
    mov r10, [rsp + 48]
    mov byte [rax + r10], 0

    mov rcx, [rsp + 32]
    mov rdx, rax
    mov r8, [rsp + 48]
    call _portapy_get_global_span_impl
    mov [rsp + 72], rax
    call _portapy_last_status_impl
    mov [rsp + 40], rax

    mov rcx, [rsp + 64]
    call free
    mov rax, [rsp + 40]
    test eax, eax
    jnz .get_global_done
    mov r8, [rsp + 56]
    mov r9, [rsp + 72]
    mov [r8], r9
.get_global_done:
    add rsp, 80
    pop rbx
    ret
.get_global_embedded_nul:
    add rsp, 80
    pop rbx
    mov eax, 1
    ret
.get_global_alloc_failed:
    add rsp, 80
    pop rbx
    mov eax, 3
    ret
.get_global_invalid:
    mov eax, 1
    ret
"""


def append_state_abi(source: str, *, target: str) -> str:
    labels = _labels(source)
    missing = [name for name in _REQUIRED_IMPLS if name not in labels]
    if missing:
        raise ValueError(
            "generated native API is missing state implementation label(s): "
            + ", ".join(missing)
        )
    if target == "linux":
        wrappers = _linux_wrappers()
    elif target == "windows":
        wrappers = _windows_wrappers()
    else:
        raise ValueError(f"unsupported ABI target: {target}")
    return source.rstrip() + "\n" + wrappers.strip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assembly", type=Path)
    parser.add_argument("--target", choices=("linux", "windows"), required=True)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args(argv)
    output = args.output or args.assembly
    output.write_text(
        append_state_abi(
            args.assembly.read_text(encoding="utf-8"),
            target=args.target,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
