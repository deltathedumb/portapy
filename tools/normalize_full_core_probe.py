"""Normalize CPython-valid shorthand unsupported by the pinned asmpython parser.

This tool mutates only the CI checkout used by the full-core transition probe.
Each replacement is exact and fails closed when no matching source remains, so
the probe cannot silently rewrite unrelated code.
"""
from __future__ import annotations

from pathlib import Path


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
    path.write_text(source, encoding="utf-8")
    print("NORMALIZED", path)


def main() -> int:
    for name, replacements in REPLACEMENTS.items():
        normalize(Path(name), replacements)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
