"""Append the C ABI wrapper for PortaPy's Python-authored expression evaluator.

The Python implementation owns parsing, precedence, arithmetic, error
classification, and value creation. This pass only validates C byte spans,
copies source bytes into temporary NUL-terminated storage for the compiled
string representation, adapts calling conventions, and writes the result handle.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


_LABEL_RE = re.compile(r"^(?P<label>[A-Za-z_.$?][\w.$?@]*):\s*(?:;.*)?$")
_REQUIRED_IMPLS = (
    "_portapy_last_status_impl",
    "_portapy_eval_span_impl",
)


def _labels(source: str) -> set[str]:
    result: set[str] = set()
    for line in source.splitlines():
        match = _LABEL_RE.match(line.strip())
        if match is not None:
            result.add(match.group("label"))
    return result


def _linux_wrapper() -> str:
    return r"""
section .text

portapy_eval_utf8:
    test rsi, rsi
    jz .eval_invalid
    test r9, r9
    jz .eval_invalid
    test r8, r8
    jz .eval_filename_ok
    test rcx, rcx
    jz .eval_invalid
.eval_filename_ok:
    cmp rdx, -1
    je .eval_invalid
    mov qword [r9], 0
    push rbx
    sub rsp, 48
    mov [rsp], rdi
    mov [rsp + 8], rsi
    mov [rsp + 16], rdx
    mov [rsp + 24], r9

    xor rcx, rcx
.eval_nul_scan:
    cmp rcx, [rsp + 16]
    jge .eval_nul_scan_done
    mov rax, [rsp + 8]
    cmp byte [rax + rcx], 0
    je .eval_embedded_nul
    inc rcx
    jmp .eval_nul_scan
.eval_nul_scan_done:

    mov rdx, [rsp + 16]
    lea rdi, [rdx + 1]
    call malloc
    test rax, rax
    jz .eval_alloc_failed
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
    call _portapy_eval_span_impl
    mov [rsp + 40], rax

    mov rdi, [rsp + 32]
    call free
    call _portapy_last_status_impl
    test eax, eax
    jnz .eval_done
    mov rdx, [rsp + 24]
    mov rcx, [rsp + 40]
    mov [rdx], rcx
.eval_done:
    add rsp, 48
    pop rbx
    ret
.eval_embedded_nul:
    add rsp, 48
    pop rbx
    mov eax, 2
    ret
.eval_alloc_failed:
    add rsp, 48
    pop rbx
    mov eax, 3
    ret
.eval_invalid:
    mov eax, 1
    ret
"""


def _windows_wrapper() -> str:
    return r"""
section .text

portapy_eval_utf8:
    test rdx, rdx
    jz .eval_invalid
    cmp qword [rsp + 40], 0
    je .eval_filename_ok
    test r9, r9
    jz .eval_invalid
.eval_filename_ok:
    mov r10, [rsp + 48]
    test r10, r10
    jz .eval_invalid
    cmp r8, -1
    je .eval_invalid
    mov qword [r10], 0
    push rbx
    sub rsp, 80
    mov [rsp + 32], rcx
    mov [rsp + 40], rdx
    mov [rsp + 48], r8
    mov [rsp + 56], r10

    xor r10, r10
.eval_nul_scan:
    cmp r10, [rsp + 48]
    jge .eval_nul_scan_done
    mov r11, [rsp + 40]
    cmp byte [r11 + r10], 0
    je .eval_embedded_nul
    inc r10
    jmp .eval_nul_scan
.eval_nul_scan_done:

    mov rcx, [rsp + 48]
    inc rcx
    call malloc
    test rax, rax
    jz .eval_alloc_failed
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
    call _portapy_eval_span_impl
    mov [rsp + 72], rax

    mov rcx, [rsp + 64]
    call free
    call _portapy_last_status_impl
    test eax, eax
    jnz .eval_done
    mov r8, [rsp + 56]
    mov r9, [rsp + 72]
    mov [r8], r9
.eval_done:
    add rsp, 80
    pop rbx
    ret
.eval_embedded_nul:
    add rsp, 80
    pop rbx
    mov eax, 2
    ret
.eval_alloc_failed:
    add rsp, 80
    pop rbx
    mov eax, 3
    ret
.eval_invalid:
    mov eax, 1
    ret
"""


def append_eval_abi(source: str, *, target: str) -> str:
    labels = _labels(source)
    missing = [name for name in _REQUIRED_IMPLS if name not in labels]
    if missing:
        raise ValueError(
            "generated native API is missing evaluator implementation label(s): "
            + ", ".join(missing)
        )
    if target == "linux":
        wrapper = _linux_wrapper()
    elif target == "windows":
        wrapper = _windows_wrapper()
    else:
        raise ValueError(f"unsupported ABI target: {target}")
    return source.rstrip() + "\n" + wrapper.strip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assembly", type=Path)
    parser.add_argument("--target", choices=("linux", "windows"), required=True)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args(argv)
    output = args.output or args.assembly
    output.write_text(
        append_eval_abi(
            args.assembly.read_text(encoding="utf-8"),
            target=args.target,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
