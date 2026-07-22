"""Restore generated exception-handler chains on every function return.

The legacy backend lowers ``try`` through a global ``_runtime_handler_top``
stack of hand-rolled setjmp buffers. Normal fallthrough restores the parent,
but an early ``return`` jumps straight to the function epilogue. That leaves
the global handler pointing into a dead frame; once the stack is reused, the
next raise restores arbitrary locals as RSP/RIP.

This post-pass adds a no-call epilogue guard to every function that installs a
handler. It preserves RAX/XMM0 return values and peels all still-active local
handlers from inner to outer before the frame is destroyed.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re


_HANDLER_LOAD = "mov rax, [rel _runtime_handler_top]"
_HANDLER_STORE = "mov [rel _runtime_handler_top], rax"
_SETJMP_CALL = "call _runtime_setjmp"
_MARKER = "; portapy: restore active exception handlers before return"
_TOP_LEVEL_LABEL_RE = re.compile(r"^[A-Za-z_$?][\w.$?@]*:$")
_LEA_RAX_LOCAL_RE = re.compile(r"^lea rax, \[rbp-(?P<offset>\d+)\]$")
_STORE_RAX_LOCAL_RE = re.compile(r"^mov \[rbp-(?P<offset>\d+)\], rax$")


@dataclass(frozen=True)
class _Function:
    name: str
    start: int
    end: int


@dataclass(frozen=True)
class _Handler:
    buffer_offset: int
    parent_offset: int


def _code(raw: str) -> str:
    return raw.split(";", 1)[0].strip()


def _text_functions(lines: list[str]) -> list[_Function]:
    functions: list[_Function] = []
    in_text = False
    current_name: str | None = None
    current_start = 0

    for index, raw in enumerate(lines):
        code = _code(raw)
        if code.startswith("section "):
            if current_name is not None:
                functions.append(_Function(current_name, current_start, index))
                current_name = None
            section = code.split(None, 1)[1].split()[0]
            in_text = section == ".text" or section.startswith(".text.")
            continue
        if (
            in_text
            and raw
            and not raw[0].isspace()
            and _TOP_LEVEL_LABEL_RE.fullmatch(code)
        ):
            if current_name is not None:
                functions.append(_Function(current_name, current_start, index))
            current_name = code[:-1]
            current_start = index

    if current_name is not None:
        functions.append(_Function(current_name, current_start, len(lines)))
    return functions


def _previous_instruction(lines: list[str], index: int, floor: int) -> int | None:
    for candidate in range(index - 1, floor - 1, -1):
        if _code(lines[candidate]):
            return candidate
    return None


def _handler_for_setjmp(
    lines: list[str],
    *,
    call_index: int,
    function_start: int,
) -> _Handler:
    cursor = _previous_instruction(lines, call_index, function_start)
    if cursor is None:
        raise ValueError(f"line {call_index + 1}: setjmp has no buffer setup")
    second_lea = _LEA_RAX_LOCAL_RE.fullmatch(_code(lines[cursor]))
    if second_lea is None:
        raise ValueError(
            f"line {call_index + 1}: setjmp buffer is not loaded from rbp"
        )
    buffer_offset = int(second_lea.group("offset"))

    cursor = _previous_instruction(lines, cursor, function_start)
    if cursor is None or _code(lines[cursor]) != _HANDLER_STORE:
        raise ValueError(
            f"line {call_index + 1}: setjmp buffer was not installed globally"
        )

    cursor = _previous_instruction(lines, cursor, function_start)
    if cursor is None:
        raise ValueError(f"line {call_index + 1}: missing handler buffer address")
    first_lea = _LEA_RAX_LOCAL_RE.fullmatch(_code(lines[cursor]))
    if first_lea is None or int(first_lea.group("offset")) != buffer_offset:
        raise ValueError(
            f"line {call_index + 1}: inconsistent setjmp buffer setup"
        )

    parent_store_index = _previous_instruction(lines, cursor, function_start)
    if parent_store_index is None:
        raise ValueError(f"line {call_index + 1}: missing parent handler save")
    parent_store = _STORE_RAX_LOCAL_RE.fullmatch(_code(lines[parent_store_index]))
    if parent_store is None:
        raise ValueError(
            f"line {call_index + 1}: parent handler is not saved to rbp storage"
        )

    parent_load_index = _previous_instruction(
        lines,
        parent_store_index,
        function_start,
    )
    if parent_load_index is None or _code(lines[parent_load_index]) != _HANDLER_LOAD:
        raise ValueError(
            f"line {call_index + 1}: parent handler save has no global load"
        )

    return _Handler(
        buffer_offset=buffer_offset,
        parent_offset=int(parent_store.group("offset")),
    )


def _handlers_in_function(lines: list[str], function: _Function) -> list[_Handler]:
    handlers: list[_Handler] = []
    seen: set[_Handler] = set()
    for index in range(function.start, function.end):
        if _code(lines[index]) != _SETJMP_CALL:
            continue
        handler = _handler_for_setjmp(
            lines,
            call_index=index,
            function_start=function.start,
        )
        if handler not in seen:
            handlers.append(handler)
            seen.add(handler)
    return handlers


def _epilogues(lines: list[str], function: _Function) -> list[int]:
    result: list[int] = []
    for index in range(function.start, function.end - 1):
        code = _code(lines[index])
        next_code = _code(lines[index + 1])
        if code == "mov rsp, rbp" and next_code == "pop rbp":
            after = index + 2
            if after < function.end and _code(lines[after]).startswith("ret"):
                result.append(index)
        elif code == "leave" and next_code.startswith("ret"):
            result.append(index)
    return result


def restore_exception_handler_epilogues(source: str) -> tuple[str, int, int]:
    lines = source.splitlines()
    insertions: dict[int, list[str]] = {}
    function_count = 0
    epilogue_count = 0

    for function_number, function in enumerate(_text_functions(lines), start=1):
        handlers = _handlers_in_function(lines, function)
        if not handlers:
            continue
        if any(
            _MARKER in lines[index]
            for index in range(function.start, function.end)
        ):
            continue

        epilogues = _epilogues(lines, function)
        if not epilogues:
            raise ValueError(
                f"function {function.name!r} installs an exception handler "
                "but has no recognized frame epilogue"
            )

        function_count += 1
        for epilogue_number, epilogue_index in enumerate(epilogues, start=1):
            indent = lines[epilogue_index][
                : len(lines[epilogue_index]) - len(lines[epilogue_index].lstrip())
            ]
            block = [f"{indent}{_MARKER}"]
            for handler_number, handler in enumerate(reversed(handlers), start=1):
                skip_label = (
                    f".Lportapy_handler_cleanup_{function_number}_"
                    f"{epilogue_number}_{handler_number}"
                )
                block.extend(
                    [
                        f"{indent}mov r10, [rel _runtime_handler_top]",
                        f"{indent}lea r11, [rbp-{handler.buffer_offset}]",
                        f"{indent}cmp r10, r11",
                        f"{indent}jne {skip_label}",
                        f"{indent}mov r10, [rbp-{handler.parent_offset}]",
                        f"{indent}mov [rel _runtime_handler_top], r10",
                        f"{skip_label}:",
                    ]
                )
            insertions[epilogue_index] = block
            epilogue_count += 1

    output: list[str] = []
    for index, raw in enumerate(lines):
        output.extend(insertions.get(index, []))
        output.append(raw)
    return "\n".join(output) + "\n", function_count, epilogue_count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assembly", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args(argv)
    output = args.output or args.assembly
    rewritten, function_count, epilogue_count = restore_exception_handler_epilogues(
        args.assembly.read_text(encoding="utf-8")
    )
    output.write_text(rewritten, encoding="utf-8")
    print("RESTORED EXCEPTION HANDLER EPILOGUES", function_count, epilogue_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
