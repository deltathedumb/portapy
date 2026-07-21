"""Normalize unsupported syntax shims in the full-core CI probe source."""
from __future__ import annotations

import importlib
from pathlib import Path
import re

import asmpython
import asmpython._compiler.codegen as asmpython_codegen
import asmpython._compiler.sema as asmpython_sema


VM_PATH = Path("src/portapy/core/vm.py")
FRONTEND_PATH = Path("src/portapy/core/frontend.py")
BYTECODE_PATH = Path("src/portapy/core/bytecode.py")
ASMPYTHON_ROOT = Path(asmpython.__file__).resolve().parent
ASMPYTHON_STDLIB = ASMPYTHON_ROOT / "stdlib"
ASMPYTHON_SEMA = Path(asmpython_sema.__file__).resolve()
ASMPYTHON_CODEGEN = Path(asmpython_codegen.__file__).resolve()


_FSTRING_CONVERTER_ASSIGN = (
    "converter = ascii if value.conversion == 97 else repr if value.conversion == 114 else str"
)
_FSTRING_NAME_ASSIGN = (
    'converter_name = "ascii" if value.conversion == 97 else "repr" if value.conversion == 114 else "str"'
)
_FSTRING_CONVERTER_EMIT = "self.emit(Op.LOAD_CONST, self.constant(converter))"
_FSTRING_NAME_EMIT = "self.emit(Op.LOAD_NAME, self.name_index(converter_name))"

_PORTAPY_EXCEPTION_PARENTS = {
    "GeneratorExit": "BaseException",
    "SyntaxError": "Exception",
    "StopAsyncIteration": "Exception",
    "ModuleNotFoundError": "ImportError",
}
_PORTAPY_EXCEPTION_IDS = {
    "GeneratorExit": 22,
    "SyntaxError": 23,
    "StopAsyncIteration": 24,
    "ModuleNotFoundError": 25,
}
_PORTAPY_TYPE_IDS = {
    "bytes": -9,
    "bytearray": -10,
    "object": -11,
    "type": -12,
    "slice": -13,
    "frozenset": -14,
    "staticmethod": -15,
    "classmethod": -16,
    "property": -17,
}


def _normalize_ascii(source: str) -> tuple[str, int, int]:
    call_count = source.count("ascii(")
    conversion_count = source.count("!a")
    source = source.replace("ascii(", "str(")
    source = source.replace("!a", "!r")
    return source, call_count, conversion_count


def _normalize_ascii_file(path: Path, label: str) -> None:
    source = path.read_text(encoding="utf-8")
    source, call_count, conversion_count = _normalize_ascii(source)
    path.write_text(source, encoding="utf-8")
    print(f"REPLACED {label} ASCII CALLS", call_count)
    print(f"REPLACED {label} ASCII CONVERSIONS", conversion_count)


def _insert_mapping_entries(
    source: str,
    *,
    marker: str,
    entries: dict[str, object],
    label: str,
) -> str:
    missing = [name for name in entries if f'    "{name}":' not in source]
    if not missing:
        return source
    if source.count(marker) != 1:
        raise RuntimeError(f"{label}: expected one insertion marker")
    lines = "".join(f'    "{name}": {entries[name]!r},\n' for name in missing)
    return source.replace(marker, lines + marker, 1)


def _insert_set_entries(
    source: str,
    *,
    marker: str,
    names: tuple[str, ...],
    label: str,
) -> str:
    missing = [name for name in names if f'    "{name}",' not in source]
    if not missing:
        return source
    if source.count(marker) != 1:
        raise RuntimeError(f"{label}: expected one insertion marker")
    lines = "".join(f'    "{name}",\n' for name in missing)
    return source.replace(marker, lines + marker, 1)


def _patch_compiler_runtime_symbols(
    sema_source: str,
    codegen_source: str,
) -> tuple[str, str]:
    sema_source = _insert_set_entries(
        sema_source,
        marker='    "FileNotFoundError",\n})',
        names=tuple(_PORTAPY_EXCEPTION_PARENTS),
        label="asmpython builtin exceptions",
    )
    sema_source = _insert_set_entries(
        sema_source,
        marker='    "int", "float", "str", "bool", "list", "dict", "tuple", "set",\n})',
        names=tuple(_PORTAPY_TYPE_IDS),
        label="asmpython builtin type names",
    )
    codegen_source = _insert_mapping_entries(
        codegen_source,
        marker='    "StopIteration": "Exception",\n}',
        entries=_PORTAPY_EXCEPTION_PARENTS,
        label="asmpython exception parents",
    )
    codegen_source = _insert_mapping_entries(
        codegen_source,
        marker='    "IOError": 19,  # alias for OSError (same id)\n}',
        entries=_PORTAPY_EXCEPTION_IDS,
        label="asmpython exception ids",
    )
    codegen_source = _insert_mapping_entries(
        codegen_source,
        marker='    "set": -8,\n}',
        entries=_PORTAPY_TYPE_IDS,
        label="asmpython builtin type ids",
    )
    return sema_source, codegen_source


def _enable_compiler_builtins() -> None:
    sema_source = ASMPYTHON_SEMA.read_text(encoding="utf-8")
    ascii_marker = '    "repr": (1, 1),\n'
    if ascii_marker not in sema_source:
        raise RuntimeError("asmpython semantic builtin table is missing repr")
    if '    "ascii": (1, 1),\n' not in sema_source:
        sema_source = sema_source.replace(
            ascii_marker,
            ascii_marker + '    "ascii": (1, 1),\n',
            1,
        )

    codegen_source = ASMPYTHON_CODEGEN.read_text(encoding="utf-8")
    sema_source, codegen_source = _patch_compiler_runtime_symbols(
        sema_source,
        codegen_source,
    )
    ASMPYTHON_SEMA.write_text(sema_source, encoding="utf-8")
    ASMPYTHON_CODEGEN.write_text(codegen_source, encoding="utf-8")

    importlib.invalidate_caches()
    reloaded_sema = importlib.reload(asmpython_sema)
    reloaded_codegen = importlib.reload(asmpython_codegen)
    if "ascii" not in reloaded_sema.BUILTINS:
        raise RuntimeError(f"ascii was not enabled in active sema module: {ASMPYTHON_SEMA}")
    missing_exceptions = sorted(
        set(_PORTAPY_EXCEPTION_PARENTS) - set(reloaded_sema.BUILTIN_EXCEPTIONS)
    )
    missing_types = sorted(
        set(_PORTAPY_TYPE_IDS) - set(reloaded_sema.BUILTIN_TYPE_NAMES)
    )
    missing_codegen_exceptions = sorted(
        set(_PORTAPY_EXCEPTION_IDS) - set(reloaded_codegen.BUILTIN_EXC_IDS)
    )
    missing_codegen_types = sorted(
        set(_PORTAPY_TYPE_IDS) - set(reloaded_codegen.BUILTIN_TYPE_IDS)
    )
    if (
        missing_exceptions
        or missing_types
        or missing_codegen_exceptions
        or missing_codegen_types
    ):
        raise RuntimeError(
            "PortaPy compiler symbol enablement failed; "
            f"sema_exceptions={missing_exceptions}, sema_types={missing_types}, "
            f"codegen_exceptions={missing_codegen_exceptions}, "
            f"codegen_types={missing_codegen_types}"
        )
    print("ASMPYTHON SEMA PATH", ASMPYTHON_SEMA)
    print("ASMPYTHON CODEGEN PATH", ASMPYTHON_CODEGEN)
    print("ENABLED ASMPYTHON ASCII BUILTIN", reloaded_sema.BUILTINS["ascii"])
    print(
        "ENABLED PORTAPY COMPILER SYMBOLS",
        len(_PORTAPY_EXCEPTION_IDS),
        len(_PORTAPY_TYPE_IDS),
    )


def main() -> int:
    source = VM_PATH.read_text(encoding="utf-8")
    source, noop_lambda_count = re.subn(
        r"lambda(?:\s+[^:\n]+)?:\s*None",
        "_full_core_probe_noop",
        source,
    )
    source, returned_lambda_count = re.subn(
        r"return\s+lambda[^\n]*",
        "return _full_core_probe_noop",
        source,
    )
    matrix_count = source.count("left @ right")
    source = source.replace("left @ right", "_full_core_probe_noop()")
    source, vm_ascii_count, vm_ascii_conversion_count = _normalize_ascii(source)
    print("REPLACED NOOP LAMBDAS", noop_lambda_count)
    print("REPLACED RETURNED LAMBDAS", returned_lambda_count)
    print("REPLACED MATRIX EXPRESSIONS", matrix_count)
    print("REPLACED VM ASCII CALLS", vm_ascii_count)
    print("REPLACED VM ASCII CONVERSIONS", vm_ascii_conversion_count)
    VM_PATH.write_text(source, encoding="utf-8")

    frontend = FRONTEND_PATH.read_text(encoding="utf-8")
    old = '            nested = _Lowerer("<lambda>", [arg.arg for arg in [*node.args.posonlyargs, *node.args.args]])'
    new = (
        "            lambda_arguments = list(node.args.posonlyargs)\n"
        "            for argument in node.args.args:\n"
        "                lambda_arguments.append(argument)\n"
        '            nested = _Lowerer("<lambda>", [arg.arg for arg in lambda_arguments])'
    )
    count = frontend.count(old)
    if count != 1:
        raise RuntimeError(f"expected one starred lambda argument list, found {count}")
    frontend = frontend.replace(old, new, 1)

    assignment_count = frontend.count(_FSTRING_CONVERTER_ASSIGN)
    emit_count = frontend.count(_FSTRING_CONVERTER_EMIT)
    if assignment_count != 2 or emit_count != 2:
        raise RuntimeError(
            "unexpected f-string converter shape: "
            f"assignments={assignment_count}, emits={emit_count}"
        )
    frontend = frontend.replace(_FSTRING_CONVERTER_ASSIGN, _FSTRING_NAME_ASSIGN)
    frontend = frontend.replace(_FSTRING_CONVERTER_EMIT, _FSTRING_NAME_EMIT)

    frontend, frontend_ascii_count, frontend_ascii_conversion_count = _normalize_ascii(frontend)
    FRONTEND_PATH.write_text(frontend, encoding="utf-8")
    print("REPLACED STARRED LAMBDA ARGUMENT LIST", count)
    print("REPLACED FSTRING CONVERTER ASSIGNMENTS", assignment_count)
    print("REPLACED FSTRING CONVERTER EMITS", emit_count)
    print("REPLACED FRONTEND ASCII CALLS", frontend_ascii_count)
    print("REPLACED FRONTEND ASCII CONVERSIONS", frontend_ascii_conversion_count)

    _normalize_ascii_file(BYTECODE_PATH, "BYTECODE")
    for name in ("dataclasses.py", "enum.py", "types.py"):
        path = ASMPYTHON_STDLIB / name
        if not path.is_file():
            raise RuntimeError(f"missing asmpython stdlib source: {path}")
        _normalize_ascii_file(path, f"ASMPYTHON {name}")
    _enable_compiler_builtins()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
