"""Patch host dispatch and adapt C calls into asmpython-generated helpers.

The generated runtime currently uses platform nonvolatile registers as ordinary
temporaries. C glue therefore calls it through audited assembly adapters that
preserve the full nonvolatile register set for each supported ABI.
"""
from __future__ import annotations

import re
from pathlib import Path


_LABEL = re.compile(r"^(?P<label>[A-Za-z_.$?][\w.$?@]*):\s*(?:;.*)?$")
_ADAPTER_TARGETS = (
    ("_portapy_cabi_last_status_impl", "_portapy_last_status_impl"),
    (
        "_portapy_cabi_value_from_host_callable_impl",
        "_portapy_value_from_host_callable_impl",
    ),
    (
        "_portapy_cabi_value_get_host_callable_id_impl",
        "_portapy_value_get_host_callable_id_impl",
    ),
    (
        "_portapy_cabi_host_pending_arg_count_impl",
        "_portapy_host_pending_arg_count_impl",
    ),
    ("_portapy_cabi_host_pending_arg_impl", "_portapy_host_pending_arg_impl"),
    (
        "_portapy_cabi_host_dispatch_complete_impl",
        "_portapy_host_dispatch_complete_impl",
    ),
    (
        "_portapy_cabi_delete_global_span_impl",
        "_portapy_delete_global_span_impl",
    ),
    ("_portapy_cabi_global_count_impl", "_portapy_global_count_impl"),
    (
        "_portapy_cabi_global_name_size_impl",
        "_portapy_global_name_size_impl",
    ),
    (
        "_portapy_cabi_global_name_byte_impl",
        "_portapy_global_name_byte_impl",
    ),
    ("_portapy_cabi_tuple_begin_impl", "_portapy_tuple_begin_impl"),
    ("_portapy_cabi_tuple_set_item_impl", "_portapy_tuple_set_item_impl"),
    ("_portapy_cabi_tuple_finish_impl", "_portapy_tuple_finish_impl"),
    ("_portapy_cabi_tuple_get_size_impl", "_portapy_tuple_get_size_impl"),
    ("_portapy_cabi_tuple_get_item_impl", "_portapy_tuple_get_item_impl"),
    ("_portapy_cabi_tuple_release_impl", "_portapy_tuple_release_impl"),
)


def _linux_adapter(adapter: str, implementation: str) -> list[str]:
    return [
        f"{adapter}:",
        "    push rbx",
        "    push rbp",
        "    push r12",
        "    push r13",
        "    push r14",
        "    push r15",
        "    sub rsp, 8",
        f"    call {implementation}",
        "    add rsp, 8",
        "    pop r15",
        "    pop r14",
        "    pop r13",
        "    pop r12",
        "    pop rbp",
        "    pop rbx",
        "    ret",
        "",
    ]


def _windows_adapter(adapter: str, implementation: str) -> list[str]:
    lines = [
        f"{adapter}:",
        "    push rbx",
        "    push rbp",
        "    push rdi",
        "    push rsi",
        "    push r12",
        "    push r13",
        "    push r14",
        "    push r15",
        # 32 bytes of shadow space, 160 bytes for XMM6-XMM15, and 8 bytes
        # of alignment padding before the nested Windows x64 ABI call.
        "    sub rsp, 200",
    ]
    for register in range(6, 16):
        offset = 32 + (register - 6) * 16
        lines.append(f"    movdqu [rsp + {offset}], xmm{register}")
    lines.append(f"    call {implementation}")
    for register in range(6, 16):
        offset = 32 + (register - 6) * 16
        lines.append(f"    movdqu xmm{register}, [rsp + {offset}]")
    lines.extend(
        [
            "    add rsp, 200",
            "    pop r15",
            "    pop r14",
            "    pop r13",
            "    pop r12",
            "    pop rsi",
            "    pop rdi",
            "    pop rbp",
            "    pop rbx",
            "    ret",
            "",
        ]
    )
    return lines


def _abi_adapters(target: str) -> list[str]:
    lines = ["", "section .text", ""]
    for adapter, implementation in _ADAPTER_TARGETS:
        if target == "linux":
            lines.extend(_linux_adapter(adapter, implementation))
        else:
            lines.extend(_windows_adapter(adapter, implementation))
    return lines


def _label_range(lines: list[str], label: str) -> tuple[int, int]:
    start = -1
    for index, line in enumerate(lines):
        if line.strip() == f"{label}:":
            start = index
            break
    if start < 0:
        raise ValueError(f"generated source is missing {label}")
    end = len(lines)
    for index in range(start + 1, len(lines)):
        match = _LABEL.match(lines[index].strip())
        if match is not None and not match.group("label").startswith("."):
            end = index
            break
    return start, end


def _patch_public_release(lines: list[str]) -> None:
    start, end = _label_range(lines, "portapy_value_release")
    replaced = False
    for index in range(start + 1, end):
        if lines[index].strip() == "call _portapy_value_release_impl":
            indent = lines[index][: len(lines[index]) - len(lines[index].lstrip())]
            lines[index] = f"{indent}call _portapy_cabi_tuple_release_impl"
            replaced = True
            break
    if not replaced:
        raise ValueError("public value release wrapper has an unexpected implementation")


def patch_host_call_dispatch(source: str, *, target: str) -> str:
    if target not in {"linux", "windows"}:
        raise ValueError(f"unsupported ABI target: {target}")
    lines = source.splitlines()
    start, end = _label_range(lines, "_portapy_host_dispatch_impl")

    if target == "linux":
        replacement = [
            "_portapy_host_dispatch_impl:",
            "    sub rsp, 8",
            "    call _portapy_host_dispatch_callback wrt ..plt",
            "    add rsp, 8",
            "    ret",
        ]
    else:
        replacement = [
            "_portapy_host_dispatch_impl:",
            "    sub rsp, 40",
            "    call _portapy_host_dispatch_callback",
            "    add rsp, 40",
            "    ret",
        ]
    lines[start:end] = replacement

    extern_line = "extern _portapy_host_dispatch_callback"
    if extern_line not in lines:
        insertion = 0
        while insertion < len(lines) and lines[insertion].startswith(";"):
            insertion += 1
        lines.insert(insertion, extern_line)
    _patch_public_release(lines)
    lines.extend(_abi_adapters(target))
    return "\n".join(lines) + "\n"


def patch_file(path: Path, *, target: str) -> Path:
    path.write_text(
        patch_host_call_dispatch(path.read_text(encoding="utf-8"), target=target),
        encoding="utf-8",
    )
    return path


__all__ = ["patch_file", "patch_host_call_dispatch"]
