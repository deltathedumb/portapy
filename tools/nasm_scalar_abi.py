"""Append C-ABI wrappers for PortaPy's Python-authored scalar values.

The generated Python functions own value creation, typing, normalization, and
status semantics. These wrappers only validate out-pointers, adapt results, and
preserve the platform calling convention.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


_LABEL_RE = re.compile(r"^(?P<label>[A-Za-z_.$?][\w.$?@]*):\s*(?:;.*)?$")
_REQUIRED_IMPLS = (
    "_portapy_last_status_impl",
    "_portapy_value_from_none_impl",
    "_portapy_value_from_bool_impl",
    "_portapy_value_as_bool_impl",
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

portapy_value_from_none:
    test rsi, rsi
    jz .value_from_none_invalid
    mov qword [rsi], 0
    push rbx
    sub rsp, 16
    mov [rsp], rsi
    call _portapy_value_from_none_impl
    mov [rsp + 8], rax
    call _portapy_last_status_impl
    test eax, eax
    jnz .value_from_none_done
    mov rdx, [rsp]
    mov rcx, [rsp + 8]
    mov [rdx], rcx
.value_from_none_done:
    add rsp, 16
    pop rbx
    ret
.value_from_none_invalid:
    mov eax, 1
    ret

portapy_value_from_bool:
    test rdx, rdx
    jz .value_from_bool_invalid
    mov qword [rdx], 0
    push rbx
    sub rsp, 16
    mov [rsp], rdx
    call _portapy_value_from_bool_impl
    mov [rsp + 8], rax
    call _portapy_last_status_impl
    test eax, eax
    jnz .value_from_bool_done
    mov rdx, [rsp]
    mov rcx, [rsp + 8]
    mov [rdx], rcx
.value_from_bool_done:
    add rsp, 16
    pop rbx
    ret
.value_from_bool_invalid:
    mov eax, 1
    ret

portapy_value_as_bool:
    test rdx, rdx
    jz .value_as_bool_invalid
    push rbx
    sub rsp, 16
    mov [rsp], rdx
    call _portapy_value_as_bool_impl
    mov [rsp + 8], rax
    call _portapy_last_status_impl
    test eax, eax
    jnz .value_as_bool_done
    mov rdx, [rsp]
    mov rcx, [rsp + 8]
    mov dword [rdx], ecx
.value_as_bool_done:
    add rsp, 16
    pop rbx
    ret
.value_as_bool_invalid:
    mov eax, 1
    ret
"""


def _windows_wrappers() -> str:
    return r"""
section .text

portapy_value_from_none:
    test rdx, rdx
    jz .value_from_none_invalid
    mov qword [rdx], 0
    push rbx
    sub rsp, 48
    mov [rsp + 32], rdx
    call _portapy_value_from_none_impl
    mov [rsp + 40], rax
    call _portapy_last_status_impl
    test eax, eax
    jnz .value_from_none_done
    mov rdx, [rsp + 32]
    mov r9, [rsp + 40]
    mov [rdx], r9
.value_from_none_done:
    add rsp, 48
    pop rbx
    ret
.value_from_none_invalid:
    mov eax, 1
    ret

portapy_value_from_bool:
    test r8, r8
    jz .value_from_bool_invalid
    mov qword [r8], 0
    push rbx
    sub rsp, 48
    mov [rsp + 32], r8
    call _portapy_value_from_bool_impl
    mov [rsp + 40], rax
    call _portapy_last_status_impl
    test eax, eax
    jnz .value_from_bool_done
    mov r8, [rsp + 32]
    mov r9, [rsp + 40]
    mov [r8], r9
.value_from_bool_done:
    add rsp, 48
    pop rbx
    ret
.value_from_bool_invalid:
    mov eax, 1
    ret

portapy_value_as_bool:
    test r8, r8
    jz .value_as_bool_invalid
    push rbx
    sub rsp, 48
    mov [rsp + 32], r8
    call _portapy_value_as_bool_impl
    mov [rsp + 40], rax
    call _portapy_last_status_impl
    test eax, eax
    jnz .value_as_bool_done
    mov r8, [rsp + 32]
    mov r9, [rsp + 40]
    mov dword [r8], r9d
.value_as_bool_done:
    add rsp, 48
    pop rbx
    ret
.value_as_bool_invalid:
    mov eax, 1
    ret
"""


def append_scalar_abi(source: str, *, target: str) -> str:
    labels = _labels(source)
    missing = [name for name in _REQUIRED_IMPLS if name not in labels]
    if missing:
        raise ValueError(
            "generated native API is missing scalar implementation label(s): "
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
        append_scalar_abi(
            args.assembly.read_text(encoding="utf-8"),
            target=args.target,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
