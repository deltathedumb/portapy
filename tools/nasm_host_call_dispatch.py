"""Replace PortaPy's generated host-dispatch stub with a C callback call."""
from __future__ import annotations

import re
from pathlib import Path


_LABEL = re.compile(r"^(?P<label>[A-Za-z_.$?][\w.$?@]*):\s*(?:;.*)?$")


def patch_host_call_dispatch(source: str, *, target: str) -> str:
    if target not in {"linux", "windows"}:
        raise ValueError(f"unsupported ABI target: {target}")
    lines = source.splitlines()
    start = -1
    for index, line in enumerate(lines):
        if line.strip() == "_portapy_host_dispatch_impl:":
            start = index
            break
    if start < 0:
        raise ValueError("generated source is missing _portapy_host_dispatch_impl")
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if _LABEL.match(lines[index].strip()) is not None:
            end = index
            break

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
    return "\n".join(lines) + "\n"


def patch_file(path: Path, *, target: str) -> Path:
    path.write_text(
        patch_host_call_dispatch(path.read_text(encoding="utf-8"), target=target),
        encoding="utf-8",
    )
    return path


__all__ = ["patch_file", "patch_host_call_dispatch"]
