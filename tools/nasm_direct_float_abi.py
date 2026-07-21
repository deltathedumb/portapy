"""Append C-ABI wrappers for direct native binary64 Runtime functions.

Unlike the incremental core, the full Runtime's compiled Python entry accepts
and returns real ``float`` values through XMM registers.  These wrappers preserve
out-parameters and status handling without converting through integer payloads.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


_LABEL_RE = re.compile(r"^(?P<label>[A-Za-z_.$?][\w.$?@]*):\s*(?:;.*)?$")
_REQUIRED_IMPLS = (
    "_portapy_last_status_impl",
    "_portapy_value_from_f64_impl",
    "_portapy_value_as_f64_impl",
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

portapy_value_from_f64:
    test rsi, rsi
    jz .value_from_f64_invalid
    mov qword [rsi], 0
    push rbx
    sub rsp, 32
    mov [rsp], rsi
    call _portapy_value_from_f64_impl
    mov [rsp + 8], rax
    call _portapy_last_status_impl
    test eax, eax
    jnz .value_from_f64_done
    mov rdx, [rsp]
    mov rcx, [rsp + 8]
    mov [rdx], rcx
.value_from_f64_done:
    add rsp, 32
    pop rbx
    ret
.value_from_f64_invalid:
    mov eax, 1
    ret

portapy_value_as_f64:
    test rdx, rdx
    jz .value_as_f64_invalid
    push rbx
    sub rsp, 32
    mov [rsp], rdx
    call _portapy_value_as_f64_impl
    movsd [rsp + 8], xmm0
    call _portapy_last_status_impl
    test eax, eax
    jnz .value_as_f64_done
    mov rdx, [rsp]
    movsd xmm0, [rsp + 8]
    movsd [rdx], xmm0
.value_as_f64_done:
    add rsp, 32
    pop rbx
    ret
.value_as_f64_invalid:
    mov eax, 1
    ret
"""


def _windows_wrappers() -> str:
    return r"""
section .text

portapy_value_from_f64:
    test r8, r8
    jz .value_from_f64_invalid
    mov qword [r8], 0
    push rbx
    sub rsp, 48
    mov [rsp + 32], r8
    call _portapy_value_from_f64_impl
    mov [rsp + 40], rax
    call _portapy_last_status_impl
    test eax, eax
    jnz .value_from_f64_done
    mov r8, [rsp + 32]
    mov r9, [rsp + 40]
    mov [r8], r9
.value_from_f64_done:
    add rsp, 48
    pop rbx
    ret
.value_from_f64_invalid:
    mov eax, 1
    ret

portapy_value_as_f64:
    test r8, r8
    jz .value_as_f64_invalid
    push rbx
    sub rsp, 48
    mov [rsp + 32], r8
    call _portapy_value_as_f64_impl
    movsd [rsp + 40], xmm0
    call _portapy_last_status_impl
    test eax, eax
    jnz .value_as_f64_done
    mov r8, [rsp + 32]
    movsd xmm0, [rsp + 40]
    movsd [r8], xmm0
.value_as_f64_done:
    add rsp, 48
    pop rbx
    ret
.value_as_f64_invalid:
    mov eax, 1
    ret
"""


def append_direct_float_abi(source: str, *, target: str) -> str:
    labels = _labels(source)
    missing = [name for name in _REQUIRED_IMPLS if name not in labels]
    if missing:
        raise ValueError(
            "generated full Runtime is missing float implementation label(s): "
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
        append_direct_float_abi(
            args.assembly.read_text(encoding="utf-8"),
            target=args.target,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
