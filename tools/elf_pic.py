"""Rewrite asmpython legacy NASM output for safe ELF shared libraries.

The legacy backend emits direct external references and follows Win64's more
permissive call-stack behavior. ELF shared libraries need PLT/GOT references,
and System V AMD64 requires ``rsp`` to be 16-byte aligned immediately before
``call``. This build-only pass fixes both properties and fails closed when the
control-flow analysis cannot prove a call's alignment.
"""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
import re


_EXTERN_DATA = {"stdin", "stdout", "stderr", "environ"}
_NORETURN_CALLS = {"abort", "exit", "_exit", "longjmp", "_runtime_longjmp"}
_DIRECT_TRANSFER_RE = re.compile(
    r"^(?P<indent>\s*)(?P<op>call|jmp)\s+"
    r"(?P<symbol>[A-Za-z_.$?][\w.$?@]*)\s*$"
)
_CALL_RE = re.compile(r"^(?P<indent>\s*)call\s+(?P<target>.+?)\s*$")
_DATA_LOAD_RE = re.compile(
    r"^(?P<indent>\s*)mov\s+(?P<register>[A-Za-z][A-Za-z0-9]*),\s*"
    r"\[(?:rel\s+)?(?P<symbol>[A-Za-z_.$?][\w.$?@]*)\]\s*$"
)
_EXTERNAL_MEMORY_RE = re.compile(
    r"\[(?:rel\s+)?(?P<symbol>[A-Za-z_.$?][\w.$?@]*)[^\]]*\]"
)
_STACK_ADJUST_RE = re.compile(
    r"^(?P<indent>\s*)(?P<op>add|sub)\s+rsp,\s*"
    r"(?P<amount>0x[0-9A-Fa-f]+|\d+)\s*$"
)
_LABEL_RE = re.compile(r"^(?P<label>[A-Za-z_.$?][\w.$?@]*):$")
_TOP_LEVEL_LABEL_RE = re.compile(r"^[A-Za-z_$?][\w.$?@]*:$")
_JUMP_RE = re.compile(
    r"^(?P<op>j[a-z]+|loop(?:e|ne)?)\s+"
    r"(?:(?:short|near)\s+)?(?P<target>[A-Za-z_.$?][\w.$?@]*)$"
)
_ALIGN_RSP_RE = re.compile(r"^and\s+rsp,\s*(?:-16|0xfffffffffffffff0)$")
_RSP_WRITE_RE = re.compile(r"^(?:mov|lea|xchg)\s+rsp\s*,")
_RBP_WRITE_RE = re.compile(r"^mov\s+rbp\s*,")


@dataclass(frozen=True)
class _Function:
    name: str
    start: int
    end: int


def _code(raw: str) -> str:
    return raw.split(";", 1)[0].strip()


def _extern_symbols(lines: list[str]) -> set[str]:
    symbols: set[str] = set()
    for raw in lines:
        stripped = _code(raw)
        if not stripped.startswith("extern "):
            continue
        payload = stripped.split(None, 1)[1]
        for symbol in payload.replace(",", " ").split():
            symbols.add(symbol)
    return symbols


def _rewrite_external_references(source: str) -> str:
    lines = source.splitlines()
    externs = _extern_symbols(lines)
    output: list[str] = []

    for line_number, raw in enumerate(lines, start=1):
        code = _code(raw)
        transfer_match = _DIRECT_TRANSFER_RE.match(code)
        if transfer_match is not None:
            symbol = transfer_match.group("symbol")
            if symbol in externs:
                output.append(
                    f'{transfer_match.group("indent")}{transfer_match.group("op")} '
                    f"{symbol} wrt ..plt"
                )
                continue

        data_match = _DATA_LOAD_RE.match(code)
        if data_match is not None:
            symbol = data_match.group("symbol")
            if symbol in externs and symbol in _EXTERN_DATA:
                indent = data_match.group("indent")
                register = data_match.group("register")
                output.append(f"{indent}mov {register}, [rel {symbol} wrt ..got]")
                output.append(f"{indent}mov {register}, [{register}]")
                continue

        for memory_match in _EXTERNAL_MEMORY_RE.finditer(code):
            symbol = memory_match.group("symbol")
            if symbol in externs and "wrt ..got" not in memory_match.group(0):
                raise ValueError(
                    f"line {line_number}: unsupported external memory reference "
                    f"to {symbol!r}: {code}"
                )

        output.append(raw)

    return "\n".join(output) + "\n"


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


def _stack_adjust(code: str) -> tuple[str, int] | None:
    match = _STACK_ADJUST_RE.match(code)
    if match is None:
        return None
    return match.group("op"), int(match.group("amount"), 0)


def _call_target(code: str) -> str | None:
    match = _CALL_RE.match(code)
    if match is None:
        return None
    return match.group("target").split()[0]


def _transfer_stack(
    code: str,
    state: tuple[int, int | None],
    *,
    line_number: int,
) -> tuple[int, int | None] | None:
    rsp, rbp = state

    if code == "mov rbp, rsp":
        rbp = rsp
    elif _RBP_WRITE_RE.match(code):
        rbp = None
    elif code == "mov rsp, rbp":
        if rbp is None:
            raise ValueError(
                f"line {line_number}: rsp restored before rbp alignment is known"
            )
        rsp = rbp
    elif code == "leave":
        if rbp is None:
            raise ValueError(
                f"line {line_number}: leave executed before rbp alignment is known"
            )
        rsp = (rbp + 8) % 16
        rbp = None
    elif code.startswith("push "):
        rsp = (rsp - 8) % 16
    elif code.startswith("pop "):
        rsp = (rsp + 8) % 16
        if code == "pop rbp":
            rbp = None
    else:
        adjustment = _stack_adjust(code)
        if adjustment is not None:
            operation, amount = adjustment
            if operation == "sub":
                rsp = (rsp - amount) % 16
            else:
                rsp = (rsp + amount) % 16
        elif _ALIGN_RSP_RE.fullmatch(code):
            rsp = 0
        elif _RSP_WRITE_RE.match(code):
            # The generated longjmp helper restores an opaque saved stack and then
            # transfers control without another call. Stop following that path;
            # any reachable call behind an opaque rsp write must be rejected by a
            # separate top-level entry instead of guessed here.
            return None
        elif code.startswith("enter ") or code.startswith(("pushf", "popf")):
            raise ValueError(
                f"line {line_number}: unsupported stack instruction: {code}"
            )

    return rsp, rbp


def _analyze_call_stacks(lines: list[str]) -> dict[int, set[int]]:
    call_states: dict[int, set[int]] = defaultdict(set)

    for function in _text_functions(lines):
        labels: dict[str, int] = {}
        for index in range(function.start, function.end):
            label_match = _LABEL_RE.fullmatch(_code(lines[index]))
            if label_match is not None:
                labels[label_match.group("label")] = index

        entry = function.start + 1
        if entry >= function.end:
            continue

        states: dict[int, set[tuple[int, int | None]]] = defaultdict(set)
        states[entry].add((8, None))
        pending: deque[int] = deque([entry])

        while pending:
            index = pending.popleft()
            code = _code(lines[index])
            for state in tuple(states[index]):
                next_state = _transfer_stack(
                    code,
                    state,
                    line_number=index + 1,
                )
                if next_state is None:
                    continue

                call_target = _call_target(code)
                if call_target is not None:
                    call_states[index].add(next_state[0])

                successors: list[int] = []
                if code.startswith("ret") or code in {"hlt", "ud2"}:
                    pass
                else:
                    jump_match = _JUMP_RE.fullmatch(code)
                    if jump_match is not None:
                        jump_target = jump_match.group("target")
                        target_index = labels.get(jump_target)
                        if target_index is not None:
                            successors.append(target_index)
                        if jump_match.group("op") != "jmp":
                            successors.append(index + 1)
                    elif code.startswith("jmp "):
                        # An indirect or cross-function tail transfer has no local
                        # fallthrough edge.
                        pass
                    elif call_target in _NORETURN_CALLS:
                        pass
                    else:
                        successors.append(index + 1)

                for successor in successors:
                    if successor >= function.end:
                        continue
                    if next_state not in states[successor]:
                        states[successor].add(next_state)
                        pending.append(successor)

    return call_states


def _next_instruction(lines: list[str], start: int, end: int) -> int | None:
    for index in range(start, end):
        code = _code(lines[index])
        if code:
            return index
    return None


def _function_containing(functions: list[_Function], index: int) -> _Function:
    for function in functions:
        if function.start <= index < function.end:
            return function
    raise ValueError(f"line {index + 1}: call is outside a recognized text function")


def _find_stack_argument_reservation(
    lines: list[str],
    *,
    call_index: int,
    cleanup_amount: int,
    function_start: int,
) -> int | None:
    for index in range(call_index - 1, function_start, -1):
        code = _code(lines[index])
        if not code:
            continue
        if _CALL_RE.match(code) or code.endswith(":"):
            return None
        adjustment = _stack_adjust(code)
        if adjustment == ("sub", cleanup_amount):
            return index
        if (
            adjustment is not None
            or code.startswith(("push ", "pop ", "leave"))
            or _RSP_WRITE_RE.match(code)
        ):
            return None
    return None


def _rewrite_stack_adjustment(raw: str, amount: int) -> str:
    code = _code(raw)
    match = _STACK_ADJUST_RE.match(code)
    if match is None:
        raise AssertionError(raw)
    suffix = ""
    if ";" in raw:
        suffix = " ;" + raw.split(";", 1)[1]
    return f'{match.group("indent")}{match.group("op")} rsp, {amount}{suffix}'


def _align_elf_calls(source: str) -> tuple[str, int, int]:
    lines = source.splitlines()
    functions = _text_functions(lines)
    call_states = _analyze_call_stacks(lines)

    for index, states in call_states.items():
        if len(states) > 1:
            raise ValueError(
                f"line {index + 1}: ambiguous stack alignment {sorted(states)} "
                f"before {_code(lines[index])!r}"
            )
        if not states <= {0, 8}:
            raise ValueError(
                f"line {index + 1}: invalid stack alignment {sorted(states)}"
            )

    misaligned = [index for index, states in call_states.items() if states == {8}]
    insert_before: dict[int, list[str]] = defaultdict(list)
    insert_after: dict[int, list[str]] = defaultdict(list)
    replacements: dict[int, str] = {}
    stack_argument_blocks = 0

    for call_index in misaligned:
        function = _function_containing(functions, call_index)
        cleanup_index = _next_instruction(
            lines,
            call_index + 1,
            function.end,
        )
        cleanup = (
            _stack_adjust(_code(lines[cleanup_index]))
            if cleanup_index is not None
            else None
        )
        reservation_index: int | None = None
        if cleanup is not None and cleanup[0] == "add":
            reservation_index = _find_stack_argument_reservation(
                lines,
                call_index=call_index,
                cleanup_amount=cleanup[1],
                function_start=function.start,
            )

        if reservation_index is not None and cleanup_index is not None:
            new_amount = cleanup[1] + 8
            for index in (reservation_index, cleanup_index):
                replacement = _rewrite_stack_adjustment(lines[index], new_amount)
                existing = replacements.get(index)
                if existing is not None and existing != replacement:
                    raise ValueError(
                        f"line {index + 1}: conflicting stack-argument rewrite"
                    )
                replacements[index] = replacement
            stack_argument_blocks += 1
            continue

        indent = lines[call_index][
            : len(lines[call_index]) - len(lines[call_index].lstrip())
        ]
        insert_before[call_index].append(f"{indent}sub rsp, 8")
        insert_after[call_index].append(f"{indent}add rsp, 8")

    output: list[str] = []
    for index, raw in enumerate(lines):
        output.extend(insert_before[index])
        output.append(replacements.get(index, raw))
        output.extend(insert_after[index])

    remaining = {
        index: states
        for index, states in _analyze_call_stacks(output).items()
        if states != {0}
    }
    if remaining:
        index, states = next(iter(remaining.items()))
        raise ValueError(
            f"line {index + 1}: ELF call-stack alignment failed with "
            f"{sorted(states)} before {_code(output[index])!r}"
        )

    return "\n".join(output) + "\n", len(misaligned), stack_argument_blocks


def make_elf_pic(source: str) -> str:
    rewritten = _rewrite_external_references(source)
    rewritten, _, _ = _align_elf_calls(rewritten)
    lines = rewritten.splitlines()
    stack_note = "section .note.GNU-stack noalloc noexec nowrite progbits"
    if not any(_code(line) == stack_note for line in lines):
        lines.extend(["", stack_note])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assembly", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args(argv)
    output = args.output or args.assembly
    source = _rewrite_external_references(
        args.assembly.read_text(encoding="utf-8")
    )
    rewritten, call_count, stack_argument_blocks = _align_elf_calls(source)
    stack_note = "section .note.GNU-stack noalloc noexec nowrite progbits"
    lines = rewritten.splitlines()
    if not any(_code(line) == stack_note for line in lines):
        lines.extend(["", stack_note])
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("ALIGNED ELF CALL STACKS", call_count, stack_argument_blocks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
