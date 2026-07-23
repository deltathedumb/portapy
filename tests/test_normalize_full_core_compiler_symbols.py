from __future__ import annotations

from tools import normalize_full_core_lambdas as normalizer


def _sema_source() -> str:
    return '''BUILTINS = {
    "repr": (1, 1),
    "type": (1, 1),
}
BUILTIN_EXCEPTIONS = frozenset({
    "FileNotFoundError",
})
BUILTIN_TYPE_NAMES = frozenset({
    "int", "float", "str", "bool", "list", "dict", "tuple", "set",
})
'''


def _codegen_source() -> str:
    return '''BUILTIN_EXC_PARENTS = {
    "StopIteration": "Exception",
}
BUILTIN_EXC_IDS = {
    "StopIteration": 21,
    "IOError": 19,  # alias for OSError (same id)
}
BUILTIN_TYPE_IDS = {
    "set": -8,
}
'''


def test_enables_all_portapy_compiler_symbols() -> None:
    sema, codegen = normalizer._patch_compiler_runtime_symbols(
        _sema_source(), _codegen_source()
    )
    for name, parent in normalizer._PORTAPY_EXCEPTION_PARENTS.items():
        assert f'    "{name}",' in sema
        assert f'    "{name}": {parent!r},' in codegen
    for name, identifier in normalizer._PORTAPY_EXCEPTION_IDS.items():
        assert f'    "{name}": {identifier},' in codegen
    for name, identifier in normalizer._PORTAPY_TYPE_IDS.items():
        assert f'    "{name}",' in sema
        assert f'    "{name}": {identifier},' in codegen


def test_compiler_symbol_patch_is_idempotent() -> None:
    sema, codegen = normalizer._patch_compiler_runtime_symbols(
        _sema_source(), _codegen_source()
    )
    assert normalizer._patch_compiler_runtime_symbols(sema, codegen) == (
        sema,
        codegen,
    )
