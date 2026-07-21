"""Normalize CPython-valid shorthand unsupported by the pinned asmpython parser.

This tool mutates only the CI checkout used by the full-core transition probe.
Exact semantic rewrites fail closed, while compact one-line suites and
semicolon-separated statements are expanded mechanically before compilation.
"""
from __future__ import annotations

import io
from pathlib import Path
import re
import tokenize


REPLACEMENTS: dict[str, tuple[tuple[str, str], ...]] = {
    "src/portapy/core/frontend.py": (
        (
            "                    if bound is None: self.emit(Op.LOAD_CONST, self.constant(None))\n"
            "                    else: self.expr(bound)",
            "                    if bound is None:\n"
            "                        self.emit(Op.LOAD_CONST, self.constant(None))\n"
            "                    else:\n"
            "                        self.expr(bound)",
        ),
        (
            "            operands = [node.left, *node.comparators]",
            "            operands = [node.left]\n"
            "            for comparator in node.comparators:\n"
            "                operands.append(comparator)",
        ),
    ),
    "src/portapy/core/vm.py": (
        (
            "@dataclass(eq=False)\n"
            "class Function:\n"
            "    code: CodeObject\n"
            "    globals: dict[str, object]\n"
            "    defaults: list[object] = field(default_factory=list)\n"
            "    kw_defaults: dict[str, object] = field(default_factory=dict)\n"
            "    closure: dict[str, object] | None = None\n"
            "    vm: \"VirtualMachine | None\" = None\n"
            "    _metadata: dict[str, object] = field(default_factory=dict, init=False, repr=False)\n"
            "\n"
            "    class _CodeDescriptor:\n"
            "        def __get__(self, instance: object, owner: type) -> object:\n"
            "            return self if instance is None else instance.code\n"
            "\n"
            "    class _GlobalsDescriptor:\n"
            "        def __get__(self, instance: object, owner: type) -> object:\n"
            "            return self if instance is None else instance.globals\n"
            "\n"
            "    __code__ = _CodeDescriptor()\n"
            "    __globals__ = _GlobalsDescriptor()",
            "class _FunctionCodeDescriptor:\n"
            "    def __get__(self, instance: object, owner: type) -> object:\n"
            "        return self if instance is None else instance.code\n"
            "\n"
            "\n"
            "class _FunctionGlobalsDescriptor:\n"
            "    def __get__(self, instance: object, owner: type) -> object:\n"
            "        return self if instance is None else instance.globals\n"
            "\n"
            "\n"
            "@dataclass(eq=False)\n"
            "class Function:\n"
            "    code: CodeObject\n"
            "    globals: dict[str, object]\n"
            "    defaults: list[object] = field(default_factory=list)\n"
            "    kw_defaults: dict[str, object] = field(default_factory=dict)\n"
            "    closure: dict[str, object] | None = None\n"
            "    vm: \"VirtualMachine | None\" = None\n"
            "    _metadata: dict[str, object] = field(default_factory=dict, init=False, repr=False)\n"
            "\n"
            "    __code__ = _FunctionCodeDescriptor()\n"
            "    __globals__ = _FunctionGlobalsDescriptor()",
        ),
        (
            "                    right = frame.stack.pop(); left = frame.stack.pop()",
            "                    right = frame.stack.pop()\n"
            "                    left = frame.stack.pop()",
        ),
        (
            "                    index = frame.stack.pop(); value = frame.stack.pop()",
            "                    index = frame.stack.pop()\n"
            "                    value = frame.stack.pop()",
        ),
        (
            "                    item = frame.stack.pop(); index = frame.stack.pop(); value = frame.stack.pop(); value[index] = item",
            "                    item = frame.stack.pop()\n"
            "                    index = frame.stack.pop()\n"
            "                    value = frame.stack.pop()\n"
            "                    value[index] = item",
        ),
        (
            "                    except StopIteration: frame.stack.pop(); frame.ip = instr.arg",
            "                    except StopIteration:\n"
            "                        frame.stack.pop()\n"
            "                        frame.ip = instr.arg",
        ),
        (
            "                    unpacked = [*values[:before], list(values[before:middle_end]), *values[middle_end:]]",
            "                    unpacked = list(values[:before])\n"
            "                    unpacked.append(list(values[before:middle_end]))\n"
            "                    for trailing in values[middle_end:]:\n"
            "                        unpacked.append(trailing)",
        ),
        (
            "                    for item in reversed(unpacked): frame.stack.append(item)",
            "                    for item in reversed(unpacked):\n"
            "                        frame.stack.append(item)",
        ),
        (
            "                    target = frame.stack.pop(); name = frame.code.names[instr.arg]",
            "                    target = frame.stack.pop()\n"
            "                    name = frame.code.names[instr.arg]",
        ),
        (
            "                    value = frame.stack.pop(); target = frame.stack.pop()",
            "                    value = frame.stack.pop()\n"
            "                    target = frame.stack.pop()",
        ),
        (
            "                    if name in frame.locals: del frame.locals[name]\n"
            "                    elif name in frame.globals: del frame.globals[name]\n"
            "                    else: _raise_typed(f\"NameError: name {name!r} is not defined\")",
            "                    if name in frame.locals:\n"
            "                        del frame.locals[name]\n"
            "                    elif name in frame.globals:\n"
            "                        del frame.globals[name]\n"
            "                    else:\n"
            "                        _raise_typed(f\"NameError: name {name!r} is not defined\")",
        ),
        (
            "                    index = frame.stack.pop(); value = frame.stack.pop(); del value[index]",
            "                    index = frame.stack.pop()\n"
            "                    value = frame.stack.pop()\n"
            "                    del value[index]",
        ),
    ),
}

_COMPOUND_PREFIXES = (
    "if ",
    "elif ",
    "else:",
    "for ",
    "while ",
    "try:",
    "except",
    "finally:",
    "with ",
    "async with ",
    "async for ",
    "def ",
    "async def ",
    "class ",
    "match ",
    "case ",
)


def _remove_positional_only_markers(source: str) -> str:
    source = re.sub(r",\s*/\s*,", ", ", source)
    return re.sub(r",\s*/\s*\)", ")", source)


def _top_level_operator_columns(source: str, operator: str) -> list[int]:
    columns: list[int] = []
    depth = 0
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for token in tokens:
            if token.type != tokenize.OP:
                continue
            if token.string in "([{":
                depth += 1
            elif token.string in ")]}":
                if depth > 0:
                    depth -= 1
            elif token.string == operator and depth == 0:
                columns.append(token.start[1])
    except (IndentationError, tokenize.TokenError):
        return []
    return columns


def _split_semicolons(source: str) -> list[str]:
    columns = _top_level_operator_columns(source, ";")
    if not columns:
        return [source.strip()]
    parts: list[str] = []
    start = 0
    for column in columns:
        part = source[start:column].strip()
        if part:
            parts.append(part)
        start = column + 1
    final = source[start:].strip()
    if final:
        parts.append(final)
    return parts


def _expand_compact_line(line: str) -> list[str]:
    newline = "\n" if line.endswith("\n") else ""
    raw = line[:-1] if newline else line
    stripped = raw.lstrip()
    indent = raw[: len(raw) - len(stripped)]
    if not stripped or stripped.startswith("#"):
        return [line]

    if stripped.startswith(_COMPOUND_PREFIXES):
        colons = _top_level_operator_columns(raw, ":")
        if colons:
            colon = colons[0]
            suite = raw[colon + 1 :].strip()
            if suite and not suite.startswith("#"):
                expanded = [raw[: colon + 1].rstrip() + "\n"]
                for statement in _split_semicolons(suite):
                    expanded.append(indent + "    " + statement + "\n")
                return expanded

    statements = _split_semicolons(stripped)
    if len(statements) > 1:
        return [indent + statement + "\n" for statement in statements]
    return [line]


def _expand_compact_statements(source: str) -> str:
    expanded: list[str] = []
    for line in source.splitlines(keepends=True):
        expanded.extend(_expand_compact_line(line))
    return "".join(expanded)


def normalize(path: Path, replacements: tuple[tuple[str, str], ...]) -> None:
    source = path.read_text(encoding="utf-8")
    ordered = sorted(replacements, key=lambda item: len(item[0]), reverse=True)
    for old, new in ordered:
        count = source.count(old)
        if count < 1:
            raise RuntimeError(
                f"normalization target is absent in {path}: {old!r}"
            )
        source = source.replace(old, new)
        print("REPLACED", path, count)
    source = _remove_positional_only_markers(source)
    source = _expand_compact_statements(source)
    path.write_text(source, encoding="utf-8")
    print("NORMALIZED", path)


def main() -> int:
    for name, replacements in REPLACEMENTS.items():
        normalize(Path(name), replacements)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
