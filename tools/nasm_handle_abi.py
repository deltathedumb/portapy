"""Append platform C-ABI wrappers for PortaPy's Python-authored handle core.

The generated Python functions own all runtime/value semantics. These wrappers
only validate C pointers/config metadata, adapt out-parameters, and preserve the
platform calling convention.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


_LABEL_RE = re.compile(r"^(?P<label>[A-Za-z_.$?][\w.$?@]*):\s*(?:;.*)?$")
_REQUIRED_IMPLS = (
    "_portapy_last_status_impl",
    "_portapy_runtime_create_impl",
    "_portapy_runtime_destroy_impl",
    "_portapy_value_from_i64_impl",
    "_portapy_value_get_kind_impl",
    "_portapy_value_as_i64_impl",
    "_portapy_value_retain_impl",
    "_portapy_value_release_impl",
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

portapy_runtime_create:
    test rdi, rdi
    jz .runtime_create_invalid
    test rsi, rsi
    jz .runtime_create_invalid
    cmp qword [rdi], 16
    jb .runtime_create_invalid
    cmp dword [rdi + 8], 1
    jne .runtime_create_abi_mismatch
    push rbx
    mov rbx, rsi
    call _portapy_runtime_create_impl
    test rax, rax
    jz .runtime_create_status
    mov [rbx], rax
    pop rbx
    xor eax, eax
    ret
.runtime_create_status:
    call _portapy_last_status_impl
    pop rbx
    ret
.runtime_create_invalid:
    mov eax, 1
    ret
.runtime_create_abi_mismatch:
    mov eax, 9
    ret

portapy_runtime_destroy:
    jmp _portapy_runtime_destroy_impl

portapy_value_from_i64:
    test rdx, rdx
    jz .value_from_i64_invalid
    push rbx
    sub rsp, 16
    mov rbx, rdx
    call _portapy_value_from_i64_impl
    mov [rsp], rax
    call _portapy_last_status_impl
    test eax, eax
    jnz .value_from_i64_done
    mov rcx, [rsp]
    mov [rbx], rcx
.value_from_i64_done:
    add rsp, 16
    pop rbx
    ret
.value_from_i64_invalid:
    mov eax, 1
    ret

portapy_value_get_kind:
    test rdx, rdx
    jz .value_get_kind_invalid
    push rbx
    sub rsp, 16
    mov rbx, rdx
    call _portapy_value_get_kind_impl
    mov [rsp], rax
    call _portapy_last_status_impl
    test eax, eax
    jnz .value_get_kind_done
    mov rcx, [rsp]
    mov dword [rbx], ecx
.value_get_kind_done:
    add rsp, 16
    pop rbx
    ret
.value_get_kind_invalid:
    mov eax, 1
    ret

portapy_value_as_i64:
    test rdx, rdx
    jz .value_as_i64_invalid
    push rbx
    sub rsp, 16
    mov rbx, rdx
    call _portapy_value_as_i64_impl
    mov [rsp], rax
    call _portapy_last_status_impl
    test eax, eax
    jnz .value_as_i64_done
    mov rcx, [rsp]
    mov [rbx], rcx
.value_as_i64_done:
    add rsp, 16
    pop rbx
    ret
.value_as_i64_invalid:
    mov eax, 1
    ret

portapy_value_retain:
    jmp _portapy_value_retain_impl

portapy_value_release:
    jmp _portapy_value_release_impl
"""


def _windows_wrappers() -> str:
    return r"""
section .text

portapy_runtime_create:
    test rcx, rcx
    jz .runtime_create_invalid
    test rdx, rdx
    jz .runtime_create_invalid
    cmp qword [rcx], 16
    jb .runtime_create_invalid
    cmp dword [rcx + 8], 1
    jne .runtime_create_abi_mismatch
    push rbx
    sub rsp, 32
    mov rbx, rdx
    call _portapy_runtime_create_impl
    test rax, rax
    jz .runtime_create_status
    mov [rbx], rax
    add rsp, 32
    pop rbx
    xor eax, eax
    ret
.runtime_create_status:
    call _portapy_last_status_impl
    add rsp, 32
    pop rbx
    ret
.runtime_create_invalid:
    mov eax, 1
    ret
.runtime_create_abi_mismatch:
    mov eax, 9
    ret

portapy_runtime_destroy:
    jmp _portapy_runtime_destroy_impl

portapy_value_from_i64:
    test r8, r8
    jz .value_from_i64_invalid
    push rbx
    sub rsp, 48
    mov rbx, r8
    call _portapy_value_from_i64_impl
    mov [rsp + 32], rax
    call _portapy_last_status_impl
    test eax, eax
    jnz .value_from_i64_done
    mov r9, [rsp + 32]
    mov [rbx], r9
.value_from_i64_done:
    add rsp, 48
    pop rbx
    ret
.value_from_i64_invalid:
    mov eax, 1
    ret

portapy_value_get_kind:
    test r8, r8
    jz .value_get_kind_invalid
    push rbx
    sub rsp, 48
    mov rbx, r8
    call _portapy_value_get_kind_impl
    mov [rsp + 32], rax
    call _portapy_last_status_impl
    test eax, eax
    jnz .value_get_kind_done
    mov r9, [rsp + 32]
    mov dword [rbx], r9d
.value_get_kind_done:
    add rsp, 48
    pop rbx
    ret
.value_get_kind_invalid:
    mov eax, 1
    ret

portapy_value_as_i64:
    test r8, r8
    jz .value_as_i64_invalid
    push rbx
    sub rsp, 48
    mov rbx, r8
    call _portapy_value_as_i64_impl
    mov [rsp + 32], rax
    call _portapy_last_status_impl
    test eax, eax
    jnz .value_as_i64_done
    mov r9, [rsp + 32]
    mov [rbx], r9
.value_as_i64_done:
    add rsp, 48
    pop rbx
    ret
.value_as_i64_invalid:
    mov eax, 1
    ret

portapy_value_retain:
    jmp _portapy_value_retain_impl

portapy_value_release:
    jmp _portapy_value_release_impl
"""


def append_handle_abi(source: str, *, target: str) -> str:
    labels = _labels(source)
    missing = [name for name in _REQUIRED_IMPLS if name not in labels]
    if missing:
        raise ValueError(
            "generated native API is missing implementation label(s): "
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
    rewritten = append_handle_abi(
        args.assembly.read_text(encoding="utf-8"),
        target=args.target,
    )
    output.write_text(rewritten, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
